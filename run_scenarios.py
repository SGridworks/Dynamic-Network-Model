#!/usr/bin/env python3
"""Simulate DER growth scenarios through OpenDSS power flow."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import opendssdirect as odd
import pandas as pd

DATA_DIR = Path("demo_data")
NETWORK_DIR = Path("sisyphean-power-and-light/network")
SCENARIO_DIR = Path("sisyphean-power-and-light/scenarios")

MAX_FEEDERS = 12
rng = np.random.default_rng(seed=42)


def load_der_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    """Load DER datasets filtered to model feeders."""
    edges = pd.read_csv(DATA_DIR / "network_edges.csv")
    feeders = list(edges["feeder_id"].unique()[:MAX_FEEDERS])

    solar = pd.read_csv(DATA_DIR / "solar_installations.csv")
    solar = solar[(solar["feeder_id"].isin(feeders)) & (solar["status"] == "active")]

    ev = pd.read_csv(DATA_DIR / "ev_chargers.csv")
    ev = ev[(ev["feeder_id"].isin(feeders)) & (ev["status"] == "active")]

    batt = pd.read_csv(DATA_DIR / "battery_installations.csv")
    batt = batt[(batt["feeder_id"].isin(feeders)) & (batt["status"] == "active")]

    return solar, ev, batt, feeders


def get_xfmr_buses() -> set[str]:
    """Get XFMR bus IDs present in the line network."""
    with open(NETWORK_DIR / "lines.dss") as f:
        text = f.read()
    import re
    buses = set(re.findall(r"bus_XFMR-\d+", text))
    return {b.replace("bus_", "") for b in buses}


def scale_der(
    solar: pd.DataFrame,
    ev: pd.DataFrame,
    batt: pd.DataFrame,
    scenario: dict[str, Any],
    n_customers: int,
    xfmr_ids: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Scale DER to match scenario penetration levels."""
    solar_target = int(n_customers * scenario["solar_penetration_pct"])
    ev_target = int(n_customers * scenario["ev_penetration_pct"])
    batt_target = int(n_customers * scenario["battery_storage_pct"])

    # Filter to transformers in model
    solar_m = solar[solar["transformer_id"].isin(xfmr_ids)].copy()
    ev_m = ev[ev["transformer_id"].isin(xfmr_ids)].copy()
    batt_m = batt[batt["transformer_id"].isin(xfmr_ids)].copy()

    # Scale: if target > current, duplicate random rows; if less, sample down
    solar_out = _scale_df(solar_m, solar_target, "solar_id", "SOL-S")
    ev_out = _scale_df(ev_m, ev_target, "charger_id", "EV-S")
    batt_out = _scale_df(batt_m, batt_target, "battery_id", "BATT-S")

    return solar_out, ev_out, batt_out


def _scale_df(
    df: pd.DataFrame, target: int, id_col: str, prefix: str
) -> pd.DataFrame:
    """Scale a DER dataframe to target count by sampling or duplicating."""
    if len(df) == 0:
        return df
    if target <= len(df):
        return df.sample(n=target, random_state=42)
    # Need more — duplicate with new IDs
    extra_n = target - len(df)
    extra = df.sample(n=extra_n, replace=True, random_state=42).copy()
    extra[id_col] = [f"{prefix}-{i:06d}" for i in range(extra_n)]
    return pd.concat([df, extra], ignore_index=True)


def write_scenario_dss(
    solar_s: pd.DataFrame,
    ev_s: pd.DataFrame,
    batt_s: pd.DataFrame,
    scenario: dict[str, Any],
    out_dir: Path,
) -> None:
    """Write scenario-specific DSS files (PV, EV loads, storage)."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # PVSystems — aggregate by transformer
    pv_lines = ["! Scenario PV Systems", ""]
    if len(solar_s) > 0:
        solar_agg = solar_s.groupby("transformer_id")["capacity_kw"].sum()
        solar_derate = scenario.get("solar_derate_factor", 1.0)
        for xid, total_kw in solar_agg.items():
            kw = total_kw * solar_derate
            pv_lines.append(
                f"New PVSystem.pv_{xid} bus1=bus_{xid}_sec phases=1 "
                f"kV=0.24 kVA={kw:.1f} Pmpp={kw:.1f} irradiance=1 pf=1"
            )
    (out_dir / "pvsystems.dss").write_text("\n".join(pv_lines) + "\n")

    # EV Chargers — aggregate by transformer as additional loads
    ev_lines = ["! Scenario EV Charging Loads", ""]
    if len(ev_s) > 0:
        ev_agg = ev_s.groupby("transformer_id")["power_kw"].sum()
        for xid, total_kw in ev_agg.items():
            ev_lines.append(
                f"New Load.ev_{xid} bus1=bus_{xid}_sec phases=1 "
                f"kv=0.24 kw={total_kw:.2f} pf=0.98"
            )
    (out_dir / "ev_loads.dss").write_text("\n".join(ev_lines) + "\n")

    # Storage — aggregate by transformer
    stor_lines = ["! Scenario Battery Storage", ""]
    if len(batt_s) > 0:
        batt_agg = batt_s.groupby("transformer_id").agg(
            total_kwh=("capacity_kwh", "sum"),
            total_kw=("power_kw", "sum"),
        )
        for xid, row in batt_agg.iterrows():
            stor_lines.append(
                f"New Storage.batt_{xid} bus1=bus_{xid}_sec phases=1 "
                f"kWRated={row['total_kw']:.1f} kWhRated={row['total_kwh']:.1f} "
                f"%stored=50"
            )
    (out_dir / "storage.dss").write_text("\n".join(stor_lines) + "\n")

    # Scenario master — wraps base model with scenario DER
    load_mult = scenario.get("peak_load_multiplier", 1.0)
    master = f"""\
! SP&L Scenario: {scenario['name']}

Clear

New Circuit.SPL bus1=sourcebus basekV=69 pu=1.04 phases=3 MVAsc3=2000 MVAsc1=2100
New Transformer.sub_xfmr phases=3 windings=2 buses=[sourcebus bus_SUB-001] conns=[delta wye] kvs=[69 12.47] kvas=[20000 20000] XHL=7

Redirect {NETWORK_DIR.resolve()}/lines.dss
Redirect {NETWORK_DIR.resolve()}/transformers.dss
Redirect {NETWORK_DIR.resolve()}/loads.dss

! Scenario DER (replaces base PV/storage)
Redirect {out_dir.resolve()}/pvsystems.dss
Redirect {out_dir.resolve()}/ev_loads.dss
Redirect {out_dir.resolve()}/storage.dss

Redirect {NETWORK_DIR.resolve()}/capacitors.dss

Set voltagebases=[69, 12.47, 0.24]
Calcvoltagebases

Redirect {NETWORK_DIR.resolve()}/coordinates.dss

Set loadmult={load_mult}
Set tolerance=0.0001
Set maxiterations=100

Solve
"""
    (out_dir / "master.dss").write_text(master)


def solve_scenario(master: Path) -> dict[str, Any]:
    """Compile and solve a scenario, return results."""
    # Full restart to clear CWD state from previous compile
    odd.Basic.Start(0)
    odd.Text.Command("ClearAll")
    # Read and execute master.dss line-by-line to control path resolution
    master_abs = master.resolve()
    for line in master_abs.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("!"):
            continue
        odd.Text.Command(line)

    converged = odd.Solution.Converged()
    tp = odd.Circuit.TotalPower()
    losses = odd.Circuit.Losses()

    # Voltage stats
    vmag = np.array(odd.Circuit.AllBusMagPu())
    nonzero = vmag[vmag > 0.01]

    source_kw = abs(tp[0])
    loss_kw = losses[0] / 1000.0

    # Gross load = sum of all Load elements (not net of PV/storage)
    gross_load_kw = 0.0
    idx = odd.Loads.First()
    while idx != 0:
        gross_load_kw += odd.Loads.kW()
        idx = odd.Loads.Next()
    total_kw = gross_load_kw if gross_load_kw > 0 else source_kw

    # Bus voltage details
    names = odd.Circuit.AllBusNames()
    violations = []
    idx = 0
    for i, name in enumerate(names):
        odd.Circuit.SetActiveBusi(i)
        n = odd.Bus.NumNodes()
        phase_v = vmag[idx : idx + n] if idx + n <= len(vmag) else []
        nz = [v for v in phase_v if v > 0.01]
        mean_v = float(np.mean(nz)) if nz else 0.0
        if mean_v > 1.05 or (mean_v < 0.95 and mean_v > 0.01):
            violations.append({
                "bus_name": name,
                "voltage_pu": round(mean_v, 4),
                "violation": "over" if mean_v > 1.05 else "under",
            })
        idx += n

    return {
        "converged": converged,
        "iterations": odd.Solution.Iterations(),
        "total_power_kw": round(total_kw, 2),
        "total_power_kvar": round(abs(tp[1]), 2),
        "total_loss_kw": round(loss_kw, 2),
        "loss_pct": round(loss_kw / total_kw * 100, 2) if total_kw > 0 else 0.0,
        "v_min": round(float(nonzero.min()), 4) if len(nonzero) > 0 else 0.0,
        "v_max": round(float(nonzero.max()), 4) if len(nonzero) > 0 else 0.0,
        "v_mean": round(float(nonzero.mean()), 4) if len(nonzero) > 0 else 0.0,
        "buses_under_095": int((nonzero < 0.95).sum()),
        "buses_over_105": int((nonzero > 1.05).sum()),
        "num_violations": len(violations),
        "violations": violations,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SP&L DER Scenario Analysis")
    parser.add_argument("--scenario-dir", type=Path, default=SCENARIO_DIR)
    args = parser.parse_args()

    scenario_dir = args.scenario_dir.resolve()
    results_base = NETWORK_DIR.resolve() / "results" / "scenarios"
    results_base.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SP&L DER Scenario Analysis")
    print("=" * 60)

    # Load DER data
    solar, ev, batt, feeders = load_der_data()
    xfmr_ids = get_xfmr_buses()
    customers = pd.read_csv(DATA_DIR / "customers.csv")
    n_customers = len(customers[customers["feeder_id"].isin(feeders)])

    print(f"Customers in model: {n_customers}")
    print(f"Base DER: {len(solar)} solar, {len(ev)} EV, {len(batt)} battery")
    print(f"XFMR buses in model: {len(xfmr_ids)}")
    print()

    # Load and run each scenario
    scenario_files = sorted(scenario_dir.glob("*.json"))
    all_results: list[dict[str, Any]] = []

    for sf in scenario_files:
        scenario = json.loads(sf.read_text())
        name = scenario["name"]
        slug = sf.stem

        print(f"--- {name} ---")
        print(f"  Solar: {scenario['solar_penetration_pct']*100:.0f}%, "
              f"EV: {scenario['ev_penetration_pct']*100:.0f}%, "
              f"Battery: {scenario['battery_storage_pct']*100:.0f}%")

        # Scale DER
        solar_s, ev_s, batt_s = scale_der(
            solar, ev, batt, scenario, n_customers, xfmr_ids
        )
        print(f"  Scaled: {len(solar_s)} solar, {len(ev_s)} EV, {len(batt_s)} storage")

        # Write scenario DSS files
        scenario_out = results_base / slug
        write_scenario_dss(solar_s, ev_s, batt_s, scenario, scenario_out)

        # Solve
        result = solve_scenario(scenario_out / "master.dss")
        result["scenario"] = name
        result["slug"] = slug

        print(f"  Converged: {result['converged']}")
        print(f"  Total load: {result['total_power_kw']:.0f} kW")
        print(f"  Losses: {result['total_loss_kw']:.0f} kW ({result['loss_pct']:.1f}%)")
        print(f"  V range: {result['v_min']:.4f} - {result['v_max']:.4f} pu")
        print(f"  Violations: {result['num_violations']} buses")
        print()

        # Save per-scenario results
        violations_df = pd.DataFrame(result.pop("violations"))
        if len(violations_df) > 0:
            violations_df.to_csv(scenario_out / "violations.csv", index=False)

        (scenario_out / "results.json").write_text(json.dumps(result, indent=2))

        all_results.append(result)

    # Comparison summary
    comparison = pd.DataFrame(all_results)
    comparison.to_csv(results_base / "comparison_summary.csv", index=False)

    print("=" * 60)
    print("Scenario Comparison")
    print("=" * 60)
    for _, row in comparison.iterrows():
        print(f"  {row['scenario']:25s} | "
              f"Load: {row['total_power_kw']:8.0f} kW | "
              f"Loss: {row['loss_pct']:4.1f}% | "
              f"V: {row['v_min']:.3f}-{row['v_max']:.3f} | "
              f"Violations: {row['num_violations']}")

    print(f"\nOutput: {results_base}/")


if __name__ == "__main__":
    main()
