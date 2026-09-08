#!/usr/bin/env python3
"""Hosting capacity analysis via iterative power flow."""

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import opendssdirect as odd
import pandas as pd

STEPS = 13  # 0% to 120% in 10% increments


def compile_model(master: Path) -> None:
    """Compile and solve base case."""
    odd.Basic.Start(0)
    odd.Text.Command(f"compile {master}")
    if not odd.Solution.Converged():
        print("WARNING: Base case did not converge")


def get_bus_voltage(bus_name: str) -> float:
    """Get mean voltage magnitude at a bus in per-unit."""
    odd.Circuit.SetActiveBus(bus_name)
    v = odd.Bus.puVmagAngle()
    mags = [v[i] for i in range(0, len(v), 2)]
    nonzero = [m for m in mags if m > 0.01]
    return float(np.mean(nonzero)) if nonzero else 0.0


def get_max_line_loading() -> float:
    """Get maximum loading percentage across all lines."""
    max_load = 0.0
    idx = odd.Lines.First()
    while idx != 0:
        odd.Circuit.SetActiveElement(f"Line.{odd.Lines.Name()}")
        currents = odd.CktElement.CurrentsMagAng()
        phases = odd.Lines.Phases()
        phase_i = [currents[i] for i in range(0, min(phases * 2, len(currents)), 2)]
        max_i = max(phase_i) if phase_i else 0
        norm = odd.Lines.NormAmps()
        if norm > 0:
            max_load = max(max_load, max_i / norm * 100)
        idx = odd.Lines.Next()
    return max_load


def get_existing_pv() -> dict[str, float]:
    """Get existing PV capacity per transformer from the model."""
    pv_map: dict[str, float] = {}
    idx = odd.PVsystems.First()
    while idx != 0:
        name = odd.PVsystems.Name().lower()
        if name.startswith("pv_"):
            xid = name[3:].upper()
            pv_map[xid] = odd.PVsystems.Pmpp()
        idx = odd.PVsystems.Next()
    return pv_map


def operating_limits() -> tuple[bool, float, float]:
    """Check phase voltage and absolute line/transformer thermal limits."""
    volts = np.asarray(odd.Circuit.AllBusMagPu())
    voltage_ok = bool(len(volts) and np.isfinite(volts).all()
                      and (volts >= 0.95).all() and (volts <= 1.05).all())
    loading = get_max_line_loading()
    idx = odd.Transformers.First()
    while idx:
        odd.Circuit.SetActiveElement(f"Transformer.{odd.Transformers.Name()}")
        powers = np.asarray(odd.CktElement.Powers())
        phases = odd.CktElement.NumPhases()
        # Check each winding phase as well as aggregate apparent power.
        per_phase = np.hypot(powers[:2 * phases:2], powers[1:2 * phases:2])
        rating = odd.Transformers.kVA()
        loading = max(loading, float(per_phase.max()) / (rating / phases) * 100)
        idx = odd.Transformers.Next()
    return voltage_ok and loading <= 100 and odd.Solution.Converged(), float(volts.max()), loading


def sweep_transformer(
    master: Path, xid: str, kva_rated: float
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return the last feasible tested injection; never grant HC on an invalid base."""
    import json

    compile_model(master)
    connection = json.loads((master.parent / "model_manifest.json").read_text())["connections"][xid]
    bus_sec = connection["bus"]
    base_v = get_bus_voltage(bus_sec.split(".")[0])
    base_ok, _, base_loading = operating_limits()
    if not base_ok:
        return {
            "transformer_id": xid, "kva_rated": kva_rated,
            "thermal_hc_kw": 0.0, "voltage_hc_kw": 0.0, "hc_kw": 0.0,
            "limiting_factor": "base_case_infeasible", "base_case_feasible": False,
            "base_voltage_pu": base_v, "worst_voltage_pu": base_v,
        }, [{
            "transformer_id": xid, "pv_kw": 0.0, "voltage_pu": base_v,
            "max_loading_pct": base_loading, "converged": odd.Solution.Converged(),
            "feasible": False,
        }]

    odd.Text.Command(
        f"New PVSystem.temp_hc bus1={bus_sec} phases={connection['phases']} "
        f"kV={connection['kv']} kVA=0.01 Pmpp=0 irradiance=1 pf=1"
    )
    curve_points = []
    last_feasible = 0.0
    worst_v = base_v
    limiting = "search_limit"
    for step_kw in np.linspace(0, kva_rated * 1.2, STEPS):
        odd.Text.Command(f"Edit PVSystem.temp_hc Pmpp={step_kw:.8f} kVA={max(step_kw, 0.01):.8f}")
        odd.Solution.Solve()
        feasible, max_voltage, loading = operating_limits()
        v = get_bus_voltage(bus_sec.split(".")[0])
        worst_v = max(worst_v, v)
        curve_points.append({
            "transformer_id": xid, "pv_kw": float(step_kw), "voltage_pu": v,
            "max_loading_pct": loading, "converged": odd.Solution.Converged(),
            "feasible": feasible,
        })
        if not feasible:
            limiting = "voltage" if max_voltage > 1.05 else "thermal_or_voltage"
            break
        last_feasible = float(step_kw)
    return {
        "transformer_id": xid, "kva_rated": kva_rated,
        "thermal_hc_kw": last_feasible, "voltage_hc_kw": last_feasible,
        "hc_kw": last_feasible, "limiting_factor": limiting,
        "base_case_feasible": True, "base_voltage_pu": base_v, "worst_voltage_pu": worst_v,
    }, curve_points

def main() -> None:
    parser = argparse.ArgumentParser(description="SP&L Hosting Capacity Analysis")
    parser.add_argument(
        "--model-dir", type=Path,
        default=Path("sisyphean-power-and-light/network"),
    )
    parser.add_argument(
        "--max-transformers", type=int, default=0,
        help="Limit number of transformers (0=all)",
    )
    args = parser.parse_args()

    model_dir = args.model_dir.resolve()
    master = model_dir / "master.dss"
    results_dir = model_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SP&L Hosting Capacity Analysis")
    print("=" * 60)

    # Get transformer list
    compile_model(master)

    existing_pv = get_existing_pv()

    xfmr_list: list[tuple[str, float]] = []
    idx = odd.Transformers.First()
    while idx != 0:
        name = odd.Transformers.Name()
        kva = odd.Transformers.kVA()
        if name.lower() != "sub_xfmr":
            xfmr_list.append((name.upper(), kva))
        idx = odd.Transformers.Next()

    if args.max_transformers > 0:
        xfmr_list = xfmr_list[: args.max_transformers]

    print(f"Analyzing {len(xfmr_list)} transformers, {STEPS} steps each")
    print(f"Existing PV on {len(existing_pv)} transformers")
    print()

    all_summaries: list[dict[str, Any]] = []
    all_curves: list[dict[str, Any]] = []

    for i, (xid, kva) in enumerate(xfmr_list):
        if (i + 1) % 50 == 0 or i == 0 or i == len(xfmr_list) - 1:
            print(f"  [{i + 1}/{len(xfmr_list)}] {xid} ({kva:.0f} kVA)")

        summary, curves = sweep_transformer(master, xid, kva)
        summary["existing_pv_kw"] = round(existing_pv.get(xid, 0.0), 2)
        all_summaries.append(summary)
        all_curves.extend(curves)

    hc_df = pd.DataFrame(all_summaries)
    hc_df.to_parquet(results_dir / "hosting_capacity_powerflow.parquet", index=False)

    curves_df = pd.DataFrame(all_curves)
    curves_df.to_parquet(results_dir / "hosting_capacity_curves.parquet", index=False)

    print()
    print("=" * 60)
    print("Results")
    print("=" * 60)
    print(f"  Transformers analyzed: {len(hc_df)}")
    print(f"  Mean HC: {hc_df['hc_kw'].mean():.1f} kW")
    print(f"  Median HC: {hc_df['hc_kw'].median():.1f} kW")
    print(f"  Min HC: {hc_df['hc_kw'].min():.1f} kW")
    print(f"  Max HC: {hc_df['hc_kw'].max():.1f} kW")
    vc = hc_df["limiting_factor"].value_counts()
    for factor, count in vc.items():
        print(f"  Limiting factor '{factor}': {count} transformers")
    print(f"\nOutput: {results_dir}/")


if __name__ == "__main__":
    main()
