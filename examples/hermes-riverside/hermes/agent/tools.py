"""Tools the agent calls for the Riverside showcase.

Every tool returns a JSON-serializable dict. All reads route through
hermes.data.spl (which wraps DNM's load_demo_data). Tools are scoped to
SUB-001 Riverside by default — the showcase narrative.
"""

from __future__ import annotations

from typing import Any

from hermes.data import spl


# --- Tool implementations -----------------------------------------------------

def get_substation_summary() -> dict[str, Any]:
    """Riverside overview: voltage levels, rated vs peak MVA, transformer count, age."""
    return spl.riverside_summary()


def get_feeders() -> dict[str, Any]:
    """All 3 Riverside feeders with direction, length, capacity, customer counts."""
    return {"feeders": spl.riverside_feeders()}


def get_customers_summary() -> dict[str, Any]:
    """Aggregated customer counts. No individual-customer data (CEII)."""
    return spl.riverside_customers_summary()


def get_der_inventory() -> dict[str, Any]:
    """DER on Riverside feeders: solar (sites + kW) and BESS (sites + kW/kWh)."""
    return {
        "solar": spl.riverside_solar_summary(),
        "battery": spl.riverside_battery_summary(),
    }


def get_hosting_capacity() -> dict[str, Any]:
    """Hosting capacity per Riverside feeder, split by thermal vs voltage limit.

    Useful for VVO reasoning: if voltage is the binding constraint, reactive
    support (cap banks, smart-inverter VAR, BESS) unlocks headroom.
    """
    return spl.riverside_hosting_capacity()


def get_microgrid() -> dict[str, Any]:
    """The Luke AFB Annex microgrid on FDR-0002: generation mix, island duration, critical load."""
    mg = spl.riverside_microgrid()
    return mg or {"error": "No microgrid present on Riverside."}


def get_topology() -> dict[str, Any]:
    """Riverside graph: node/edge counts by feeder, equipment classes, edge types.

    Includes breakers, sectionalizers, open points — the switching levers for
    restoration scenarios.
    """
    return spl.riverside_topology()


def get_outage_history(
    feeder_id: str | None = None,
    cause: str | None = None,
    min_customers: int = 0,
    limit: int = 20,
) -> dict[str, Any]:
    """Historical outages at Riverside, optionally filtered by feeder, cause, or severity."""
    outs = spl.riverside_outages()
    if feeder_id:
        outs = [o for o in outs if o.get("feeder_id") == feeder_id]
    if cause:
        outs = [o for o in outs if cause.lower() in str(o.get("cause", "")).lower()]
    if min_customers:
        outs = [o for o in outs if int(o.get("customers_affected", 0)) >= min_customers]
    # Most recent first, capped.
    outs = sorted(outs, key=lambda o: o.get("start_time", ""), reverse=True)[:limit]
    return {"count": len(outs), "outages": outs}


def get_outage(outage_id: str) -> dict[str, Any]:
    """One outage record by id."""
    o = spl.riverside_outage(outage_id)
    return o or {"error": f"No outage {outage_id} on Riverside."}


def get_load_snapshot(timestamp: str) -> dict[str, Any]:
    """Load (MW + MVAR), voltage (pu), and power factor per Riverside feeder at a timestamp."""
    return spl.riverside_load_snapshot(timestamp)


def get_solar_snapshot(timestamp: str) -> dict[str, Any]:
    """Solar conditions and estimated per-feeder generation (kW) at a timestamp."""
    return spl.riverside_solar_snapshot(timestamp)


def get_weather(timestamp: str) -> dict[str, Any]:
    """Weather at Riverside for a timestamp (temperature, wind, GHI, cloud cover, storm/heatwave flags)."""
    return spl.riverside_weather(timestamp)


# --- Tool specs (LiteLLM / OpenAI shape) --------------------------------------

TOOL_SPECS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_substation_summary",
            "description": "Get the Riverside (SUB-001) substation overview: voltage levels, MVA rating, peak load, transformer count, age.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_feeders",
            "description": "List Riverside's 3 feeders (FDR-0001/2/3) with direction, length, conductor type, capacity, customer counts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customers_summary",
            "description": "Aggregated customer counts for Riverside by feeder and customer type. No individual-customer data.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_der_inventory",
            "description": "Solar and BESS inventory on Riverside feeders: total sites, kW, kWh.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_hosting_capacity",
            "description": "Per-feeder hosting capacity at Riverside, split by thermal and voltage limits. The limiting-factor breakdown tells you whether VAR support unlocks headroom.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_microgrid",
            "description": "The Luke AFB Annex microgrid on FDR-0002: solar/battery/CHP capacity, critical load, island duration.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_topology",
            "description": "Riverside graph summary: node/edge counts by feeder, equipment classes (breakers, sectionalizers, open points), edge types.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_outage_history",
            "description": "Historical outages at Riverside. Filter by feeder_id (FDR-0001/2/3), cause (equipment_failure|weather|overload|animal|vegetation), min_customers, or limit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "feeder_id": {"type": "string"},
                    "cause": {"type": "string"},
                    "min_customers": {"type": "integer"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_outage",
            "description": "Look up a single outage by outage_id (e.g. OUT-00017).",
            "parameters": {
                "type": "object",
                "properties": {"outage_id": {"type": "string"}},
                "required": ["outage_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_load_snapshot",
            "description": "Per-feeder load (MW and MVAR), voltage (pu), and power factor at a timestamp. Pass an ISO string like '2023-07-19 14:00'. SP&L time-series runs 2020-01 through 2024-10.",
            "parameters": {
                "type": "object",
                "properties": {"timestamp": {"type": "string"}},
                "required": ["timestamp"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_solar_snapshot",
            "description": "Solar conditions (clear-sky factor, GHI) and estimated per-feeder solar generation (kW) at a timestamp.",
            "parameters": {
                "type": "object",
                "properties": {"timestamp": {"type": "string"}},
                "required": ["timestamp"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Weather at Riverside for a timestamp: temperature_f, humidity_pct, wind_speed_mph, ghi_w_per_m2, cloud_cover_pct, is_heatwave, is_storm.",
            "parameters": {
                "type": "object",
                "properties": {"timestamp": {"type": "string"}},
                "required": ["timestamp"],
            },
        },
    },
]


REGISTRY = {
    "get_substation_summary": get_substation_summary,
    "get_feeders": get_feeders,
    "get_customers_summary": get_customers_summary,
    "get_der_inventory": get_der_inventory,
    "get_hosting_capacity": get_hosting_capacity,
    "get_microgrid": get_microgrid,
    "get_topology": get_topology,
    "get_outage_history": get_outage_history,
    "get_outage": get_outage,
    "get_load_snapshot": get_load_snapshot,
    "get_solar_snapshot": get_solar_snapshot,
    "get_weather": get_weather,
}


def call(name: str, **kwargs: Any) -> dict[str, Any]:
    fn = REGISTRY.get(name)
    if not fn:
        return {"error": f"unknown tool '{name}'"}
    try:
        return fn(**kwargs)
    except TypeError as e:
        return {"error": f"bad arguments to {name}: {e}"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{name} failed: {e}"}
