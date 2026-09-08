#!/usr/bin/env python3
"""Simulate DER growth scenarios through OpenDSS power flow."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import opendssdirect as odd
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "demo_data"
NETWORK_DIR = ROOT / "sisyphean-power-and-light/network"
SCENARIO_DIR = ROOT / "sisyphean-power-and-light/scenarios"


def load_der_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    """Load DER datasets filtered to model feeders."""
    feeders = json.loads((NETWORK_DIR / "model_manifest.json").read_text())["feeders"]

    solar = pd.read_csv(DATA_DIR / "solar_installations.csv")
    solar = solar[(solar["feeder_id"].isin(feeders)) & (solar["status"] == "active")]

    ev = pd.read_csv(DATA_DIR / "ev_chargers.csv")
    ev = ev[(ev["feeder_id"].isin(feeders)) & (ev["status"] == "active")]

    batt = pd.read_csv(DATA_DIR / "battery_installations.csv")
    batt = batt[(batt["feeder_id"].isin(feeders)) & (batt["status"] == "active")]

    return solar, ev, batt, feeders


def get_xfmr_buses() -> set[str]:
    """Get XFMR bus IDs present in the line network."""
    return set(json.loads((NETWORK_DIR / "model_manifest.json").read_text())["connections"])


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
    connections = json.loads((NETWORK_DIR / "model_manifest.json").read_text())["connections"]

    # PVSystems — aggregate by transformer
    pv_lines = ["! Scenario PV Systems", ""]
    if len(solar_s) > 0:
        solar_agg = solar_s.groupby("transformer_id")["capacity_kw"].sum()
        solar_derate = scenario.get("solar_derate_factor", 1.0)
        for xid, total_kw in solar_agg.items():
            kw = total_kw * solar_derate
            connection = connections[xid]
            pv_lines.append(
                f"New PVSystem.pv_{xid} bus1={connection['bus']} phases={connection['phases']} "
                f"kV={connection['kv']} kVA={kw:.1f} Pmpp={kw:.1f} irradiance=1 pf=1"
            )
    (out_dir / "pvsystems.dss").write_text("\n".join(pv_lines) + "\n")

    # EV Chargers — aggregate by transformer as additional loads
    ev_lines = ["! Scenario EV Charging Loads", ""]
    if len(ev_s) > 0:
        ev_agg = ev_s.groupby("transformer_id")["power_kw"].sum()
        for xid, total_kw in ev_agg.items():
            connection = connections[xid]
            ev_lines.append(
                f"New Load.ev_{xid} bus1={connection['bus']} phases={connection['phases']} "
                f"kv={connection['kv']} kw={total_kw:.2f} pf=0.98"
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
            connection = connections[xid]
            stor_lines.append(
                f"New Storage.batt_{xid} bus1={connection['bus']} phases={connection['phases']} "
                f"kV={connection['kv']} "
                f"kWRated={row['total_kw']:.1f} kWhRated={row['total_kwh']:.1f} "
                f"%stored=50 state=idling"
            )
    (out_dir / "storage.dss").write_text("\n".join(stor_lines) + "\n")

    # Scenario master — wraps base model with scenario DER
    load_mult = scenario.get("peak_load_multiplier", 1.0)
    # Reuse the repaired source, winding ratings and voltage bases.
    master_lines = [f"! SP&L Scenario: {scenario['name']}"]
    for line in (NETWORK_DIR / "master.dss").read_text().splitlines():
        if line.strip().lower() == "solve":
            continue
        if line.startswith("Redirect "):
            filename = line.split(maxsplit=1)[1]
            parent = out_dir if filename in {"pvsystems.dss", "storage.dss"} else NETWORK_DIR
            relative = Path(os.path.relpath(parent / filename, out_dir)).as_posix()
            line = f'Redirect "{relative}"'
        master_lines.append(line)
    master_lines.extend([
        'Redirect "ev_loads.dss"',
        f"Set loadmult={load_mult}", "Solve",
    ])
    master = "\n".join(master_lines) + "\n"
    (out_dir / "master.dss").write_text(master)


def solve_scenario(master: Path) -> dict[str, Any]:
    """Compile and solve a scenario, return results."""
    odd.Basic.Start(0)
    odd.Text.Command(f'compile "{master.resolve()}"')

    converged = odd.Solution.Converged()
    tp = odd.Circuit.TotalPower()
    losses = odd.Circuit.Losses()

    # Voltage stats
    vmag = np.array(odd.Circuit.AllBusMagPu())
    nonzero = vmag[vmag > 0.01]

    source_kw = -tp[0]
    loss_kw = losses[0] / 1000.0

    # Gross load = sum of all Load elements (not net of PV/storage)
    gross_load_kw = 0.0
    idx = odd.Loads.First()
    while idx != 0:
        gross_load_kw += odd.Loads.kW() * odd.Solution.LoadMult()
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
        if len(phase_v) and (min(phase_v) < 0.95 or max(phase_v) > 1.05):
            violations.append({
                "bus_name": name,
                "voltage_pu": round(mean_v, 4),
                "violation": "over" if max(phase_v) > 1.05 else "under",
            })
        idx += n

    return {
        "converged": converged,
        "iterations": odd.Solution.Iterations(),
        "total_power_kw": round(total_kw, 2),
        "source_power_kw": round(source_kw, 2),
        "total_power_kvar": round(abs(tp[1]), 2),
        "total_loss_kw": round(loss_kw, 2),
        "loss_pct": round(loss_kw / total_kw * 100, 2) if total_kw > 0 else 0.0,
        "v_min": round(float(nonzero.min()), 4) if len(nonzero) > 0 else 0.0,
        "v_max": round(float(nonzero.max()), 4) if len(nonzero) > 0 else 0.0,
        "v_mean": round(float(nonzero.mean()), 4) if len(nonzero) > 0 else 0.0,
        "phases_under_095": int((vmag < 0.95).sum()),
        "phases_over_105": int((vmag > 1.05).sum()),
        "buses_under_095": sum(v["violation"] == "under" for v in violations),
        "buses_over_105": sum(v["violation"] == "over" for v in violations),
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
    n_customers = len(customers[customers["transformer_id"].isin(xfmr_ids)])

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
        violations_df.reindex(columns=["bus_name", "voltage_pu", "violation"]).to_csv(
            scenario_out / "violations.csv", index=False
        )

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
