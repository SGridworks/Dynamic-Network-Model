#!/usr/bin/env python3
"""Quasi-Static Time-Series (QSTS) power flow simulation."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import opendssdirect as odd
import pandas as pd

NETWORK_DIR = Path("sisyphean-power-and-light/network")
TS_DIR = Path("sisyphean-power-and-light/timeseries")
DATA_DIR = Path("demo_data")

# Representative weeks: mid-month of each season
SEASON_WEEKS = {
    "winter": ("2024-01-15", 168),
    "spring": ("2024-04-15", 168),
    "summer": ("2024-07-15", 168),
    "fall": ("2024-10-14", 168),
}


def load_feeder_profiles(feeders: list[str]) -> pd.DataFrame:
    """Load hourly load profiles for model feeders, normalized to per-unit."""
    sl = pd.read_parquet(TS_DIR / "substation_load_hourly.parquet")
    sl = sl[sl["feeder_id"].isin(feeders)].copy()
    sl["timestamp"] = pd.to_datetime(sl["timestamp"])

    # Normalize each feeder to its peak (for LoadShape multipliers)
    peaks = sl.groupby("feeder_id")["total_load_mw"].max()
    sl["load_mult"] = sl.apply(
        lambda r: r["total_load_mw"] / peaks[r["feeder_id"]]
        if peaks[r["feeder_id"]] > 0 else 0.0,
        axis=1,
    )
    return sl


def load_solar_profile() -> np.ndarray:
    """Load solar generation profile as hourly multipliers (0-1) for a year.

    Solar profiles CSV has 12 months x 24 hours = 288 rows.
    Expand to 8760 by repeating each month's daily pattern.
    """
    sp = pd.read_csv(DATA_DIR / "solar_profiles.csv")
    sp["generation_pct_of_capacity"] /= 100.0

    # Build 8760 array: each month's 24-hour pattern repeated for days in month
    days_per_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # 2024 leap
    yearly = []
    for m in range(12):
        month_data = sp.iloc[m * 24 : (m + 1) * 24]["generation_pct_of_capacity"].values
        for _ in range(days_per_month[m]):
            yearly.extend(month_data)
    return np.array(yearly[:8760])


def get_season_hours(
    feeder_profiles: pd.DataFrame, season: str, start_date: str, n_hours: int
) -> pd.DataFrame:
    """Extract hours for a representative week."""
    start = pd.Timestamp(start_date)
    end = start + pd.Timedelta(hours=n_hours)
    mask = (feeder_profiles["timestamp"] >= start) & (feeder_profiles["timestamp"] < end)
    return feeder_profiles[mask].copy()


def compile_base(model_dir: Path) -> None:
    """Compile base model."""
    odd.Basic.Start(0)
    odd.Text.Command(f"compile {model_dir / 'master.dss'}")
    if not odd.Solution.Converged():
        print("WARNING: Base case did not converge")


def extract_hourly_snapshot() -> dict[str, Any]:
    """Extract key metrics from current solved state."""
    vmag = np.array(odd.Circuit.AllBusMagPu())
    nonzero = vmag[vmag > 0.01]

    tp = odd.Circuit.TotalPower()
    losses = odd.Circuit.Losses()

    # Gross load
    gross_kw = 0.0
    idx = odd.Loads.First()
    while idx != 0:
        gross_kw += odd.Loads.kW()
        idx = odd.Loads.Next()

    return {
        "source_kw": abs(tp[0]),
        "source_kvar": abs(tp[1]),
        "gross_load_kw": gross_kw,
        "loss_kw": losses[0] / 1000.0,
        "loss_kvar": losses[1] / 1000.0,
        "v_min": float(nonzero.min()) if len(nonzero) > 0 else 0.0,
        "v_max": float(nonzero.max()) if len(nonzero) > 0 else 0.0,
        "v_mean": float(nonzero.mean()) if len(nonzero) > 0 else 0.0,
        "buses_under_095": int((nonzero < 0.95).sum()),
        "buses_over_105": int((nonzero > 1.05).sum()),
        "converged": odd.Solution.Converged(),
    }


def run_qsts_season(
    model_dir: Path,
    feeder_hours: pd.DataFrame,
    solar_year: np.ndarray,
    season: str,
    start_date: str,
    n_hours: int,
) -> list[dict[str, Any]]:
    """Run QSTS for one season's representative week."""
    compile_base(model_dir)

    start_ts = pd.Timestamp(start_date)
    # Hour-of-year for solar profile indexing
    start_hoy = int((start_ts - pd.Timestamp("2024-01-01")).total_seconds() / 3600)

    feeders = feeder_hours["feeder_id"].unique()
    results: list[dict[str, Any]] = []

    for h in range(n_hours):
        ts = start_ts + pd.Timedelta(hours=h)
        hoy = start_hoy + h
        solar_mult = solar_year[hoy] if hoy < len(solar_year) else 0.0

        # Set load multiplier — use average across feeders for this hour
        hour_data = feeder_hours[feeder_hours["timestamp"] == ts]
        if len(hour_data) > 0:
            load_mult = hour_data["load_mult"].mean()
        else:
            load_mult = 0.5  # fallback

        # Apply load multiplier
        odd.Text.Command(f"Set loadmult={load_mult:.4f}")

        # Update PV output via irradiance
        odd.Text.Command(f"BatchEdit PVSystem..* irradiance={solar_mult:.4f}")

        # Solve snapshot at this hour
        odd.Text.Command("Set mode=snapshot")
        odd.Text.Command("Solve")

        snapshot = extract_hourly_snapshot()
        snapshot["timestamp"] = str(ts)
        snapshot["hour"] = h
        snapshot["season"] = season
        snapshot["load_mult"] = round(load_mult, 4)
        snapshot["solar_mult"] = round(solar_mult, 4)
        results.append(snapshot)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="SP&L QSTS Analysis")
    parser.add_argument(
        "--model-dir", type=Path, default=NETWORK_DIR,
    )
    parser.add_argument(
        "--seasons", nargs="*", default=list(SEASON_WEEKS.keys()),
        help="Seasons to simulate (default: all 4)",
    )
    args = parser.parse_args()

    model_dir = args.model_dir.resolve()
    results_dir = model_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("SP&L Quasi-Static Time-Series Analysis")
    print("=" * 60)

    # Load data
    edges = pd.read_csv(DATA_DIR / "network_edges.csv")
    feeders = list(edges["feeder_id"].unique()[:12])

    print("Loading feeder profiles...")
    feeder_profiles = load_feeder_profiles(feeders)
    print(f"  {len(feeder_profiles)} hourly records across {len(feeders)} feeders")

    print("Loading solar profile...")
    solar_year = load_solar_profile()
    print(f"  {len(solar_year)} hourly values")

    total_hours = sum(
        SEASON_WEEKS[s][1] for s in args.seasons if s in SEASON_WEEKS
    )
    print(f"\nSimulating {total_hours} hours ({len(args.seasons)} seasons)")
    print()

    all_results: list[dict[str, Any]] = []

    for season in args.seasons:
        if season not in SEASON_WEEKS:
            print(f"  Unknown season: {season}, skipping")
            continue

        start_date, n_hours = SEASON_WEEKS[season]
        print(f"--- {season.upper()} ({start_date}, {n_hours} hours) ---")

        feeder_hours = get_season_hours(feeder_profiles, season, start_date, n_hours)
        print(f"  Feeder data: {len(feeder_hours)} records")

        season_results = run_qsts_season(
            model_dir, feeder_hours, solar_year, season, start_date, n_hours,
        )
        all_results.extend(season_results)

        # Season summary
        sr = pd.DataFrame(season_results)
        print(f"  V range: {sr['v_min'].min():.4f} - {sr['v_max'].max():.4f} pu")
        print(f"  Load range: {sr['source_kw'].min():.0f} - {sr['source_kw'].max():.0f} kW")
        print(f"  Loss range: {sr['loss_kw'].min():.0f} - {sr['loss_kw'].max():.0f} kW")
        print(f"  Converged: {sr['converged'].sum()}/{len(sr)}")
        print()

    # Save results
    ts_df = pd.DataFrame(all_results)
    ts_df.to_parquet(results_dir / "qsts_timeseries.parquet", index=False)

    # Summary stats
    print("=" * 60)
    print("QSTS Summary")
    print("=" * 60)
    print(f"  Total hours simulated: {len(ts_df)}")
    print(f"  Converged: {ts_df['converged'].sum()}/{len(ts_df)}")
    print(f"  V min (overall): {ts_df['v_min'].min():.4f} pu")
    print(f"  V max (overall): {ts_df['v_max'].max():.4f} pu")
    print(f"  Peak source: {ts_df['source_kw'].max():.0f} kW")
    print(f"  Min source: {ts_df['source_kw'].min():.0f} kW")
    print(f"  Peak losses: {ts_df['loss_kw'].max():.0f} kW")
    print(f"  Total energy (MWh): {ts_df['source_kw'].sum() / 1000:.0f}")
    print(f"  Total loss energy (MWh): {ts_df['loss_kw'].sum() / 1000:.0f}")
    if ts_df["source_kw"].sum() > 0:
        print(f"  Energy loss %: {ts_df['loss_kw'].sum() / ts_df['source_kw'].sum() * 100:.1f}%")

    # Hours with violations
    violation_hours = ts_df[
        (ts_df["buses_under_095"] > 0) | (ts_df["buses_over_105"] > 0)
    ]
    print(f"  Hours with violations: {len(violation_hours)}/{len(ts_df)}")

    print(f"\nOutput: {results_dir / 'qsts_timeseries.parquet'}")


if __name__ == "__main__":
    main()
