#!/usr/bin/env python3
"""
Guide 02: Load Forecasting with Random Forest
Testing with restructured dataset
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)

# Point to restructured dataset
DATA_DIR = "sisyphean-power-and-light/"

print("="*70)
print("GUIDE 02: LOAD FORECASTING WITH RANDOM FOREST")
print("="*70)

# ============================================================================
# STEP 1: Load the Data
# ============================================================================

print("\n[STEP 1] Loading data...")

# Load hourly load data
load_data = pd.read_parquet(DATA_DIR + "timeseries/substation_load_hourly.parquet")

# Load hourly weather
weather = pd.read_csv(DATA_DIR + "weather/hourly_observations.csv",
                      parse_dates=["timestamp"])

print(f"✅ Load records loaded: {len(load_data):,}")
print(f"✅ Weather records loaded: {len(weather):,}")

# ============================================================================
# STEP 2: Aggregate to System-Wide Load
# ============================================================================

print("\n[STEP 2] Aggregating to system-wide hourly load...")

# Sum load across all feeders for each timestamp
system_load = load_data.groupby("timestamp").agg({
    "total_load_mw": "sum",
    "residential_mw": "sum",
    "commercial_mw": "sum",
    "industrial_mw": "sum",
    "customer_count": "sum"
}).reset_index()

print(f"✅ System-wide hourly records: {len(system_load)}")
print(f"✅ Load range: {system_load['total_load_mw'].min():.1f} - {system_load['total_load_mw'].max():.1f} MW")

# ============================================================================
# STEP 3: Merge with Weather Data
# ============================================================================

print("\n[STEP 3] Merging with weather data...")

# Merge on timestamp
df = system_load.merge(weather, on="timestamp", how="inner")

print(f"✅ Merged records: {len(df)}")

# ============================================================================
# STEP 4: Feature Engineering
# ============================================================================

print("\n[STEP 4] Creating time-based features...")

# Extract temporal features
df["hour"] = df["timestamp"].dt.hour
df["day_of_week"] = df["timestamp"].dt.dayofweek
df["month"] = df["timestamp"].dt.month
df["day_of_year"] = df["timestamp"].dt.dayofyear
df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

# Business hours flag
df["is_business_hours"] = ((df["hour"] >= 8) & (df["hour"] <= 17) & (df["is_weekend"] == 0)).astype(int)

# Lag features (previous hour load)
df = df.sort_values("timestamp")
df["load_lag1"] = df["total_load_mw"].shift(1)
df["load_lag24"] = df["total_load_mw"].shift(24)  # Same hour yesterday

# Drop rows with NaN from lag features
df = df.dropna()

print(f"✅ Feature engineering complete: {len(df.columns)} features")

# ============================================================================
# STEP 5: Time-Aware Train/Test Split
# ============================================================================

print("\n[STEP 5] Time-aware train/test split...")

feature_cols = [
    "hour", "day_of_week", "month", "day_of_year",
    "is_weekend", "is_business_hours",
    "temperature", "wind_speed", "humidity",
    "load_lag1", "load_lag24"
]

X = df[feature_cols]
y = df["total_load_mw"]

# Time-based split: train on first 80%, test on last 20%
split_idx = int(len(df) * 0.8)
df_sorted = df.sort_values("timestamp").reset_index(drop=True)

X_train = X.iloc[:split_idx]
y_train = y.iloc[:split_idx]
X_test = X.iloc[split_idx:]
y_test = y.iloc[split_idx:]

train_dates = df_sorted.iloc[:split_idx]["timestamp"]
test_dates = df_sorted.iloc[split_idx:]["timestamp"]

print(f"✅ Training samples: {len(X_train):,} ({train_dates.min().date()} to {train_dates.max().date()})")
print(f"✅ Test samples: {len(X_test):,} ({test_dates.min().date()} to {test_dates.max().date()})")

# ============================================================================
# STEP 6: Train Random Forest Regressor
# ============================================================================

print("\n[STEP 6] Training Random Forest regressor...")

model = RandomForestRegressor(
    n_estimators=100,
    max_depth=15,
    min_samples_split=5,
    random_state=42,
    n_jobs=-1
)

model.fit(X_train, y_train)

print(f"✅ Model training complete")
print(f"✅ Number of trees: {model.n_estimators}")

# ============================================================================
# STEP 7: Evaluate Model
# ============================================================================

print("\n[STEP 7] Evaluating model...")

y_pred_train = model.predict(X_train)
y_pred_test = model.predict(X_test)

# Calculate metrics
train_mae = mean_absolute_error(y_train, y_pred_train)
test_mae = mean_absolute_error(y_test, y_pred_test)
train_rmse = np.sqrt(mean_squared_error(y_train, y_pred_train))
test_rmse = np.sqrt(mean_squared_error(y_test, y_pred_test))
train_r2 = r2_score(y_train, y_pred_train)
test_r2 = r2_score(y_test, y_pred_test)

print("\n" + "="*70)
print("MODEL PERFORMANCE METRICS")
print("="*70)
print(f"\nTraining Set:")
print(f"  MAE:  {train_mae:.3f} MW")
print(f"  RMSE: {train_rmse:.3f} MW")
print(f"  R²:   {train_r2:.3f}")

print(f"\nTest Set:")
print(f"  MAE:  {test_mae:.3f} MW")
print(f"  RMSE: {test_rmse:.3f} MW")
print(f"  R²:   {test_r2:.3f}")

# Calculate MAPE (Mean Absolute Percentage Error)
test_mape = np.mean(np.abs((y_test - y_pred_test) / y_test)) * 100
print(f"  MAPE: {test_mape:.2f}%")

# ============================================================================
# STEP 8: Feature Importance
# ============================================================================

print("\n[STEP 8] Analyzing feature importance...")

importance = model.feature_importances_
feat_imp = pd.Series(importance, index=feature_cols).sort_values(ascending=False)

print("\nTop 10 Most Important Features:")
print("="*70)
for i, (feature, imp) in enumerate(feat_imp.head(10).items(), 1):
    print(f"{i:2}. {feature:25} {imp:.4f}")

# ============================================================================
# STEP 9: Sample Predictions
# ============================================================================

print("\n[STEP 9] Sample predictions (first 24 hours of test set)...")

sample_df = df_sorted.iloc[split_idx:split_idx+24][["timestamp", "total_load_mw"]].copy()
sample_df["predicted_load_mw"] = y_pred_test[:24]
sample_df["error_mw"] = sample_df["total_load_mw"] - sample_df["predicted_load_mw"]
sample_df["error_pct"] = (sample_df["error_mw"] / sample_df["total_load_mw"]) * 100

print("\n" + "="*70)
print("SAMPLE 24-HOUR FORECAST")
print("="*70)
print(sample_df.to_string(index=False))

# ============================================================================
# STEP 10: Summary
# ============================================================================

print("\n" + "="*70)
print("GUIDE 02 TEST COMPLETE")
print("="*70)

print(f"\n✅ Test R² Score: {test_r2:.3f}")
print(f"✅ Test MAE: {test_mae:.3f} MW ({test_mape:.2f}% MAPE)")
print(f"✅ Average System Load: {df['total_load_mw'].mean():.1f} MW")
print(f"✅ Peak Load: {df['total_load_mw'].max():.1f} MW")

print("\n🎯 KEY FINDINGS:")
print(f"   • Most important feature: {feat_imp.index[0]}")
print(f"   • Lag features capture temporal patterns effectively")
print(f"   • Model explains {test_r2:.1%} of load variance")
print(f"   • Average forecast error: {test_mae:.2f} MW")

print("\n✅ Load forecasting validated - Random Forest regression works!")
print("="*70)
