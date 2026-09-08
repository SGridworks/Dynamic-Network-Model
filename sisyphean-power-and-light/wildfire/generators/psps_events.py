#!/usr/bin/env python3
"""Generate synthetic PSPS events for SP&L wildfire notebooks."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
WILDFIRE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FEEDERS_PATH = REPO_ROOT / "demo_data" / "feeders.csv"
DEFAULT_OUTPUT_PATH = WILDFIRE_DIR / "psps_events.parquet"

RATIONALES = (
    "red-flag wind alignment across grassland feeders",
    "high ERC with forecast gusts over WUI laterals",
    "chaparral-pocket exposure and low overnight humidity",
    "asset clearance watchlist plus sustained wind corridor",
)


def generate_psps_events(
    feeders_path: str | Path = DEFAULT_FEEDERS_PATH,
    output_path: str | Path | None = None,
    start_year: int = 2020,
    end_year: int = 2025,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate 3-6 synthetic PSPS events per year."""
    rng = np.random.default_rng(seed)
    feeders = pd.read_csv(feeders_path)
    required = {"feeder_id", "num_customers"}
    missing = required.difference(feeders.columns)
    if missing:
        raise ValueError(f"feeders data missing columns: {sorted(missing)}")

    rows: list[dict[str, object]] = []
    event_num = 1
    for year in range(start_year, end_year + 1):
        for _ in range(int(rng.integers(3, 7))):
            month = int(rng.choice([5, 6, 7, 8, 9, 10], p=[0.08, 0.13, 0.25, 0.24, 0.20, 0.10]))
            day = int(rng.integers(1, 29))
            start_hour = int(rng.integers(10, 21))
            duration = int(rng.integers(8, 38))
            start_time = pd.Timestamp(year=year, month=month, day=day, hour=start_hour)
            end_time = start_time + pd.Timedelta(hours=duration)

            feeder_count = int(rng.integers(2, 8))
            selected = feeders.sample(feeder_count, random_state=int(rng.integers(0, 1_000_000)))
            peak_wind = float(rng.uniform(31, 58))
            peak_erc = float(rng.uniform(66, 98))
            customer_factor = float(rng.uniform(0.55, 0.95))
            customers = int(selected["num_customers"].sum() * customer_factor)

            rows.append(
                {
                    "event_id": f"PSPS-{year}-{event_num:04d}",
                    "start_time": start_time,
                    "end_time": end_time,
                    "feeder_ids": selected["feeder_id"].astype(str).tolist(),
                    "customers_deenergized": customers,
                    "peak_wind_mph": round(peak_wind, 1),
                    "peak_erc": round(peak_erc, 1),
                    "decision_rationale": str(rng.choice(RATIONALES)),
                    "post_event_ignitions_avoided_est": round(float(rng.uniform(0.15, 2.8)), 2),
                }
            )
            event_num += 1

    df = pd.DataFrame(rows).sort_values("start_time").reset_index(drop=True)
    destination = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destination, index=False)
    return df


def load_psps_events(path: str | Path | None = None) -> pd.DataFrame:
    """Load generated PSPS event records."""
    source = Path(path) if path is not None else DEFAULT_OUTPUT_PATH
    if not source.exists():
        raise FileNotFoundError(f"psps_events.parquet not found at {source}")
    return pd.read_parquet(source)


if __name__ == "__main__":
    generated = generate_psps_events()
    print(f"Generated {len(generated)} PSPS event records at {DEFAULT_OUTPUT_PATH}")
