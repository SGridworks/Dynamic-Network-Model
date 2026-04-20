"""SP&L data adapter.

Thin wrapper around the Dynamic Network Model's demo_data loaders. The DNM
repo (https://github.com/SGridworks/Dynamic-Network-Model) is the source of
truth; we expose Riverside-filtered (SUB-001) views for the showcase plus an
escape hatch for the full 23-substation network.

All outputs are JSON-serializable dicts so the agent tools that call into this
module can hand results straight to the LLM as tool results.
"""

from __future__ import annotations

import os
import sys
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

# Suppress pandas DtypeWarning from DNM's load_demo_data, which prints a message
# containing the absolute path to load_demo_data.py. That path can leak identifying
# info when captured into notebook output. Silenced at the adapter boundary.
warnings.filterwarnings("ignore", category=Warning, module=r".*load_demo_data.*")

RIVERSIDE_ID = "SUB-001"

# DNM is the source of the 23 datasets this adapter wraps. Resolution order:
#   1. DNM_REPO_PATH env var
#   2. walk up from this file looking for a sibling demo_data/ dir (common case:
#      this POC is running from inside the DNM repo as examples/hermes-riverside/)
#   3. fall back to ~/Projects/Dynamic-Network-Model
_DNM_ENV = "DNM_REPO_PATH"
_DNM_DEFAULT = Path.home() / "Projects" / "Dynamic-Network-Model"


def _find_dnm_via_walkup() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "demo_data" / "load_demo_data.py").exists():
            return parent
    return None


def _dnm_path() -> Path:
    env_path = os.environ.get(_DNM_ENV)
    if env_path:
        p = Path(env_path).expanduser()
        if (p / "demo_data" / "load_demo_data.py").exists():
            return p
    walkup = _find_dnm_via_walkup()
    if walkup:
        return walkup
    p = _DNM_DEFAULT
    if (p / "demo_data" / "load_demo_data.py").exists():
        return p
    raise FileNotFoundError(
        "Dynamic-Network-Model not found. This example normally lives inside the DNM "
        "repo at examples/hermes-riverside/ and finds the data by walking up.\n"
        f"If you cloned it elsewhere, set {_DNM_ENV}=/path/to/Dynamic-Network-Model "
        f"or clone DNM to {_DNM_DEFAULT}:\n"
        "  git clone https://github.com/SGridworks/Dynamic-Network-Model "
        f"{_DNM_DEFAULT}"
    )


@lru_cache(maxsize=1)
def _loaders():
    """Import DNM loaders once, cache the module."""
    dnm = _dnm_path()
    if str(dnm) not in sys.path:
        sys.path.insert(0, str(dnm))
    from demo_data import load_demo_data as L  # noqa: E402

    return L


@lru_cache(maxsize=1)
def _riverside_feeders_df():
    f = _loaders().load_feeders()
    return f[f["substation_id"] == RIVERSIDE_ID]


@lru_cache(maxsize=1)
def riverside_feeder_ids() -> list[str]:
    """The 3 Riverside feeder IDs (FDR-0001/2/3), in order."""
    df = _riverside_feeders_df()
    return sorted(df.index.tolist() if df.index.name == "feeder_id" else df["feeder_id"].tolist())


# --- Substation-level ---------------------------------------------------------

@lru_cache(maxsize=1)
def riverside_summary() -> dict[str, Any]:
    subs = _loaders().load_substations()
    row = subs.loc[RIVERSIDE_ID] if subs.index.name == "substation_id" else subs[subs["substation_id"] == RIVERSIDE_ID].iloc[0]
    d = row.to_dict()
    d["substation_id"] = RIVERSIDE_ID
    return {k: _coerce(v) for k, v in d.items()}


@lru_cache(maxsize=1)
def riverside_feeders() -> list[dict[str, Any]]:
    df = _riverside_feeders_df().reset_index()
    return [_row_to_dict(r) for _, r in df.iterrows()]


@lru_cache(maxsize=1)
def riverside_transformers() -> list[dict[str, Any]]:
    tx = _loaders().load_transformers().reset_index()
    fids = riverside_feeder_ids()
    return [_row_to_dict(r) for _, r in tx[tx["feeder_id"].isin(fids)].iterrows()]


@lru_cache(maxsize=1)
def riverside_customers_summary() -> dict[str, Any]:
    """Aggregate customer counts; never returns individual customer PII."""
    c = _loaders().load_customers().reset_index()
    fids = riverside_feeder_ids()
    rc = c[c["feeder_id"].isin(fids)]
    total = len(rc)
    by_feeder = rc.groupby("feeder_id").size().to_dict()
    by_type = rc.groupby("customer_type").size().to_dict() if "customer_type" in rc.columns else {}
    return {
        "total": int(total),
        "by_feeder": {k: int(v) for k, v in by_feeder.items()},
        "by_customer_type": {k: int(v) for k, v in by_type.items()},
    }


# --- DER ----------------------------------------------------------------------

@lru_cache(maxsize=1)
def riverside_solar_summary() -> dict[str, Any]:
    s = _loaders().load_solar_installations().reset_index()
    fids = riverside_feeder_ids()
    rs = s[s["feeder_id"].isin(fids)]
    by_feeder = rs.groupby("feeder_id").agg(
        sites=("capacity_kw", "size"),
        total_kw=("capacity_kw", "sum"),
    ).reset_index().to_dict(orient="records")
    return {
        "total_sites": int(len(rs)),
        "total_kw": float(rs["capacity_kw"].sum()),
        "by_feeder": [{k: _coerce(v) for k, v in row.items()} for row in by_feeder],
    }


@lru_cache(maxsize=1)
def riverside_battery_summary() -> dict[str, Any]:
    b = _loaders().load_battery_installations().reset_index()
    fids = riverside_feeder_ids()
    rb = b[b["feeder_id"].isin(fids)]
    kw_col = "capacity_kw" if "capacity_kw" in rb.columns else None
    kwh_col = "capacity_kwh" if "capacity_kwh" in rb.columns else None
    out: dict[str, Any] = {"total_sites": int(len(rb))}
    if kw_col:
        out["total_kw"] = float(rb[kw_col].sum())
    if kwh_col:
        out["total_kwh"] = float(rb[kwh_col].sum())
    return out


@lru_cache(maxsize=1)
def riverside_hosting_capacity() -> dict[str, Any]:
    hc = _loaders().load_hosting_capacity().reset_index()
    fids = riverside_feeder_ids()
    rhc = hc[hc["feeder_id"].isin(fids)]
    by_feeder = rhc.groupby("feeder_id").agg(
        transformers=("hosting_capacity_kw", "size"),
        thermal_kw=("thermal_hosting_capacity_kw", "sum"),
        voltage_kw=("voltage_hosting_capacity_kw", "sum"),
        binding_kw=("hosting_capacity_kw", "sum"),
        existing_der_kw=("existing_der_kw", "sum"),
    ).reset_index().to_dict(orient="records")
    return {
        "total_binding_kw": float(rhc["hosting_capacity_kw"].sum()),
        "total_existing_der_kw": float(rhc["existing_der_kw"].sum()) if "existing_der_kw" in rhc.columns else None,
        "by_feeder": [{k: _coerce(v) for k, v in row.items()} for row in by_feeder],
        "limiting_factors": _value_counts(rhc.get("limiting_factor")),
    }


# --- Microgrid (FDR-0002: Luke AFB Annex) -------------------------------------

@lru_cache(maxsize=1)
def riverside_microgrid() -> dict[str, Any] | None:
    mg = _loaders().load_microgrids().reset_index()
    fids = riverside_feeder_ids()
    rmg = mg[mg["feeder_id"].isin(fids)]
    if rmg.empty:
        return None
    return _row_to_dict(rmg.iloc[0])


# --- Outages ------------------------------------------------------------------

@lru_cache(maxsize=1)
def riverside_outages() -> list[dict[str, Any]]:
    o = _loaders().load_outage_history().reset_index()
    fids = riverside_feeder_ids()
    ro = o[o["feeder_id"].isin(fids)] if "feeder_id" in o.columns else o[o["substation_id"] == RIVERSIDE_ID]
    return [_row_to_dict(r) for _, r in ro.sort_values("start_time").iterrows()]


def riverside_outage(outage_id: str) -> dict[str, Any] | None:
    for o in riverside_outages():
        if o.get("outage_id") == outage_id:
            return o
    return None


# --- Topology -----------------------------------------------------------------

@lru_cache(maxsize=1)
def riverside_topology() -> dict[str, Any]:
    L = _loaders()
    nodes = L.load_network_nodes().reset_index()
    edges = L.load_network_edges().reset_index()
    fids = riverside_feeder_ids()
    rn = nodes[nodes["feeder_id"].isin(fids)] if "feeder_id" in nodes.columns else nodes.head(0)
    re_ = edges[edges["feeder_id"].isin(fids)] if "feeder_id" in edges.columns else edges.head(0)
    return {
        "nodes": {
            "total": int(len(rn)),
            "by_feeder": {k: int(v) for k, v in rn.groupby("feeder_id").size().items()},
            "by_equipment_class": _value_counts(rn.get("equipment_class")),
        },
        "edges": {
            "total": int(len(re_)),
            "by_feeder": {k: int(v) for k, v in re_.groupby("feeder_id").size().items()},
            "by_edge_type": _value_counts(re_.get("edge_type")),
        },
    }


# --- Time-series snapshots ---------------------------------------------------
#
# SP&L time-series files use 15-minute timestamps spanning 2020-01 through 2024-10.
# Snapshots take an ISO timestamp; the adapter finds the nearest 15-min tick.


@lru_cache(maxsize=4)
def _load_profiles_df():
    import pandas as pd

    path = _dnm_path() / "demo_data" / "load_profiles.csv.gz"
    df = pd.read_csv(path, usecols=["feeder_id", "timestamp", "load_mw", "load_mvar", "voltage_pu", "power_factor"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@lru_cache(maxsize=4)
def _solar_profile_df():
    import pandas as pd

    path = _dnm_path() / "demo_data" / "solar_profiles.csv"
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@lru_cache(maxsize=4)
def _weather_df():
    import pandas as pd

    path = _dnm_path() / "demo_data" / "weather_data.csv"
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def _nearest_row(df, ts: str):
    import pandas as pd

    target = pd.to_datetime(ts)
    idx = (df["timestamp"] - target).abs().idxmin()
    return df.loc[idx]


def riverside_load_snapshot(timestamp: str) -> dict[str, Any]:
    """Load (MW + MVAR) and voltage (pu) per Riverside feeder at the nearest 15-min tick."""
    df = _load_profiles_df()
    fids = riverside_feeder_ids()
    rdf = df[df["feeder_id"].isin(fids)]
    if rdf.empty:
        return {"timestamp": timestamp, "note": "no Riverside load profile rows"}
    results = {}
    for fid in fids:
        fdf = rdf[rdf["feeder_id"] == fid]
        if fdf.empty:
            continue
        row = _nearest_row(fdf, timestamp)
        results[fid] = {
            "timestamp": row["timestamp"].isoformat(),
            "load_mw": float(row["load_mw"]),
            "load_mvar": float(row["load_mvar"]),
            "voltage_pu": float(row["voltage_pu"]),
            "power_factor": float(row["power_factor"]),
        }
    return {"requested": timestamp, "by_feeder": results}


def riverside_solar_snapshot(timestamp: str) -> dict[str, Any]:
    """Solar generation at the requested timestamp.

    The SP&L solar profile is a typical-year shape indexed by month and hour (288 rows),
    not a calendar time-series. We match on month-of-year + hour-of-day.
    """
    import pandas as pd

    df = _solar_profile_df().copy()
    target = pd.to_datetime(timestamp)
    df["month"] = df["timestamp"].dt.month
    df["hour"] = df["timestamp"].dt.hour
    match = df[(df["month"] == target.month) & (df["hour"] == target.hour)]
    if match.empty:
        return {"requested": timestamp, "note": "no solar profile entry for this month+hour"}
    row = match.iloc[0]
    # SP&L stores generation_pct_of_capacity on 0-100 scale; convert to fraction.
    frac = float(row["generation_pct_of_capacity"]) / 100.0
    solar_summary = riverside_solar_summary()
    feeder_kw = {
        f["feeder_id"]: float(f["total_kw"]) * frac
        for f in solar_summary["by_feeder"]
    }
    return {
        "requested": timestamp,
        "profile_applied_month": int(row["month"]),
        "profile_applied_hour": int(row["hour"]),
        "clear_sky_factor": float(row["clear_sky_factor"]),
        "generation_pct_of_capacity": float(row["generation_pct_of_capacity"]),
        "ghi_w_per_m2": float(row["ghi_w_per_m2"]),
        "estimated_solar_kw_by_feeder": {k: round(v, 1) for k, v in feeder_kw.items()},
    }


def riverside_weather(timestamp: str) -> dict[str, Any]:
    """Weather at the nearest tick: temperature (F), humidity, wind, GHI, cloud cover, storm/heatwave flags."""
    df = _weather_df()
    row = _nearest_row(df, timestamp)
    return {
        "requested": timestamp,
        "at_timestamp": row["timestamp"].isoformat(),
        "temperature_f": float(row["temperature_f"]),
        "humidity_pct": float(row["humidity_pct"]),
        "wind_speed_mph": float(row["wind_speed_mph"]),
        "ghi_w_per_m2": float(row["ghi_w_per_m2"]),
        "cloud_cover_pct": float(row["cloud_cover_pct"]),
        "is_heatwave": bool(row["is_heatwave"]),
        "is_storm": bool(row["is_storm"]),
    }


# --- Helpers ------------------------------------------------------------------

def _coerce(v: Any) -> Any:
    try:
        import pandas as pd

        if pd.isna(v):
            return None
    except Exception:
        pass
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _row_to_dict(row) -> dict[str, Any]:
    return {k: _coerce(v) for k, v in row.to_dict().items()}


def _value_counts(s) -> dict[str, int]:
    if s is None:
        return {}
    try:
        return {str(k): int(v) for k, v in s.value_counts().items()}
    except Exception:
        return {}
