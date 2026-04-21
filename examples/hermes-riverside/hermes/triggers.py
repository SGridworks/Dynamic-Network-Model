"""Event-driven dispatch for the Hermes substation copilot.

Hermes doesn't wait for an operator query. It watches the utility's existing
telemetry and dispatches the right playbook when a detection signal fires.

This module ships two reference watchers:

    PowerQualityWatcher  — historian/PQ + AMI → VVO playbooks
    AMIOutageWatcher     — AMI last-gasp cluster → restoration playbooks

The watchers emit `TriggerEvent(playbook_key, context)`. The dispatcher looks
the playbook up in `hermes/agent/HERMES.md` (via `hermes.agent.prompts`),
renders it with the event context, and hands it to the agent loop as the first
user turn. What the agent actually does on each event is authored in HERMES.md,
not here. Add a new event kind by adding a playbook to the markdown file and
wiring a detection threshold in this module.

Each watcher is a minimal polling loop. Replace the stub `_poll_*` method with
a call into your utility's historian / AMI head-end / weather vendor. A
production deployment swaps the poll for a Kafka/MQTT subscription, but the
contract (detection → TriggerEvent → dispatcher) stays identical.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from hermes.data import spl


# --- Event model -------------------------------------------------------------


@dataclass
class TriggerEvent:
    """A detection signal routed to a playbook in HERMES.md."""

    source: str                             # "AMI last-gasp", "Power quality", ...
    playbook_key: str                       # maps to ### heading under Playbooks
    summary: str                            # human-readable event line
    context: dict[str, Any] = field(default_factory=dict)  # renders into template

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "playbook_key": self.playbook_key,
            "summary": self.summary,
            "context": self.context,
        }


Dispatcher = Callable[[TriggerEvent], None]


# --- Power-quality → VVO playbooks ------------------------------------------


class PowerQualityWatcher:
    """Poll historian + AMI for voltage excursions on Riverside feeders.

    Fires `upper_band_voltage` on FDR-0001 when V > 1.05 pu sustains.
    Fires `far_end_undervoltage` on FDR-0003 when far-end V < 0.95 pu clusters.
    Fires `dvdt_storm` when dV/dt is high AND weather.is_storm is set.
    """

    UPPER_BAND_PU = 1.05
    LOWER_BAND_PU = 0.95
    DVDT_PU_PER_MIN = 0.02

    def __init__(self, dispatch: Dispatcher, poll_seconds: int = 60):
        self.dispatch = dispatch
        self.poll_seconds = poll_seconds
        self._last_fire: dict[str, float] = {}

    def _poll_feeder_state(self, feeder_id: str) -> dict[str, float]:
        """Stub — replace with historian/AMI query.

        Returns a dict with at least: voltage_pu, far_end_voltage_pu,
        dvdt_pu_per_min, ami_upper_band_count, ami_lower_band_count.
        """
        snap = spl.riverside_load_snapshot(time.strftime("%Y-%m-%d %H:%M"))
        fdr = snap.get("by_feeder", {}).get(feeder_id, {})
        return {
            "voltage_pu": fdr.get("voltage_pu", 1.0),
            "far_end_voltage_pu": fdr.get("voltage_pu", 1.0),
            "dvdt_pu_per_min": 0.0,
            "ami_upper_band_count": 0,
            "ami_lower_band_count": 0,
        }

    def _evaluate(self) -> TriggerEvent | None:
        ts = time.strftime("%Y-%m-%d %H:%M")

        fdr1 = self._poll_feeder_state("FDR-0001")
        if fdr1["voltage_pu"] >= self.UPPER_BAND_PU or fdr1["ami_upper_band_count"] >= 10:
            return TriggerEvent(
                source="Power quality · AMI",
                playbook_key="upper_band_voltage",
                summary=(
                    f"V={fdr1['voltage_pu']:.3f} pu at FDR-0001 head · "
                    f"{fdr1['ami_upper_band_count']} AMI meters in upper band"
                ),
                context={
                    "source": "Power quality · AMI",
                    "feeder_id": "FDR-0001",
                    "timestamp": ts,
                    **fdr1,
                },
            )

        fdr3 = self._poll_feeder_state("FDR-0003")
        if fdr3["far_end_voltage_pu"] <= self.LOWER_BAND_PU or fdr3["ami_lower_band_count"] >= 8:
            battery_sites = spl.riverside_battery_summary().get("total_sites", 0)
            return TriggerEvent(
                source="Power quality · AMI",
                playbook_key="far_end_undervoltage",
                summary=(
                    f"Far-end V={fdr3['far_end_voltage_pu']:.3f} pu on FDR-0003 · "
                    f"{fdr3['ami_lower_band_count']} AMI meters in lower band"
                ),
                context={
                    "source": "Power quality · AMI",
                    "feeder_id": "FDR-0003",
                    "timestamp": ts,
                    "battery_sites": battery_sites,
                    **fdr3,
                },
            )

        weather = spl.riverside_weather(ts)
        if fdr1["dvdt_pu_per_min"] >= self.DVDT_PU_PER_MIN and weather.get("is_storm"):
            return TriggerEvent(
                source="Power quality · weather",
                playbook_key="dvdt_storm",
                summary=(
                    f"dV/dt={fdr1['dvdt_pu_per_min']:.3f} pu/min on FDR-0001 · "
                    f"weather.is_storm=True"
                ),
                context={
                    "source": "Power quality · weather",
                    "feeder_id": "FDR-0001",
                    "timestamp": ts,
                    "cloud_cover_pct": weather.get("cloud_cover_pct", "<unset>"),
                    **fdr1,
                },
            )
        return None

    def _debounce_ok(self, key: str, cooldown_seconds: int = 900) -> bool:
        now = time.monotonic()
        last = self._last_fire.get(key, 0.0)
        if now - last < cooldown_seconds:
            return False
        self._last_fire[key] = now
        return True

    def tick(self) -> None:
        ev = self._evaluate()
        if ev and self._debounce_ok(ev.playbook_key):
            self.dispatch(ev)

    def run(self) -> None:
        while True:
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001
                print(f"[PowerQualityWatcher] tick error: {e}")
            time.sleep(self.poll_seconds)


# --- AMI last-gasp → restoration playbooks ----------------------------------


class AMIOutageWatcher:
    """Cluster AMI last-gasp messages and dispatch restoration playbooks.

    The fastest outage-detection signal on a distribution feeder is an AMI
    last-gasp cluster — individual meters reporting loss-of-power within
    seconds of the event, before the upstream SCADA/OMS has finished
    evaluating the trip.

    Fires `ami_last_gasp_cluster` on a cluster for a feeder without a
    microgrid. Fires `microgrid_islanding` if the affected feeder hosts one.
    """

    CLUSTER_THRESHOLD = 50
    CLUSTER_WINDOW_SECONDS = 120

    def __init__(self, dispatch: Dispatcher, poll_seconds: int = 10):
        self.dispatch = dispatch
        self.poll_seconds = poll_seconds
        self._last_fire: dict[str, float] = {}

    def _poll_last_gasp_counts(self) -> dict[str, int]:
        """Stub — replace with query to AMI head-end.

        Returns last-gasp message count per feeder within CLUSTER_WINDOW_SECONDS.
        """
        return {fid: 0 for fid in spl.riverside_feeder_ids()}

    def _microgrid_on_feeder(self, feeder_id: str) -> dict | None:
        mg = spl.riverside_microgrid()
        if mg and mg.get("feeder_id") == feeder_id:
            return mg
        return None

    def _debounce_ok(self, feeder_id: str, cooldown_seconds: int = 1800) -> bool:
        now = time.monotonic()
        last = self._last_fire.get(feeder_id, 0.0)
        if now - last < cooldown_seconds:
            return False
        self._last_fire[feeder_id] = now
        return True

    def tick(self) -> None:
        ts = time.strftime("%Y-%m-%d %H:%M")
        counts = self._poll_last_gasp_counts()
        for feeder_id, n in counts.items():
            if n < self.CLUSTER_THRESHOLD:
                continue
            if not self._debounce_ok(feeder_id):
                continue
            mg = self._microgrid_on_feeder(feeder_id)
            if mg:
                ev = TriggerEvent(
                    source="AMI last-gasp · microgrid controller",
                    playbook_key="microgrid_islanding",
                    summary=(
                        f"{n} last-gasp messages on {feeder_id} in "
                        f"{self.CLUSTER_WINDOW_SECONDS}s · "
                        f"{mg['facility_name']} ({mg['microgrid_id']})"
                    ),
                    context={
                        "source": "AMI last-gasp · microgrid controller",
                        "feeder_id": feeder_id,
                        "count": n,
                        "window_seconds": self.CLUSTER_WINDOW_SECONDS,
                        "timestamp": ts,
                        "microgrid_name": mg["facility_name"],
                        "microgrid_id": mg["microgrid_id"],
                    },
                )
            else:
                ev = TriggerEvent(
                    source="AMI last-gasp",
                    playbook_key="ami_last_gasp_cluster",
                    summary=(
                        f"{n} last-gasp messages on {feeder_id} in "
                        f"{self.CLUSTER_WINDOW_SECONDS}s · OMS ticket pending"
                    ),
                    context={
                        "source": "AMI last-gasp",
                        "feeder_id": feeder_id,
                        "count": n,
                        "window_seconds": self.CLUSTER_WINDOW_SECONDS,
                        "timestamp": ts,
                    },
                )
            self.dispatch(ev)

    def run(self) -> None:
        while True:
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001
                print(f"[AMIOutageWatcher] tick error: {e}")
            time.sleep(self.poll_seconds)


# --- Default dispatcher ------------------------------------------------------


def default_dispatcher() -> Dispatcher:
    """Render the playbook from HERMES.md and hand it to the agent loop."""
    from hermes.agent.loop import run as run_turn
    from hermes.agent.prompts import action_message, system_message

    def _dispatch(ev: TriggerEvent) -> None:
        print(f"[hermes.triggers] {ev.source}: {ev.summary}")
        print(f"[hermes.triggers] playbook={ev.playbook_key}")
        history = [system_message()]
        user_turn = action_message(ev.playbook_key, **ev.context)
        turn = run_turn(user_turn["content"], history=history)
        print(f"[hermes.triggers] agent response:\n{turn.final_text}\n")

    return _dispatch


if __name__ == "__main__":
    import threading

    dispatch = default_dispatcher()
    threading.Thread(target=PowerQualityWatcher(dispatch).run, daemon=True).start()
    threading.Thread(target=AMIOutageWatcher(dispatch).run, daemon=True).start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
