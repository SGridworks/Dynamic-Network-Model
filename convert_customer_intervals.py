#!/usr/bin/env python3
"""Rebuild the V2 AMI sample from the current V1 customer interval corpus."""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent


def main() -> None:
    start, end = pd.Timestamp("2024-07-15"), pd.Timestamp("2024-07-22")
    chunks = pd.read_csv(ROOT / "demo_data/customer_interval_data.csv.gz",
                         parse_dates=["timestamp"], chunksize=250_000)
    sample = pd.concat([c[c.timestamp.ge(start) & c.timestamp.lt(end)] for c in chunks],
                       ignore_index=True)
    customers = pd.read_csv(ROOT / "demo_data/customers.csv").set_index("customer_id")
    for column in ("transformer_id", "feeder_id", "substation_id", "customer_type"):
        expected = sample.customer_id.map(customers[column])
        if expected.isna().any() or not sample[column].eq(expected).all():
            raise ValueError(f"Source AMI disagrees with customer registry: {column}")
    if sample.empty or sample.duplicated(["customer_id", "timestamp"]).any():
        raise ValueError("Empty or duplicate AMI sample")
    path = ROOT / "sisyphean-power-and-light/timeseries/ami_15min_sample.parquet"
    sample.to_parquet(path, index=False)
    pd.testing.assert_frame_equal(pd.read_parquet(path), sample)
    print(f"Saved {len(sample):,} intervals for {sample.customer_id.nunique()} customers")


if __name__ == "__main__":
    main()
