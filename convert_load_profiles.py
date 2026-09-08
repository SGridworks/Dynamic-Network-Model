#!/usr/bin/env python3
"""Convert sampled 15-minute demand to observed hourly means, without filling gaps."""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent


def convert_profiles(source: pd.DataFrame, feeders: pd.DataFrame) -> pd.DataFrame:
    """Preserve sampled hours, energy, electrical quantities, and registry links."""
    source = source.copy()
    source["timestamp"] = pd.to_datetime(source["timestamp"])
    keys = ["feeder_id", "timestamp"]
    values = ["load_mw", "load_mvar", "voltage_pu"]
    if source.duplicated(keys).any() or not np.isfinite(source[values]).all().all():
        raise ValueError("Duplicate intervals or non-finite source electrical values")
    if not source.timestamp.eq(source.timestamp.dt.floor("15min")).all():
        raise ValueError("Source timestamps must align to 15-minute boundaries")
    source["timestamp"] = source.timestamp.dt.floor("h")
    grouped = source.groupby(keys, sort=True)
    if not grouped.size().eq(4).all():
        raise ValueError("Each sampled hour must contain four 15-minute readings")
    hourly = grouped[values].mean().reset_index()
    hourly = hourly.rename(columns={"load_mw": "total_load_mw"})
    registry = feeders[["feeder_id", "substation_id", "num_customers"]].rename(
        columns={"num_customers": "customer_count"}
    )
    hourly = hourly.merge(registry, on="feeder_id", how="left", validate="many_to_one")
    if hourly[["substation_id", "customer_count"]].isna().any().any():
        raise ValueError("Unknown feeder in source load profiles")
    hourly["customer_count"] = hourly.customer_count.astype(int)
    # Synthetic class allocation retained from the original conversion.
    hour = hourly.timestamp.dt.hour
    conditions = [hour.between(6, 8), hour.between(9, 16), hour.between(17, 21)]
    residential = np.select(conditions, [0.75, 0.60, 0.85], default=0.70)
    commercial = np.select(conditions, [0.18, 0.30, 0.10], default=0.20)
    hourly["residential_mw"] = hourly.total_load_mw * residential
    hourly["commercial_mw"] = hourly.total_load_mw * commercial
    hourly["industrial_mw"] = hourly.total_load_mw * (1 - residential - commercial)
    apparent = np.hypot(hourly.total_load_mw, hourly.load_mvar)
    hourly["power_factor"] = np.divide(
        hourly.total_load_mw, apparent, out=np.ones(len(hourly)), where=apparent != 0
    )
    return hourly


def main() -> None:
    source = pd.read_csv(ROOT / "demo_data/load_profiles.csv.gz", parse_dates=["timestamp"])
    feeders = pd.read_csv(ROOT / "demo_data/feeders.csv")
    hourly = convert_profiles(source, feeders)
    output = ROOT / "sisyphean-power-and-light/timeseries/substation_load_hourly.parquet"
    hourly.to_parquet(output, index=False)
    pd.testing.assert_frame_equal(pd.read_parquet(output), hourly)
    print(f"Saved {len(hourly):,} observed hourly rows across {hourly.feeder_id.nunique()} feeders")


if __name__ == "__main__":
    main()
