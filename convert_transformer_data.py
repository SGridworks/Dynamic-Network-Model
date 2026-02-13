#!/usr/bin/env python3
"""Convert demo_data/transformers.csv to assets/transformers.csv"""

import pandas as pd
import numpy as np

# Set random seed
np.random.seed(42)

# Read source data
print("Reading transformers.csv...")
df = pd.read_csv("demo_data/transformers.csv")

print(f"Original data: {len(df)} transformers")

# Rename columns to match guide expectations
df = df.rename(columns={
    "rated_kva": "kva_rating"
})

# ADD MISSING COLUMNS

# 1. install_year (calculate from age_years, current year = 2025)
df["install_year"] = 2025 - df["age_years"]

# 2. health_index (1-5 scale: 1=Poor, 5=Excellent)
# Correlate with age: newer transformers generally healthier
# Add some randomness for realism
def generate_health_index(age_years):
    """Generate health index based on age with some randomness"""
    if age_years < 5:
        base = 5  # Excellent
    elif age_years < 15:
        base = 4  # Good
    elif age_years < 30:
        base = 3  # Fair
    elif age_years < 45:
        base = 2  # Poor
    else:
        base = 1  # Very Poor

    # Add random variation (±1 level, but keep in 1-5 range)
    variation = np.random.choice([-1, 0, 0, 1], p=[0.2, 0.5, 0.2, 0.1])
    health = base + variation
    return max(1, min(5, health))

df["health_index"] = df["age_years"].apply(generate_health_index)

# 3. condition_score (0-100 scale, correlates with health_index)
# health_index 5 → ~90-100, health_index 1 → ~10-30
health_to_condition = {
    5: (85, 100),
    4: (70, 90),
    3: (50, 75),
    2: (30, 55),
    1: (10, 35)
}

def generate_condition_score(health_index):
    min_score, max_score = health_to_condition[health_index]
    return np.random.randint(min_score, max_score + 1)

df["condition_score"] = df["health_index"].apply(generate_condition_score)

# 4. type (oil or dry)
# Distribution: ~70% oil, ~30% dry (typical for US utilities)
# Larger transformers (>100 kVA) more likely to be oil-filled
def generate_type(kva_rating):
    if kva_rating >= 100:
        return np.random.choice(["oil", "dry"], p=[0.85, 0.15])
    else:
        return np.random.choice(["oil", "dry"], p=[0.60, 0.40])

df["type"] = df["kva_rating"].apply(generate_type)

# Select only required columns for guides
output_columns = [
    "transformer_id",
    "feeder_id",
    "kva_rating",
    "install_year",
    "manufacturer",
    "type",
    "health_index",
    "condition_score",
    "age_years"
]

df_output = df[output_columns]

# Save to new location
output_path = "sisyphean-power-and-light/assets/transformers.csv"
df_output.to_csv(output_path, index=False)

print(f"\n✅ Saved {len(df_output)} transformers to {output_path}")
print(f"\nHealth index distribution:")
print(df_output["health_index"].value_counts().sort_index())
print(f"\nType distribution:")
print(df_output["type"].value_counts())
print(f"\nCondition score summary:")
print(df_output["condition_score"].describe())
print(f"\nAge range: {df_output['age_years'].min()} - {df_output['age_years'].max()} years")
print(f"Install year range: {df_output['install_year'].min()} - {df_output['install_year'].max()}")
