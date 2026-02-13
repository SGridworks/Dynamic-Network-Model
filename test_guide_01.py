#!/usr/bin/env python3
"""
Guide 01: Outage Prediction with Random Forest
Testing with restructured dataset
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)

# Point to restructured dataset
DATA_DIR = "sisyphean-power-and-light/"

print("="*70)
print("GUIDE 01: OUTAGE PREDICTION WITH RANDOM FOREST")
print("="*70)

# ============================================================================
# STEP 1: Load the Data
# ============================================================================

print("\n[STEP 1] Loading data...")

# Load outage events
outages = pd.read_csv(DATA_DIR + "outages/outage_events.csv",
                      parse_dates=["fault_detected", "service_restored"])

# Load hourly weather
weather = pd.read_csv(DATA_DIR + "weather/hourly_observations.csv",
                      parse_dates=["timestamp"])

# Load transformer asset data
transformers = pd.read_csv(DATA_DIR + "assets/transformers.csv")

print(f"✅ Outage events loaded: {len(outages):,}")
print(f"✅ Weather rows loaded:  {len(weather):,}")
print(f"✅ Transformers loaded:  {len(transformers):,}")

# ============================================================================
# STEP 2: Explore the Data
# ============================================================================

print("\n[STEP 2] Exploring the data...")

print(f"\nCause code distribution:")
print(outages["cause_code"].value_counts())

print(f"\nWeather summary (temperature):")
print(weather["temperature"].describe())

# ============================================================================
# STEP 3: Build Daily Features
# ============================================================================

print("\n[STEP 3] Building daily features...")

# Create a date column from the weather timestamp
weather["date"] = weather["timestamp"].dt.date

# Aggregate weather to daily summaries
daily_weather = weather.groupby("date").agg({
    "temperature":  ["max", "min", "mean"],
    "wind_speed":   ["max", "mean"],
    "precipitation": "sum",
    "humidity":      "mean",
}).reset_index()

# Flatten the multi-level column names
daily_weather.columns = [
    "date", "temp_max", "temp_min", "temp_mean",
    "wind_max", "wind_mean", "precip_total", "humidity_mean"
]

print(f"✅ Daily weather rows: {len(daily_weather)}")

# ============================================================================
# STEP 4: Create the Target Variable
# ============================================================================

print("\n[STEP 4] Creating target variable...")

# Extract the date from each outage event
outages["date"] = outages["fault_detected"].dt.date

# Count outages per day
outage_days = outages.groupby("date").size().reset_index(name="outage_count")

# Merge with daily weather
df = daily_weather.merge(outage_days, on="date", how="left")

# Fill days with no outages as 0
df["outage_count"] = df["outage_count"].fillna(0).astype(int)

# Create the binary target: 1 if any outage, 0 if none
df["outage_flag"] = (df["outage_count"] > 0).astype(int)

print(f"✅ Total days: {len(df)}")
print(f"✅ Days with outages: {df['outage_flag'].sum()}")
print(f"✅ Days without outages: {(df['outage_flag'] == 0).sum()}")

# ============================================================================
# STEP 5: Add Time-Based Features
# ============================================================================

print("\n[STEP 5] Adding time-based features...")

# Convert date column to datetime for feature extraction
df["date"] = pd.to_datetime(df["date"])

# Add calendar features
df["month"]       = df["date"].dt.month
df["day_of_week"] = df["date"].dt.dayofweek    # 0 = Monday, 6 = Sunday
df["is_summer"]   = df["month"].isin([6, 7, 8]).astype(int)

print(f"✅ Features added: month, day_of_week, is_summer")

# ============================================================================
# STEP 6: Split into Training and Test Sets (TIME-BASED)
# ============================================================================

print("\n[STEP 6] Splitting data (time-based)...")

# Define features (X) and target (y)
feature_cols = [
    "temp_max", "temp_min", "temp_mean",
    "wind_max", "wind_mean",
    "precip_total", "humidity_mean",
    "month", "day_of_week", "is_summer"
]

# Sort by date to ensure chronological order
df = df.sort_values("date").reset_index(drop=True)

X = df[feature_cols]
y = df["outage_flag"]

# Time-based split: train on 2020-2023, test on 2024-2025
split_date = pd.Timestamp("2024-01-01")
train_mask = df["date"] < split_date
test_mask = df["date"] >= split_date

X_train, y_train = X[train_mask], y[train_mask]
X_test, y_test = X[test_mask], y[test_mask]

print(f"✅ Training samples: {len(X_train)} (2020-2023)")
print(f"✅ Test samples:     {len(X_test)} (2024-2025)")
print(f"✅ Train outage rate: {y_train.mean():.1%}")
print(f"✅ Test outage rate:  {y_test.mean():.1%}")

# ============================================================================
# STEP 7: Train the Random Forest
# ============================================================================

print("\n[STEP 7] Training Random Forest...")

# Create the model with 200 decision trees
model = RandomForestClassifier(
    n_estimators=200,       # number of trees in the forest
    max_depth=10,           # limit tree depth to prevent overfitting
    random_state=42,        # for reproducible results
    class_weight="balanced" # adjust for imbalanced classes
)

# Train the model
model.fit(X_train, y_train)

print("✅ Model training complete.")
print(f"✅ Number of trees: {model.n_estimators}")
print(f"✅ Features used:   {model.n_features_in_}")

# ============================================================================
# STEP 8: Test the Model
# ============================================================================

print("\n[STEP 8] Testing the model...")

# Make predictions on the test set
y_pred = model.predict(X_test)

# Print a classification report
print("\n" + "="*70)
print("CLASSIFICATION REPORT")
print("="*70)
print(classification_report(y_test, y_pred,
      target_names=["No Outage", "Outage"]))

# ============================================================================
# STEP 9: Feature Importance
# ============================================================================

print("\n[STEP 9] Analyzing feature importance...")

# Get feature importances
importances = model.feature_importances_
feat_imp = pd.Series(importances, index=feature_cols).sort_values(ascending=False)

print("\nTop 5 Most Important Features:")
print("="*70)
for i, (feature, importance) in enumerate(feat_imp.head(5).items(), 1):
    print(f"{i}. {feature:20} {importance:.4f}")

# ============================================================================
# STEP 10: Summary
# ============================================================================

print("\n" + "="*70)
print("GUIDE 01 TEST COMPLETE")
print("="*70)

accuracy = (y_pred == y_test).mean()
print(f"\n✅ Test Accuracy: {accuracy:.1%}")
print(f"✅ Date Range: {df['date'].min().date()} to {df['date'].max().date()}")
print(f"✅ Total Outages in Dataset: {outages['affected_customers'].sum():,} customers affected")

print("\n🎯 KEY FINDINGS:")
print(f"   • Most important feature: {feat_imp.index[0]}")
print(f"   • Outage rate (2020-2023 training): {y_train.mean():.1%}")
print(f"   • Outage rate (2024-2025 test):     {y_test.mean():.1%}")
print(f"   • Model achieves {accuracy:.1%} accuracy on unseen future data")

print("\n✅ Dataset structure validated - Guide 01 runs successfully!")
print("="*70)
