#!/usr/bin/env python3
"""Convert demo_data/outage_history.csv to outages/outage_events.csv"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Set random seed for reproducibility
np.random.seed(42)

# Read source data
print("Reading outage_history.csv...")
df = pd.read_csv("demo_data/outage_history.csv", parse_dates=["start_time", "end_time"])

print(f"Original data: {len(df)} outages")

# Rename columns to match guide expectations
df = df.rename(columns={
    "start_time": "fault_detected",
    "end_time": "service_restored",
    "cause": "cause_code",
    "customers_affected": "affected_customers",
    "equipment_involved": "transformer_id"
})

# Standardize cause codes to match guide expectations (5 categories)
cause_mapping = {
    "equipment failure": "equipment_failure",
    "underground cable fault": "equipment_failure",
    "tree contact": "vegetation",
    "dig-in": "equipment_failure",
    "animal contact": "animal_contact",
    "lightning": "weather",
    "storm damage": "weather",
    "vehicle accident": "equipment_failure",
    "scheduled maintenance": "equipment_failure",
    "overload": "overload",
    "other": "overload",
    "unknown": "equipment_failure"
}
df["cause_code"] = df["cause_code"].replace(cause_mapping)

# Add transformer_id where missing (extract from equipment_involved or generate)
# For now, use a placeholder pattern
mask = df["transformer_id"].isna() | (df["transformer_id"] == "")
df.loc[mask, "transformer_id"] = [f"XFMR-{i:06d}" for i in range(1, mask.sum() + 1)]

# EXPAND DATASET: Generate synthetic outages to reach 3,247+ events
# Strategy: Replicate existing outages with time shifts and minor variations

target_count = 3247
current_count = len(df)
needed = target_count - current_count

if needed > 0:
    print(f"Expanding dataset by {needed} outages to reach {target_count} total...")

    # Create synthetic outages by sampling and time-shifting
    synthetic_outages = []

    for i in range(needed):
        # Sample a random existing outage
        base_outage = df.sample(n=1).iloc[0].copy()

        # Time shift: distribute across 2020-2025
        year_offset = np.random.randint(-4, 2)  # -4 years to +1 year from 2024
        month_offset = np.random.randint(-6, 7)  # Random month variation

        base_outage["fault_detected"] = base_outage["fault_detected"] + pd.DateOffset(years=year_offset, months=month_offset)

        # Recalculate service_restored based on duration
        duration = base_outage["service_restored"] - df.iloc[0]["fault_detected"]
        base_outage["service_restored"] = base_outage["fault_detected"] + duration

        # Add some randomness to customer count (±20%)
        base_outage["affected_customers"] = int(base_outage["affected_customers"] * np.random.uniform(0.8, 1.2))

        # Vary feeder_id occasionally
        if np.random.random() < 0.3:
            feeder_num = np.random.randint(1, 66)
            base_outage["feeder_id"] = f"FDR-{feeder_num:04d}"

        synthetic_outages.append(base_outage)

    # Concatenate original and synthetic
    synthetic_df = pd.DataFrame(synthetic_outages)
    df = pd.concat([df, synthetic_df], ignore_index=True)

    # Sort by fault_detected
    df = df.sort_values("fault_detected").reset_index(drop=True)

    print(f"Expanded to {len(df)} outages")

# Ensure date range spans 2020-2025
print(f"Date range: {df['fault_detected'].min()} to {df['fault_detected'].max()}")

# Select only required columns for guides
output_columns = [
    "fault_detected",
    "service_restored",
    "cause_code",
    "affected_customers",
    "feeder_id",
    "transformer_id"
]

df_output = df[output_columns]

# Save to new location
output_path = "sisyphean-power-and-light/outages/outage_events.csv"
df_output.to_csv(output_path, index=False)

print(f"\n✅ Saved {len(df_output)} outages to {output_path}")
print(f"\nCause code distribution:")
print(df_output["cause_code"].value_counts())
print(f"\nDate range: {df_output['fault_detected'].min()} to {df_output['fault_detected'].max()}")
print(f"Total affected customers: {df_output['affected_customers'].sum():,}")
