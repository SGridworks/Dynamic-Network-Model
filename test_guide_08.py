#!/usr/bin/env python3
"""
Guide 08: Anomaly Detection with Isolation Forest
Testing with restructured dataset
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)

DATA_DIR = "sisyphean-power-and-light/"

print("="*70)
print("GUIDE 08: ANOMALY DETECTION WITH ISOLATION FOREST")
print("="*70)

# ============================================================================
# STEP 1: Load AMI Data
# ============================================================================

print("\n[STEP 1] Loading AMI 15-minute data...")

ami_data = pd.read_parquet(DATA_DIR + "timeseries/ami_15min_sample.parquet")

print(f"✅ AMI records loaded: {len(ami_data):,}")
print(f"✅ Unique meters: {ami_data['customer_id'].nunique():,}")
print(f"✅ Date range: {ami_data['timestamp'].min()} to {ami_data['timestamp'].max()}")

# ============================================================================
# STEP 2: Feature Engineering for Anomaly Detection
# ============================================================================

print("\n[STEP 2] Engineering anomaly detection features...")

# Extract temporal features
ami_data["hour"] = ami_data["timestamp"].dt.hour
ami_data["day_of_week"] = ami_data["timestamp"].dt.dayofweek
ami_data["is_weekend"] = (ami_data["day_of_week"] >= 5).astype(int)

# Calculate per-meter statistics
meter_stats = ami_data.groupby("customer_id").agg({
    "energy_kwh": ["mean", "std", "max", "min"]
}).reset_index()

meter_stats.columns = ["customer_id", "mean_energy_kwh", "std_energy_kwh", "max_energy_kwh", "min_energy_kwh"]

# Merge stats back to main data
ami_data = ami_data.merge(meter_stats, on="customer_id")

# Create anomaly features
ami_data["z_score"] = (ami_data["energy_kwh"] - ami_data["mean_energy_kwh"]) / (ami_data["std_energy_kwh"] + 1e-6)
ami_data["deviation_from_mean"] = ami_data["energy_kwh"] - ami_data["mean_energy_kwh"]
ami_data["usage_ratio"] = ami_data["energy_kwh"] / (ami_data["mean_energy_kwh"] + 1e-6)

print(f"✅ Feature engineering complete")
print(f"✅ Total features: {len(ami_data.columns)}")

# ============================================================================
# STEP 3: Prepare Features for Isolation Forest
# ============================================================================

print("\n[STEP 3] Preparing features for anomaly detection...")

feature_cols = [
    "energy_kwh",
    "hour",
    "day_of_week",
    "is_weekend",
    "z_score",
    "deviation_from_mean"
]

# Sample data for faster processing (use 10,000 records)
sample_size = min(10000, len(ami_data))
ami_sample = ami_data.sample(n=sample_size, random_state=42)

X = ami_sample[feature_cols]

# Standardize features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

print(f"✅ Sample size for training: {len(ami_sample):,}")
print(f"✅ Features used: {len(feature_cols)}")

# ============================================================================
# STEP 4: Train Isolation Forest
# ============================================================================

print("\n[STEP 4] Training Isolation Forest...")

# contamination = expected proportion of outliers
iso_forest = IsolationForest(
    n_estimators=100,
    contamination=0.05,  # Expect 5% anomalies
    random_state=42,
    n_jobs=-1
)

# Fit and predict
ami_sample["anomaly"] = iso_forest.fit_predict(X_scaled)
ami_sample["anomaly_score"] = iso_forest.score_samples(X_scaled)

# Convert -1/1 to 1/0 (1 = anomaly, 0 = normal)
ami_sample["is_anomaly"] = (ami_sample["anomaly"] == -1).astype(int)

print(f"✅ Isolation Forest trained")
print(f"\nAnomaly distribution:")
print(ami_sample["is_anomaly"].value_counts())

# ============================================================================
# STEP 5: Analyze Detected Anomalies
# ============================================================================

print("\n[STEP 5] Analyzing detected anomalies...")

anomalies = ami_sample[ami_sample["is_anomaly"] == 1]
normal = ami_sample[ami_sample["is_anomaly"] == 0]

print(f"\n✅ Total anomalies detected: {len(anomalies):,} ({len(anomalies)/len(ami_sample):.1%})")
print(f"\n" + "="*70)
print("ANOMALY CHARACTERISTICS")
print("="*70)

print(f"\nNormal readings:")
print(f"  Mean kWh:   {normal['energy_kwh'].mean():.3f}")
print(f"  Std kWh:    {normal['energy_kwh'].std():.3f}")
print(f"  Max kWh:    {normal['energy_kwh'].max():.3f}")

print(f"\nAnomalous readings:")
print(f"  Mean kWh:   {anomalies['energy_kwh'].mean():.3f}")
print(f"  Std kWh:    {anomalies['energy_kwh'].std():.3f}")
print(f"  Max kWh:    {anomalies['energy_kwh'].max():.3f}")

# ============================================================================
# STEP 6: Top Anomalies
# ============================================================================

print("\n[STEP 6] Identifying top anomalies...")

top_anomalies = anomalies.nsmallest(10, "anomaly_score")

print(f"\nTop 10 Most Anomalous Readings:")
print("="*70)
print(top_anomalies[["customer_id", "timestamp", "energy_kwh", "mean_energy_kwh",
                     "z_score", "anomaly_score"]].to_string(index=False))

# ============================================================================
# STEP 7: Temporal Patterns
# ============================================================================

print("\n[STEP 7] Analyzing temporal patterns...")

hourly_anomalies = ami_sample.groupby("hour")["is_anomaly"].sum()

print(f"\nAnomalies by Hour of Day:")
print("="*70)
for hour, count in hourly_anomalies.items():
    bar = "█" * int(count / 5)
    print(f"  {hour:02d}:00  {count:3d}  {bar}")

# ============================================================================
# STEP 8: Summary
# ============================================================================

print("\n" + "="*70)
print("GUIDE 08 TEST COMPLETE")
print("="*70)

print(f"\n✅ AMI records analyzed: {len(ami_sample):,}")
print(f"✅ Anomalies detected: {len(anomalies):,} ({len(anomalies)/len(ami_sample):.1%})")
print(f"✅ Unique meters with anomalies: {anomalies['customer_id'].nunique():,}")

print("\n🎯 KEY FINDINGS:")
print(f"   • Isolation Forest contamination rate: 5%")
print(f"   • Actual anomaly rate detected: {len(anomalies)/len(ami_sample):.1%}")
print(f"   • Anomalies have {anomalies['energy_kwh'].mean()/normal['energy_kwh'].mean():.1f}x higher avg consumption")
print(f"   • Peak anomaly hour: {hourly_anomalies.idxmax():02d}:00")

print("\n✅ Anomaly detection validated!")
print("="*70)
