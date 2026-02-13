#!/usr/bin/env python3
"""Convert demo_data/load_profiles.csv to timeseries/substation_load_hourly.parquet"""

import pandas as pd
import numpy as np

# Set random seed
np.random.seed(42)

# Read source data
print("Reading load_profiles.csv...")
df = pd.read_csv("demo_data/load_profiles.csv", parse_dates=["timestamp"])

print(f"Original data: {len(df)} load profile records")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# Rename columns to match guide expectations
df = df.rename(columns={
    "load_mw": "total_load_mw"
})

# ADD MISSING COLUMNS: Customer class breakdowns
# Typical distribution for Phoenix-area utility:
# Residential: 82%
# Commercial: 13%
# Industrial: 5%

# BUT: these percentages vary by hour of day
# Residential peaks in evening, Commercial peaks midday, Industrial is steady

df["hour"] = df["timestamp"].dt.hour

def allocate_load_by_class(row):
    """Allocate total load to customer classes based on hour of day"""
    total = row["total_load_mw"]
    hour = row["hour"]

    # Time-of-day load shapes (as % of total)
    if 6 <= hour < 9:  # Morning
        residential_pct = 0.75
        commercial_pct = 0.18
        industrial_pct = 0.07
    elif 9 <= hour < 17:  # Business hours
        residential_pct = 0.60
        commercial_pct = 0.30
        industrial_pct = 0.10
    elif 17 <= hour < 22:  # Evening peak
        residential_pct = 0.85
        commercial_pct = 0.10
        industrial_pct = 0.05
    else:  # Night/early morning
        residential_pct = 0.70
        commercial_pct = 0.20
        industrial_pct = 0.10

    return pd.Series({
        "residential_mw": total * residential_pct,
        "commercial_mw": total * commercial_pct,
        "industrial_mw": total * industrial_pct
    })

print("\nAllocating load by customer class...")
class_loads = df.apply(allocate_load_by_class, axis=1)
df = pd.concat([df, class_loads], axis=1)

# ADD customer_count (from feeders.csv)
feeders = pd.read_csv("demo_data/feeders.csv")
feeder_customers = feeders[["feeder_id", "num_customers"]].rename(columns={"num_customers": "customer_count"})

df = df.merge(feeder_customers, on="feeder_id", how="left")

# Fill missing customer_count with median
median_customers = df["customer_count"].median()
df["customer_count"] = df["customer_count"].fillna(median_customers).astype(int)

# Select only required columns for guides
output_columns = [
    "timestamp",
    "feeder_id",
    "total_load_mw",
    "residential_mw",
    "commercial_mw",
    "industrial_mw",
    "customer_count"
]

df_output = df[output_columns]

# Sort by timestamp and feeder_id
df_output = df_output.sort_values(["timestamp", "feeder_id"]).reset_index(drop=True)

# Save as Parquet
output_path = "sisyphean-power-and-light/timeseries/substation_load_hourly.parquet"
df_output.to_parquet(output_path, index=False)

print(f"\n✅ Saved {len(df_output)} load records to {output_path}")
print(f"\nDate range: {df_output['timestamp'].min()} to {df_output['timestamp'].max()}")
print(f"Feeders: {df_output['feeder_id'].nunique()}")
print(f"\nLoad summary by class (MW):")
print(df_output[["total_load_mw", "residential_mw", "commercial_mw", "industrial_mw"]].describe())

# Verify file can be read
print("\nVerifying Parquet file...")
test_df = pd.read_parquet(output_path)
print(f"✅ Parquet file readable: {len(test_df)} rows")
