"""Event-driven dispatch for the Hermes substation copilot.

Hermes doesn't wait for an operator query. It watches the utility's existing
telemetry and dispatches the right scenario when a detection signal fires.

This module ships three reference watchers:

    PowerQualityWatcher  — historian/PQ → VVO scenarios (1, 2, 3)
    AMIOutageWatcher     — AMI last-gasp → restoration scenarios (4, 5)
    WeatherWatcher       — storm flag   — augments the PQ signal on scenario 3

Each watcher is a simple polling loop. Replace the stub `_poll_*` method with a
call into your utility's historian / AMI head-end / weather vendor. Nothing
else in the stack changes. When a trigger fires, the watcher hands a
`TriggerEvent` to its dispatcher callback, which spawns the corresponding
Hermes scenario via `scripts.record_traces.record_one()`.

The 80-line watcher pattern below is intentionally minimal. A production
deployment replaces the poll with a Kafka/MQTT subscription, but the contract
(detection → TriggerEvent → dispatcher) stays identical.
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
    """A detection signal that dispatches a scenario."""

    source: str                       # "Power quality", "AMI last-gasp", etc.
    event: str                        # human-readable trigger description
    scenario_id: str                  # which scenario to dispatch
    context: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "event": self.event,
            "scenario_id": self.scenario_id,
            "context": self.context,
        }


Dispatcher = Callable[[TriggerEvent], None]


# --- Power-quality → VVO (scenarios 1, 2, 3) --------------------------------


class PowerQualityWatcher:
    """Poll historian + AMI for voltage excursions on Riverside feeders.

    Fires scenario-01 when upper-band voltage is sustained on FDR-0001.
    Fires scenario-02 when far-end undervoltage clusters on FDR-0003.
    Fires scenario-03 when dV/dt jumps AND weather.is_storm is set.

    Replace `_poll_feeder_state` with a call into your historian / AMI stack.
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

        Returns a dict with keys: voltage_pu (feeder-head), far_end_voltage_pu,
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
        fdr1 = self._poll_feeder_state("FDR-0001")
        if fdr1["voltage_pu"] >= self.UPPER_BAND_PU or fdr1["ami_upper_band_count"] >= 10:
            return TriggerEvent(
                source="Power quality · AMI",
                event=(
                    f"V={fdr1['voltage_pu']:.3f} pu at FDR-0001 head · "
                    f"{fdr1['ami_upper_band_count']} AMI meters in upper band"
                ),
                scenario_id="01-afternoon-der",
                context=fdr1,
            )

        fdr3 = self._poll_feeder_state("FDR-0003")
        if fdr3["far_end_voltage_pu"] <= self.LOWER_BAND_PU or fdr3["ami_lower_band_count"] >= 8:
            return TriggerEvent(
                source="Power quality · AMI",
                event=(
                    f"Far-end V={fdr3['far_end_voltage_pu']:.3f} pu on FDR-0003 · "
                    f"{fdr3['ami_lower_band_count']} AMI meters in lower band"
                ),
                scenario_id="02-evening-sag",
                context=fdr3,
            )

        storm = self._weather_is_storm()
        if fdr1["dvdt_pu_per_min"] >= self.DVDT_PU_PER_MIN and storm:
            return TriggerEvent(
                source="Power quality · weather",
                event=(
                    f"dV/dt={fdr1['dvdt_pu_per_min']:.3f} pu/min on FDR-0001 · "
                    f"weather.is_storm=True"
                ),
                scenario_id="03-monsoon",
                context={**fdr1, "is_storm": storm},
            )
        return None

    def _weather_is_storm(self) -> bool:
        w = spl.riverside_weather(time.strftime("%Y-%m-%d %H:%M"))
        return bool(w.get("is_storm"))

    def _debounce_ok(self, scenario_id: str, cooldown_seconds: int = 900) -> bool:
        """Avoid re-firing the same scenario within a cooldown window."""
        now = time.monotonic()
        last = self._last_fire.get(scenario_id, 0.0)
        if now - last < cooldown_seconds:
            return False
        self._last_fire[scenario_id] = now
        return True

    def tick(self) -> None:
        ev = self._evaluate()
        if ev and self._debounce_ok(ev.scenario_id):
            self.dispatch(ev)

    def run(self) -> None:
        """Long-running poll loop. In production, replace with pub/sub."""
        while True:
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001
                print(f"[PowerQualityWatcher] tick error: {e}")
            time.sleep(self.poll_seconds)


# --- AMI last-gasp → restoration (scenarios 4, 5) ---------------------------


class AMIOutageWatcher:
    """Cluster AMI last-gasp messages; dispatch restoration scenarios.

    The fastest detection signal on a distribution feeder is an AMI last-gasp
    cluster — individual meters reporting loss-of-power within seconds of the
    event, before the upstream SCADA/OMS has finished evaluating the trip.

    Fires scenario-04 on a last-gasp cluster for a feeder without a microgrid.
    Fires scenario-05 if the affected feeder hosts a microgrid.
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

    def tick(self) -> None:
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
                    event=(
                        f"{n} last-gasp messages on {feeder_id} in "
                        f"{self.CLUSTER_WINDOW_SECONDS}s · {mg['facility_name']} "
                        f"({mg['microgrid_id']}) on feeder"
                    ),
                    scenario_id="05-microgrid-island",
                    context={"feeder_id": feeder_id, "count": n, "microgrid": mg},
                )
            else:
                ev = TriggerEvent(
                    source="AMI last-gasp",
                    event=(
                        f"{n} last-gasp messages on {feeder_id} in "
                        f"{self.CLUSTER_WINDOW_SECONDS}s · OMS ticket pending"
                    ),
                    scenario_id="04-single-feeder-restoration",
                    context={"feeder_id": feeder_id, "count": n},
                )
            self.dispatch(ev)

    def _debounce_ok(self, feeder_id: str, cooldown_seconds: int = 1800) -> bool:
        now = time.monotonic()
        last = self._last_fire.get(feeder_id, 0.0)
        if now - last < cooldown_seconds:
            return False
        self._last_fire[feeder_id] = now
        return True

    def run(self) -> None:
        while True:
            try:
                self.tick()
            except Exception as e:  # noqa: BLE001
                print(f"[AMIOutageWatcher] tick error: {e}")
            time.sleep(self.poll_seconds)


# --- Default dispatcher ------------------------------------------------------


def default_dispatcher(out_dir: str = "fixtures/traces/live") -> Dispatcher:
    """Return a dispatcher that records a Hermes trace for the triggered scenario."""
    from pathlib import Path

    from scripts.record_traces import record_one

    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)

    def _dispatch(ev: TriggerEvent) -> None:
        print(f"[hermes.triggers] {ev.source}: {ev.event}")
        print(f"[hermes.triggers] dispatching scenario {ev.scenario_id}")
        record_one(ev.scenario_id, target)

    return _dispatch


if __name__ == "__main__":
    dispatch = default_dispatcher()
    import threading

    threading.Thread(target=PowerQualityWatcher(dispatch).run, daemon=True).start()
    threading.Thread(target=AMIOutageWatcher(dispatch).run, daemon=True).start()
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
