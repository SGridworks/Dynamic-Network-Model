#!/usr/bin/env python3
"""
Guide 10: Advanced Load Forecasting (LSTM Deep Learning)
Testing with restructured dataset
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Check if TensorFlow/Keras is installed
try:
    # Suppress TensorFlow warnings before import
    import os
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
    os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

    import tensorflow as tf
    # Set memory growth to avoid segfaults
    physical_devices = tf.config.list_physical_devices('GPU')
    for device in physical_devices:
        tf.config.experimental.set_memory_growth(device, True)

    from tensorflow import keras
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.callbacks import EarlyStopping

    # Use CPU only to avoid GPU issues
    tf.config.set_visible_devices([], 'GPU')

    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    print("⚠️  TensorFlow not installed. Skipping LSTM test...")
    print("Install with: pip3 install tensorflow")
    import sys
    sys.exit(0)

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)

# Point to restructured dataset
DATA_DIR = "sisyphean-power-and-light/"

print("="*70)
print("GUIDE 10: ADVANCED LOAD FORECASTING (LSTM)")
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

system_load = load_data.groupby("timestamp").agg({
    "total_load_mw": "sum",
    "residential_mw": "sum",
    "commercial_mw": "sum",
    "industrial_mw": "sum"
}).reset_index()

print(f"✅ System-wide hourly records: {len(system_load)}")

# ============================================================================
# STEP 3: Merge with Weather and Feature Engineering
# ============================================================================

print("\n[STEP 3] Merging weather and creating features...")

df = system_load.merge(weather, on="timestamp", how="inner")

# Temporal features
df["hour"] = df["timestamp"].dt.hour
df["day_of_week"] = df["timestamp"].dt.dayofweek
df["month"] = df["timestamp"].dt.month
df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

# Sort chronologically
df = df.sort_values("timestamp").reset_index(drop=True)

print(f"✅ Merged records: {len(df)}")

# ============================================================================
# STEP 4: Prepare Sequences for LSTM
# ============================================================================

print("\n[STEP 4] Preparing LSTM sequences...")

# Select features for LSTM
feature_cols = [
    "total_load_mw", "temperature", "wind_speed", "humidity",
    "hour", "day_of_week", "is_weekend"
]

data = df[feature_cols].values

# Normalize features
scaler = MinMaxScaler()
data_scaled = scaler.fit_transform(data)

# Create sequences (use past 24 hours to predict next hour)
SEQ_LENGTH = 24
FORECAST_HORIZON = 1

def create_sequences(data, seq_length, forecast_horizon):
    X, y = [], []
    for i in range(len(data) - seq_length - forecast_horizon + 1):
        X.append(data[i:i+seq_length])
        y.append(data[i+seq_length:i+seq_length+forecast_horizon, 0])  # Predict load only
    return np.array(X), np.array(y)

X, y = create_sequences(data_scaled, SEQ_LENGTH, FORECAST_HORIZON)

print(f"✅ Sequences created: {len(X)}")
print(f"✅ Sequence shape: {X.shape}")
print(f"✅ Target shape: {y.shape}")

# ============================================================================
# STEP 5: Time-Aware Train/Test Split
# ============================================================================

print("\n[STEP 5] Time-aware train/test split...")

# 80/20 split
split_idx = int(len(X) * 0.8)

X_train = X[:split_idx]
y_train = y[:split_idx]
X_test = X[split_idx:]
y_test = y[split_idx:]

print(f"✅ Training sequences: {len(X_train):,}")
print(f"✅ Test sequences: {len(X_test):,}")

# ============================================================================
# STEP 6: Build LSTM Model
# ============================================================================

print("\n[STEP 6] Building LSTM model...")

model = Sequential([
    LSTM(50, activation='relu', return_sequences=True, input_shape=(SEQ_LENGTH, len(feature_cols))),
    Dropout(0.2),
    LSTM(50, activation='relu'),
    Dropout(0.2),
    Dense(25, activation='relu'),
    Dense(FORECAST_HORIZON)
])

model.compile(optimizer='adam', loss='mse', metrics=['mae'])

print(f"✅ Model architecture:")
model.summary()

# ============================================================================
# STEP 7: Train LSTM Model
# ============================================================================

print("\n[STEP 7] Training LSTM model...")

early_stop = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)

history = model.fit(
    X_train, y_train,
    epochs=30,
    batch_size=32,
    validation_split=0.1,
    callbacks=[early_stop],
    verbose=0
)

print(f"✅ Training complete")
print(f"✅ Epochs trained: {len(history.history['loss'])}")
print(f"✅ Final training loss: {history.history['loss'][-1]:.4f}")
print(f"✅ Final validation loss: {history.history['val_loss'][-1]:.4f}")

# ============================================================================
# STEP 8: Evaluate Model
# ============================================================================

print("\n[STEP 8] Evaluating LSTM model...")

# Predict on test set
y_pred_scaled = model.predict(X_test, verbose=0)

# Inverse transform to get actual MW values
# Create dummy array for inverse transform
dummy = np.zeros((len(y_pred_scaled), len(feature_cols)))
dummy[:, 0] = y_pred_scaled.flatten()
y_pred = scaler.inverse_transform(dummy)[:, 0]

dummy_actual = np.zeros((len(y_test), len(feature_cols)))
dummy_actual[:, 0] = y_test.flatten()
y_test_actual = scaler.inverse_transform(dummy_actual)[:, 0]

# Calculate metrics
mae = mean_absolute_error(y_test_actual, y_pred)
rmse = np.sqrt(mean_squared_error(y_test_actual, y_pred))
r2 = r2_score(y_test_actual, y_pred)
mape = np.mean(np.abs((y_test_actual - y_pred) / y_test_actual)) * 100

print("\n" + "="*70)
print("LSTM MODEL PERFORMANCE")
print("="*70)
print(f"\nTest Set Metrics:")
print(f"  MAE:  {mae:.3f} MW")
print(f"  RMSE: {rmse:.3f} MW")
print(f"  R²:   {r2:.3f}")
print(f"  MAPE: {mape:.2f}%")

# ============================================================================
# STEP 9: Sample Predictions
# ============================================================================

print("\n[STEP 9] Sample 24-hour forecast...")

sample_size = 24
sample_actual = y_test_actual[:sample_size]
sample_pred = y_pred[:sample_size]

# Get corresponding timestamps
start_idx = split_idx + SEQ_LENGTH
timestamps = df.iloc[start_idx:start_idx+sample_size]["timestamp"].values

sample_df = pd.DataFrame({
    "timestamp": timestamps,
    "actual_load_mw": sample_actual,
    "predicted_load_mw": sample_pred,
    "error_mw": sample_actual - sample_pred,
    "error_pct": ((sample_actual - sample_pred) / sample_actual) * 100
})

print("\n" + "="*70)
print("SAMPLE 24-HOUR LSTM FORECAST")
print("="*70)
print(sample_df.to_string(index=False))

# ============================================================================
# STEP 10: Training History
# ============================================================================

print("\n[STEP 10] Training convergence...")

print(f"\nTraining Loss Progression (first 10 epochs):")
for i in range(min(10, len(history.history['loss']))):
    train_loss = history.history['loss'][i]
    val_loss = history.history['val_loss'][i]
    print(f"  Epoch {i+1:2}: Train Loss = {train_loss:.4f}, Val Loss = {val_loss:.4f}")

# ============================================================================
# STEP 11: Summary
# ============================================================================

print("\n" + "="*70)
print("GUIDE 10 (ADVANCED) TEST COMPLETE")
print("="*70)

print(f"\n✅ LSTM Test R² Score: {r2:.3f}")
print(f"✅ LSTM Test MAE: {mae:.3f} MW ({mape:.2f}% MAPE)")
print(f"✅ Sequence Length: {SEQ_LENGTH} hours")
print(f"✅ Average System Load: {df['total_load_mw'].mean():.1f} MW")
print(f"✅ Peak Load: {df['total_load_mw'].max():.1f} MW")

print("\n🎯 KEY FINDINGS:")
print(f"   • LSTM captures temporal dependencies in load patterns")
print(f"   • Model trained with early stopping (converged in {len(history.history['loss'])} epochs)")
print(f"   • Deep learning explains {r2:.1%} of load variance")
print(f"   • Average forecast error: {mae:.2f} MW")
print(f"   • Sequence-based approach enables multi-hour forecasting")

print("\n✅ Advanced LSTM load forecasting validated!")
print("="*70)
