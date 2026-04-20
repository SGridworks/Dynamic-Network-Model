"""Authoritative scenario definitions for the Hermes-at-Riverside showcase.

Each scenario binds a narrative intro, the SP&L data preamble a reader sees in
the notebook, and the user query the agent answers. The preamble is a list of
(label, callable) pairs — the callable returns a JSON-serializable dict that
the notebook renders as a code cell output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from hermes.data import spl


@dataclass
class Scenario:
    id: str
    title: str
    kind: str  # "vvo" or "restoration"
    intro_md: str
    preamble: list[tuple[str, Callable[[], dict[str, Any]]]]
    query: str
    takeaway_md: str


SCENARIOS: list[Scenario] = [
    Scenario(
        id="01-afternoon-der",
        title="Afternoon DER absorption on FDR-0001",
        kind="vvo",
        intro_md=(
            "Riverside's west feeder (FDR-0001) holds the highest concentration of "
            "rooftop solar on the substation — 12.3 MW of existing DER against a "
            "voltage-limited hosting capacity. On a clear July afternoon the feeder "
            "is running near voltage ceiling as solar generation peaks. The agent is "
            "asked what a VVO advisor would recommend for the next 15-minute interval."
        ),
        preamble=[
            ("hosting_capacity", spl.riverside_hosting_capacity),
            ("feeders", lambda: {"feeders": spl.riverside_feeders()}),
            ("der_inventory", lambda: {
                "solar": spl.riverside_solar_summary(),
                "battery": spl.riverside_battery_summary(),
            }),
            ("load_snapshot_2023-07-19_14h", lambda: spl.riverside_load_snapshot("2023-07-19 14:00")),
            ("solar_snapshot_2023-07-19_14h", lambda: spl.riverside_solar_snapshot("2023-07-19 14:00")),
        ],
        query=(
            "It's July 19, 2023, 2pm local. FDR-0001 is carrying heavy solar output and "
            "voltage is pushing the upper band. What should I do for the next 15 minutes? "
            "Keep it specific — name the devices and the direction of change."
        ),
        takeaway_md=(
            "**Takeaway.** The hosting-capacity split tells the operator where the "
            "room is. When voltage is the binding constraint on 95% of transformers, "
            "Q-mode reactive support on existing DER and a cap-bank switch order "
            "buys real MW of headroom without capital spend. A utility extending this "
            "would feed the agent's recommendations into its DERMS as shadow-mode "
            "proposals for 2–3 quarters before a human-confirmed Rung-3 pilot."
        ),
    ),
    Scenario(
        id="02-evening-sag",
        title="Evening voltage sag on FDR-0003",
        kind="vvo",
        intro_md=(
            "FDR-0003 runs south for 6.4 miles — the longest Riverside feeder, and "
            "the one with the most residential load hitting its evening peak. Solar "
            "is dropping, AC load is still up, and the far-end voltage is sagging. "
            "The agent is asked to coordinate BESS dispatch and voltage support."
        ),
        preamble=[
            ("feeders", lambda: {"feeders": spl.riverside_feeders()}),
            ("hosting_capacity", spl.riverside_hosting_capacity),
            ("der_inventory", lambda: {
                "solar": spl.riverside_solar_summary(),
                "battery": spl.riverside_battery_summary(),
            }),
            ("load_snapshot_2023-07-19_19h", lambda: spl.riverside_load_snapshot("2023-07-19 19:00")),
            ("solar_snapshot_2023-07-19_19h", lambda: spl.riverside_solar_snapshot("2023-07-19 19:00")),
        ],
        query=(
            "Evening peak on FDR-0003, July 19 2023, 7pm local. Far-end voltage is sagging. "
            "I have BESS sites on feeder. What coordinated action should I take? "
            "Include the load/solar context in your reasoning."
        ),
        takeaway_md=(
            "**Takeaway.** Evening peak is where distributed BESS earns its keep — "
            "if the agent can reason about the coincident load-minus-solar shape, "
            "BESS dispatch becomes a voltage-support tool, not just a peak-shave tool. "
            "That reframing is what utilities are buying when they fund a DER orchestration "
            "layer; the agent makes the reframing cheap."
        ),
    ),
    Scenario(
        id="03-monsoon",
        title="Monsoon event — DER absorption vs voltage hold",
        kind="vvo",
        intro_md=(
            "A summer monsoon storm cell is over west Phoenix. Cloud transients are "
            "driving sharp solar output swings on FDR-0001. The agent is asked how "
            "to think about the tradeoff between absorbing remaining DER and holding "
            "voltage steady as the storm passes."
        ),
        preamble=[
            ("weather_2020-07-08_16h", lambda: spl.riverside_weather("2020-07-08 16:00")),
            ("solar_snapshot_2020-07-08_16h", lambda: spl.riverside_solar_snapshot("2020-07-08 16:00")),
            ("load_snapshot_2020-07-08_16h", lambda: spl.riverside_load_snapshot("2020-07-08 16:00")),
            ("hosting_capacity", spl.riverside_hosting_capacity),
            ("der_inventory", lambda: {
                "solar": spl.riverside_solar_summary(),
                "battery": spl.riverside_battery_summary(),
            }),
        ],
        query=(
            "Monsoon cell over the west Valley — July 8, 2020, 4pm local, storm flag is "
            "set on the weather feed. Solar output is swinging sharply every few minutes. "
            "For FDR-0001 in the next hour, what's the right tradeoff between chasing DER "
            "absorption and holding voltage steady? Be explicit about what you would NOT do."
        ),
        takeaway_md=(
            "**Takeaway.** Fast solar transients are where a reasoning loop beats a "
            "setpoint table. The agent can propose a 'hold-and-ride-through' posture "
            "for the storm window that a static VVO algorithm can't express — and it "
            "can defend the choice in plain English to the operator who has to sign off."
        ),
    ),
    Scenario(
        id="04-single-feeder-restoration",
        title="Weather outage on FDR-0003 — single-feeder restoration",
        kind="restoration",
        intro_md=(
            "OUT-00016 is a weather-driven outage on FDR-0003 (the long south feeder) "
            "from September 2020: an overhead-line event took out 1,007 customers for "
            "4 hours 45 minutes. Riverside has 3 breakers, 6 sectionalizers, and 3 "
            "open-point switches — enough topology to do partial restoration via tie "
            "switching while the faulted section is cleared. The agent is asked to "
            "draft a restoration sequence."
        ),
        preamble=[
            ("outage_OUT-00016", lambda: spl.riverside_outage("OUT-00016")),
            ("topology", spl.riverside_topology),
            ("feeders", lambda: {"feeders": spl.riverside_feeders()}),
            ("hosting_capacity", spl.riverside_hosting_capacity),
        ],
        query=(
            "Draft a restoration plan for OUT-00016 (FDR-0003 overhead-line fault, "
            "weather-driven, ~1000 customers out). Use what the topology gives you — "
            "sectionalizers, open points, and any tie-switch paths to adjacent feeders. "
            "Call out what requires operator judgment."
        ),
        takeaway_md=(
            "**Takeaway.** Restoration reasoning is the cleanest fit for agentic "
            "assistance — the decision surface is well-defined (isolate, transfer, "
            "restore) and the evidence comes from the outage ticket, the topology, "
            "and the adjacent-feeder load margin. A shadow-mode agent logging its "
            "recommended sequence alongside the operator's actions builds an "
            "audit-grade evidence base for Rung-3 authorization without changing "
            "anything the operator does today."
        ),
    ),
    Scenario(
        id="05-microgrid-island",
        title="Multi-feeder event — Luke AFB microgrid islanding",
        kind="restoration",
        intro_md=(
            "OUT-00009 hit FDR-0002 in May 2020 — a weather-driven fuse operation took "
            "the feeder down for 8 hours and affected 806 customers. FDR-0002 hosts "
            "Luke AFB Annex (MG-0005), a military microgrid with 4 MW solar + 3 MW / "
            "12 MWh BESS + 2.5 MW CHP, capable of 2.3 hours of islanded operation "
            "against 5.16 MW of critical load. The agent is asked when and how to "
            "island and resync."
        ),
        preamble=[
            ("outage_OUT-00009", lambda: spl.riverside_outage("OUT-00009")),
            ("microgrid", spl.riverside_microgrid),
            ("topology", spl.riverside_topology),
            ("feeders", lambda: {"feeders": spl.riverside_feeders()}),
        ],
        query=(
            "OUT-00009: weather-driven fuse operation, FDR-0002, 8-hour outage. "
            "FDR-0002 hosts the Luke AFB Annex microgrid (MG-0005). Walk me through "
            "whether to island, when, and the resync conditions. Be explicit about "
            "what happens after the 2.3-hour battery window if the feeder is still out."
        ),
        takeaway_md=(
            "**Takeaway.** Microgrid islanding decisions live at the intersection of "
            "protection coordination, battery state-of-charge, and a customer the "
            "utility cannot afford to drop. An agent that pulls the microgrid's "
            "published envelopes, the outage ETR, and the CHP fuel status into one "
            "reasoning pass — and explains the tradeoffs in plain English — is the "
            "shortest path from 'the operator manually thinks through this' to 'the "
            "operator confirms a recommendation in 30 seconds.'"
        ),
    ),
]


def by_id(sid: str) -> Scenario:
    for s in SCENARIOS:
        if s.id == sid:
            return s
    raise KeyError(f"Unknown scenario: {sid}")
