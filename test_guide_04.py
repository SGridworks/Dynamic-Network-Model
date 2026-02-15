#!/usr/bin/env python3
"""
Guide 04: Predictive Maintenance with Random Forest
Testing with restructured dataset
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)

DATA_DIR = "sisyphean-power-and-light/"

print("="*70)
print("GUIDE 04: PREDICTIVE MAINTENANCE WITH RANDOM FOREST")
print("="*70)

# ============================================================================
# STEP 1: Load the Data
# ============================================================================

print("\n[STEP 1] Loading data...")

transformers = pd.read_csv(DATA_DIR + "assets/transformers.csv")
maintenance = pd.read_csv(DATA_DIR + "assets/maintenance_log.csv",
                          parse_dates=["inspection_date"])

print(f"✅ Transformers loaded: {len(transformers):,}")
print(f"✅ Maintenance records: {len(maintenance):,}")

# ============================================================================
# STEP 2: Create Target Variable (Failure Risk)
# ============================================================================

print("\n[STEP 2] Creating failure risk target...")

# Define high-risk transformers based on health_index
# health_index: 1=Poor, 2=Fair, 3=Good, 4=Very Good, 5=Excellent
transformers["failure_risk"] = (transformers["health_index"] <= 2).astype(int)

print(f"\nFailure risk distribution:")
print(transformers["failure_risk"].value_counts())
print(f"\nHigh-risk rate: {transformers['failure_risk'].mean():.1%}")

# ============================================================================
# STEP 3: Feature Engineering
# ============================================================================

print("\n[STEP 3] Engineering features...")

# Get latest inspection for each transformer
latest_inspection = maintenance.sort_values("inspection_date").groupby("transformer_id").last()

# Merge with transformer data
df = transformers.merge(latest_inspection, left_on="transformer_id",
                       right_index=True, how="left")

# Fill missing inspections with defaults
df["condition_after"] = df["condition_after"].fillna(3)  # Default to "Good" condition
df["condition_before"] = df["condition_before"].fillna(3)

# Encode categorical variables
df["type_encoded"] = (df["type"] == "oil").astype(int)

# Create condition change feature
df["condition_degraded"] = (df["condition_after"] < df["condition_before"]).astype(int)
df["condition_improved"] = (df["condition_after"] > df["condition_before"]).astype(int)

# Create age buckets
df["age_bucket"] = pd.cut(df["age_years"], bins=[0, 10, 20, 30, 50],
                          labels=["0-10", "10-20", "20-30", "30+"])

print(f"✅ Feature engineering complete")
print(f"✅ Total features: {len(df.columns)}")

# ============================================================================
# STEP 4: Prepare Features
# ============================================================================

print("\n[STEP 4] Preparing features...")

feature_cols = [
    "age_years",
    "kva_rating",
    "condition_score",
    "type_encoded",
    "condition_after",
    "condition_degraded"
]

# Remove rows with missing data
df_clean = df.dropna(subset=feature_cols + ["failure_risk"])

X = df_clean[feature_cols]
y = df_clean["failure_risk"]

print(f"✅ Clean samples: {len(df_clean):,}")
print(f"✅ Features: {len(feature_cols)}")

# ============================================================================
# STEP 5: Train/Test Split
# ============================================================================

print("\n[STEP 5] Train/test split...")

from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"✅ Training samples: {len(X_train):,}")
print(f"✅ Test samples: {len(X_test):,}")
print(f"✅ Train failure rate: {y_train.mean():.1%}")
print(f"✅ Test failure rate: {y_test.mean():.1%}")

# ============================================================================
# STEP 6: Train Random Forest
# ============================================================================

print("\n[STEP 6] Training Random Forest...")

model = RandomForestClassifier(
    n_estimators=100,
    max_depth=8,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)

print(f"✅ Model training complete")

# ============================================================================
# STEP 7: Evaluate Model
# ============================================================================

print("\n[STEP 7] Evaluating model...")

y_pred = model.predict(X_test)
y_pred_proba = model.predict_proba(X_test)[:, 1]

print("\n" + "="*70)
print("CLASSIFICATION REPORT")
print("="*70)
print(classification_report(y_test, y_pred,
      target_names=["Low Risk", "High Risk"]))

auc_score = roc_auc_score(y_test, y_pred_proba)
print(f"\nROC AUC Score: {auc_score:.3f}")

# ============================================================================
# STEP 8: Feature Importance
# ============================================================================

print("\n[STEP 8] Feature importance...")

importance = model.feature_importances_
feat_imp = pd.Series(importance, index=feature_cols).sort_values(ascending=False)

print("\nTop Features:")
print("="*70)
for i, (feature, imp) in enumerate(feat_imp.items(), 1):
    print(f"{i}. {feature:25} {imp:.4f}")

# ============================================================================
# STEP 9: High-Risk Asset Identification
# ============================================================================

print("\n[STEP 9] Identifying high-risk assets...")

# Predict on all transformers
df_all_features = df[feature_cols].fillna(0)
df["predicted_risk_score"] = model.predict_proba(df_all_features)[:, 1]

high_risk_assets = df[df["predicted_risk_score"] > 0.7].sort_values(
    "predicted_risk_score", ascending=False
)

print(f"\n✅ High-risk transformers identified: {len(high_risk_assets)}")
print(f"\nTop 10 Highest-Risk Transformers:")
print("="*70)
print(high_risk_assets[["transformer_id", "age_years", "condition_score",
                        "health_index", "predicted_risk_score"]].head(10).to_string(index=False))

# ============================================================================
# STEP 10: Summary
# ============================================================================

print("\n" + "="*70)
print("GUIDE 04 TEST COMPLETE")
print("="*70)

accuracy = (y_pred == y_test).mean()
print(f"\n✅ Test Accuracy: {accuracy:.1%}")
print(f"✅ ROC AUC: {auc_score:.3f}")
print(f"✅ High-risk assets identified: {len(high_risk_assets):,}")
print(f"✅ Total transformers analyzed: {len(transformers):,}")

print("\n🎯 KEY FINDINGS:")
print(f"   • Most important feature: {feat_imp.index[0]}")
print(f"   • {len(high_risk_assets)} transformers need priority maintenance")
print(f"   • Model achieves {auc_score:.1%} AUC for risk discrimination")

print("\n✅ Predictive maintenance validated!")
print("="*70)
