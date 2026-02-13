#!/usr/bin/env python3
"""Convert demo_data/weather_data.csv to weather/hourly_observations.csv"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Set random seed
np.random.seed(42)

# Read source data
print("Reading weather_data.csv...")
df = pd.read_csv("demo_data/weather_data.csv", parse_dates=["timestamp"])

print(f"Original data: {len(df)} weather records")
print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# Rename columns to match guide expectations
df = df.rename(columns={
    "temperature_f": "temperature",
    "humidity_pct": "humidity",
    "wind_speed_mph": "wind_speed"
})

# ADD MISSING PRECIPITATION COLUMN
# Phoenix, AZ climate: Monsoon season (July-September) has most rain
# Annual average: ~8 inches, mostly concentrated in summer

print("\nGenerating precipitation data...")

# Create precipitation based on month and storm patterns
df["month"] = df["timestamp"].dt.month

# Base precipitation rates (inches/hour) by month for Phoenix
monthly_precip_rate = {
    1: 0.003, 2: 0.003, 3: 0.004, 4: 0.001, 5: 0.001, 6: 0.001,
    7: 0.020, 8: 0.025, 9: 0.015,  # Monsoon season
    10: 0.005, 11: 0.003, 12: 0.004
}

df["precipitation"] = df["month"].map(monthly_precip_rate)

# Add storm events (when is_storm=1, increase precipitation dramatically)
if "is_storm" in df.columns:
    storm_mask = df["is_storm"] == 1
    df.loc[storm_mask, "precipitation"] = df.loc[storm_mask, "precipitation"] * np.random.uniform(5, 20, storm_mask.sum())

# Add random variability
df["precipitation"] = df["precipitation"] * np.random.uniform(0.5, 2.0, len(df))

# Most hours have zero precipitation
df.loc[np.random.random(len(df)) > 0.15, "precipitation"] = 0

# Round to 2 decimals
df["precipitation"] = df["precipitation"].round(2)

# EXTEND DATE RANGE to 2020-2025 (guides expect 5 years)
current_start = df["timestamp"].min()
current_end = df["timestamp"].max()

print(f"\nCurrent date range: {current_start} to {current_end}")

# If data doesn't start at 2020-01-01, we need to backfill
target_start = pd.Timestamp("2020-01-01 00:00:00")
target_end = pd.Timestamp("2025-12-31 23:00:00")

if current_start > target_start:
    print(f"Backfilling weather data from {target_start} to {current_start}...")

    # Calculate hours needed
    hours_to_backfill = int((current_start - target_start).total_seconds() / 3600)

    # Replicate patterns from existing data
    backfill_data = []
    for i in range(hours_to_backfill):
        # Sample a random hour from existing data with same month
        target_ts = target_start + pd.Timedelta(hours=i)
        month = target_ts.month

        # Find similar month in existing data
        similar_month_data = df[df["timestamp"].dt.month == month]
        if len(similar_month_data) > 0:
            sample = similar_month_data.sample(n=1).iloc[0].copy()
            sample["timestamp"] = target_ts
            backfill_data.append(sample)

    if backfill_data:
        backfill_df = pd.DataFrame(backfill_data)
        df = pd.concat([backfill_df, df], ignore_index=True)

# If data doesn't extend to 2025-12-31, forward-fill
if current_end < target_end:
    print(f"Forward-filling weather data from {current_end} to {target_end}...")

    hours_to_forwardfill = int((target_end - current_end).total_seconds() / 3600)

    forwardfill_data = []
    for i in range(hours_to_forwardfill):
        target_ts = current_end + pd.Timedelta(hours=i+1)
        month = target_ts.month

        similar_month_data = df[df["timestamp"].dt.month == month]
        if len(similar_month_data) > 0:
            sample = similar_month_data.sample(n=1).iloc[0].copy()
            sample["timestamp"] = target_ts
            forwardfill_data.append(sample)

    if forwardfill_data:
        forwardfill_df = pd.DataFrame(forwardfill_data)
        df = pd.concat([df, forwardfill_df], ignore_index=True)

# Sort by timestamp
df = df.sort_values("timestamp").reset_index(drop=True)

# Remove duplicate timestamps
df = df.drop_duplicates(subset=["timestamp"], keep="first")

print(f"\nExpanded to {len(df)} weather records")
print(f"New date range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# Select only required columns for guides
output_columns = ["timestamp", "temperature", "wind_speed", "precipitation", "humidity"]
df_output = df[output_columns]

# Save to new location
output_path = "sisyphean-power-and-light/weather/hourly_observations.csv"
df_output.to_csv(output_path, index=False)

print(f"\n✅ Saved {len(df_output)} weather records to {output_path}")
print(f"\nSummary statistics:")
print(df_output.describe())
print(f"\nPrecipitation events: {(df_output['precipitation'] > 0).sum()} hours ({(df_output['precipitation'] > 0).sum() / len(df_output) * 100:.1f}%)")
