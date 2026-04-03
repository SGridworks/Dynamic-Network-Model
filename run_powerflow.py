#!/usr/bin/env python3
"""Run OpenDSS power flow on the SP&L model and export results."""

import argparse
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import opendssdirect as odd
import pandas as pd


def compile_model(model_dir: Path) -> bool:
    """Compile master.dss and return convergence status."""
    odd.Basic.Start(0)
    master = model_dir / "master.dss"
    odd.Text.Command(f"compile {master}")
    converged = odd.Solution.Converged()
    print(f"Circuit: {odd.Circuit.Name()}")
    print(f"Buses: {odd.Circuit.NumBuses()}, Elements: {odd.Circuit.NumCktElements()}")
    print(f"Converged: {converged}, Iterations: {odd.Solution.Iterations()}")
    if not converged:
        print("WARNING: Power flow did not converge")
    return converged


def extract_bus_voltages() -> pd.DataFrame:
    """Extract per-bus voltage magnitudes in per-unit."""
    names = odd.Circuit.AllBusNames()
    vmag_pu = odd.Circuit.AllBusMagPu()

    rows = []
    idx = 0
    for i, name in enumerate(names):
        odd.Circuit.SetActiveBusi(i)
        n_nodes = odd.Bus.NumNodes()
        phase_v = vmag_pu[idx:idx + n_nodes]
        nonzero = [v for v in phase_v if v > 0.01]
        rows.append({
            "bus_name": name,
            "voltage_pu": np.mean(nonzero) if nonzero else 0.0,
            "num_nodes": n_nodes,
            "v_min": min(nonzero) if nonzero else 0.0,
            "v_max": max(nonzero) if nonzero else 0.0,
        })
        idx += n_nodes

    return pd.DataFrame(rows)


def extract_line_flows() -> pd.DataFrame:
    """Extract line power flows and loading."""
    rows = []
    idx = odd.Lines.First()
    while idx != 0:
        name = odd.Lines.Name()
        bus1 = odd.Lines.Bus1()
        bus2 = odd.Lines.Bus2()
        length = odd.Lines.Length()
        phases = odd.Lines.Phases()
        norm_amps = odd.Lines.NormAmps()

        # Set as active element to get powers and currents
        odd.Circuit.SetActiveElement(f"Line.{name}")
        powers = odd.CktElement.Powers()
        # Powers: [P1, Q1, P2, Q2, ...] for each terminal
        # First terminal (sending end): first phases*2 values
        n_vals = phases * 2
        p_kw = sum(powers[i] for i in range(0, min(n_vals, len(powers)), 2))
        q_kvar = sum(powers[i] for i in range(1, min(n_vals, len(powers)), 2))

        # Current magnitudes
        currents = odd.CktElement.CurrentsMagAng()
        # Interleaved [mag, ang, mag, ang, ...] for each phase per terminal
        phase_currents = [currents[i] for i in range(0, min(phases * 2, len(currents)), 2)]
        max_current = max(phase_currents) if phase_currents else 0.0

        loading_pct = (max_current / norm_amps * 100) if norm_amps > 0 else 0.0

        rows.append({
            "line_name": name,
            "bus1": bus1,
            "bus2": bus2,
            "length_mi": length,
            "phases": phases,
            "kw": p_kw,
            "kvar": q_kvar,
            "norm_amps": norm_amps,
            "max_current_amps": max_current,
            "loading_pct": loading_pct,
        })
        idx = odd.Lines.Next()

    return pd.DataFrame(rows)


def extract_transformer_loading() -> pd.DataFrame:
    """Extract transformer loading percentages."""
    rows = []
    idx = odd.Transformers.First()
    while idx != 0:
        name = odd.Transformers.Name()
        kva_rated = odd.Transformers.kVA()

        odd.Circuit.SetActiveElement(f"Transformer.{name}")
        powers = odd.CktElement.Powers()

        # First winding (primary): first 2 values per phase
        n_phases = odd.CktElement.NumPhases()
        n_vals = n_phases * 2
        p_kw = sum(powers[i] for i in range(0, min(n_vals, len(powers)), 2))
        q_kvar = sum(powers[i] for i in range(1, min(n_vals, len(powers)), 2))
        kva_load = math.sqrt(p_kw**2 + q_kvar**2)
        loading_pct = (kva_load / kva_rated * 100) if kva_rated > 0 else 0.0

        rows.append({
            "transformer_name": name,
            "kva_rated": kva_rated,
            "kw_load": abs(p_kw),
            "kvar_load": abs(q_kvar),
            "kva_load": kva_load,
            "loading_pct": loading_pct,
        })
        idx = odd.Transformers.Next()

    return pd.DataFrame(rows)


def extract_system_losses() -> pd.DataFrame:
    """Extract per-element losses for all power delivery elements."""
    rows = []
    idx = odd.Circuit.FirstPDElement()
    while idx != 0:
        name = odd.CktElement.Name()
        losses = odd.CktElement.Losses()  # returns watts
        kw_loss = losses[0] / 1000.0
        kvar_loss = losses[1] / 1000.0

        # Parse element type from name (e.g. "Line.line_EDGE-000001" -> "Line")
        elem_type = name.split(".")[0] if "." in name else name

        if abs(kw_loss) > 0.001 or abs(kvar_loss) > 0.001:
            rows.append({
                "element_name": name,
                "element_type": elem_type,
                "kw_loss": kw_loss,
                "kvar_loss": kvar_loss,
            })
        idx = odd.Circuit.NextPDElement()

    return pd.DataFrame(rows)


def build_summary(voltages_df: pd.DataFrame) -> dict[str, Any]:
    """Build circuit-level summary statistics."""
    tp = odd.Circuit.TotalPower()
    losses = odd.Circuit.Losses()

    v_vals = voltages_df["voltage_pu"]
    nonzero = v_vals[v_vals > 0.01]

    total_kw = abs(tp[0])
    loss_kw = losses[0] / 1000.0

    return {
        "circuit_name": odd.Circuit.Name(),
        "num_buses": odd.Circuit.NumBuses(),
        "num_elements": odd.Circuit.NumCktElements(),
        "num_nodes": odd.Circuit.NumNodes(),
        "converged": odd.Solution.Converged(),
        "iterations": odd.Solution.Iterations(),
        "total_power_kw": round(total_kw, 2),
        "total_power_kvar": round(abs(tp[1]), 2),
        "total_loss_kw": round(loss_kw, 2),
        "total_loss_kvar": round(losses[1] / 1000.0, 2),
        "loss_pct": round(loss_kw / total_kw * 100, 2) if total_kw > 0 else 0.0,
        "v_min": round(float(nonzero.min()), 4) if len(nonzero) > 0 else 0.0,
        "v_max": round(float(nonzero.max()), 4) if len(nonzero) > 0 else 0.0,
        "v_mean": round(float(nonzero.mean()), 4) if len(nonzero) > 0 else 0.0,
        "buses_under_095": int((nonzero < 0.95).sum()),
        "buses_over_105": int((nonzero > 1.05).sum()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpenDSS power flow on SP&L model")
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("sisyphean-power-and-light/network"),
        help="Path to directory containing master.dss",
    )
    args = parser.parse_args()

    # Resolve to absolute paths before OpenDSS compile changes CWD
    model_dir = args.model_dir.resolve()
    results_dir = (model_dir / "results").resolve()
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SP&L Power Flow Analysis")
    print("=" * 60)

    converged = compile_model(model_dir)

    print("\nExtracting bus voltages...")
    voltages = extract_bus_voltages()
    voltages.to_parquet(results_dir / "bus_voltages.parquet", index=False)
    print(f"  {len(voltages)} buses")

    print("Extracting line flows...")
    line_flows = extract_line_flows()
    line_flows.to_parquet(results_dir / "line_flows.parquet", index=False)
    print(f"  {len(line_flows)} lines")

    print("Extracting transformer loading...")
    xfmr_loading = extract_transformer_loading()
    xfmr_loading.to_parquet(results_dir / "transformer_loading.parquet", index=False)
    print(f"  {len(xfmr_loading)} transformers")

    print("Extracting system losses...")
    losses = extract_system_losses()
    losses.to_csv(results_dir / "system_losses.csv", index=False)
    print(f"  {len(losses)} elements with losses")

    print("Building summary...")
    summary = build_summary(voltages)
    (results_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print("\n" + "=" * 60)
    print("Results")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print(f"\nOutput: {results_dir}/")


if __name__ == "__main__":
    main()
