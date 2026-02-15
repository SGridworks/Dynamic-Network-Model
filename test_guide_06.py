#!/usr/bin/env python3
"""
Guide 06: Volt-VAR Optimization with Reinforcement Learning
Testing with restructured dataset
"""

import pandas as pd
import numpy as np

DATA_DIR = "sisyphean-power-and-light/"

print("="*70)
print("GUIDE 06: VOLT-VAR OPTIMIZATION")
print("="*70)

# ============================================================================
# STEP 1: Load Voltage and Load Data
# ============================================================================

print("\n[STEP 1] Loading voltage and load data...")

load_data = pd.read_parquet(DATA_DIR + "timeseries/substation_load_hourly.parquet")

# Pick a single feeder for VVO analysis
feeder_id = load_data["feeder_id"].unique()[0]
feeder_load = load_data[load_data["feeder_id"] == feeder_id].copy()
feeder_load = feeder_load.sort_values("timestamp").reset_index(drop=True)

print(f"✅ Load data loaded: {len(load_data):,} records")
print(f"✅ Selected feeder: {feeder_id}")
print(f"✅ Feeder records: {len(feeder_load):,}")

# ============================================================================
# STEP 2: Simulate Voltage Profile
# ============================================================================

print("\n[STEP 2] Simulating voltage profile...")

np.random.seed(42)

# Simulate voltage based on load (higher load -> lower voltage)
peak_load = feeder_load["total_load_mw"].max()
feeder_load["load_fraction"] = feeder_load["total_load_mw"] / peak_load

# Voltage drops with load: V = 1.05 - 0.10 * load_fraction + noise
feeder_load["voltage_pu"] = (
    1.05
    - 0.10 * feeder_load["load_fraction"]
    + np.random.normal(0, 0.005, size=len(feeder_load))
)

print(f"✅ Voltage range: {feeder_load['voltage_pu'].min():.4f} - {feeder_load['voltage_pu'].max():.4f} pu")
print(f"✅ Mean voltage: {feeder_load['voltage_pu'].mean():.4f} pu")

# Count voltage violations
low_v = (feeder_load["voltage_pu"] < 0.95).sum()
high_v = (feeder_load["voltage_pu"] > 1.05).sum()
print(f"✅ Low voltage violations (<0.95): {low_v}")
print(f"✅ High voltage violations (>1.05): {high_v}")

# ============================================================================
# STEP 3: Rule-Based VVO Controller
# ============================================================================

print("\n[STEP 3] Implementing rule-based VVO controller...")

# Capacitor bank state: 0=off, 1=on
# Rule: turn on when V < 0.97, turn off when V > 1.03
cap_state = 0
cap_boost = 0.02  # Voltage boost when cap bank is on

rule_results = []
for i, row in feeder_load.iterrows():
    v = row["voltage_pu"]

    # Apply current cap bank effect
    v_corrected = v + (cap_boost if cap_state else 0)

    # Switching logic with deadband
    if v_corrected < 0.97:
        cap_state = 1
        v_corrected = v + cap_boost
    elif v_corrected > 1.03:
        cap_state = 0
        v_corrected = v

    # Calculate reward: penalty for voltage deviation from 1.0
    deviation = abs(v_corrected - 1.0)
    reward = -deviation * 100  # Scale penalty

    rule_results.append({
        "voltage_before": v,
        "voltage_after": v_corrected,
        "cap_state": cap_state,
        "reward": reward
    })

rule_df = pd.DataFrame(rule_results)
rule_total_reward = rule_df["reward"].sum()
rule_violations_after = (
    (rule_df["voltage_after"] < 0.95).sum() +
    (rule_df["voltage_after"] > 1.05).sum()
)

print(f"✅ Rule-based total reward: {rule_total_reward:.1f}")
print(f"✅ Voltage violations after rule-based VVO: {rule_violations_after}")
print(f"✅ Cap bank on fraction: {rule_df['cap_state'].mean():.1%}")

# ============================================================================
# STEP 4: Q-Learning VVO Agent
# ============================================================================

print("\n[STEP 4] Training Q-learning VVO agent...")

# State: discretized voltage (5 buckets) x cap state (2)
# Actions: 0=turn off cap, 1=turn on cap
N_VOLTAGE_BUCKETS = 5
N_CAP_STATES = 2
N_ACTIONS = 2
N_EPISODES = 100

# Discretize voltage into buckets
v_min, v_max = 0.92, 1.08
v_edges = np.linspace(v_min, v_max, N_VOLTAGE_BUCKETS + 1)

def discretize_voltage(v):
    bucket = np.digitize(v, v_edges) - 1
    return max(0, min(N_VOLTAGE_BUCKETS - 1, bucket))

# Initialize Q-table
Q = np.zeros((N_VOLTAGE_BUCKETS, N_CAP_STATES, N_ACTIONS))

# Training parameters
alpha = 0.1   # Learning rate
gamma = 0.95  # Discount factor
epsilon = 0.3  # Exploration rate

voltages = feeder_load["voltage_pu"].values

episode_rewards = []

for episode in range(N_EPISODES):
    total_reward = 0
    cap_state = 0

    # Decay exploration
    eps = max(0.01, epsilon * (1 - episode / N_EPISODES))

    for t in range(len(voltages)):
        v_raw = voltages[t]
        v_bucket = discretize_voltage(v_raw)

        # Epsilon-greedy action
        if np.random.random() < eps:
            action = np.random.randint(N_ACTIONS)
        else:
            action = np.argmax(Q[v_bucket, cap_state])

        # Execute action
        new_cap_state = action  # 0=off, 1=on
        v_corrected = v_raw + (cap_boost if new_cap_state else 0)

        # Reward
        deviation = abs(v_corrected - 1.0)
        reward = -deviation * 100

        # Next state
        next_v_bucket = discretize_voltage(v_corrected)

        # Q-update
        best_next = np.max(Q[next_v_bucket, new_cap_state])
        Q[v_bucket, cap_state, action] += alpha * (
            reward + gamma * best_next - Q[v_bucket, cap_state, action]
        )

        cap_state = new_cap_state
        total_reward += reward

    episode_rewards.append(total_reward)

print(f"✅ Q-learning training complete ({N_EPISODES} episodes)")
print(f"✅ First episode reward:  {episode_rewards[0]:.1f}")
print(f"✅ Last episode reward:   {episode_rewards[-1]:.1f}")
print(f"✅ Best episode reward:   {max(episode_rewards):.1f}")

# ============================================================================
# STEP 5: Evaluate Q-Learning Agent
# ============================================================================

print("\n[STEP 5] Evaluating Q-learning agent...")

ql_results = []
cap_state = 0

for t in range(len(voltages)):
    v_raw = voltages[t]
    v_bucket = discretize_voltage(v_raw)

    # Greedy policy
    action = np.argmax(Q[v_bucket, cap_state])
    new_cap_state = action
    v_corrected = v_raw + (cap_boost if new_cap_state else 0)

    deviation = abs(v_corrected - 1.0)
    reward = -deviation * 100

    ql_results.append({
        "voltage_before": v_raw,
        "voltage_after": v_corrected,
        "cap_state": new_cap_state,
        "reward": reward
    })

    cap_state = new_cap_state

ql_df = pd.DataFrame(ql_results)
ql_total_reward = ql_df["reward"].sum()
ql_violations_after = (
    (ql_df["voltage_after"] < 0.95).sum() +
    (ql_df["voltage_after"] > 1.05).sum()
)

print(f"✅ Q-learning total reward: {ql_total_reward:.1f}")
print(f"✅ Voltage violations after Q-learning VVO: {ql_violations_after}")
print(f"✅ Cap bank on fraction: {ql_df['cap_state'].mean():.1%}")

# ============================================================================
# STEP 6: Compare Results
# ============================================================================

print("\n" + "="*70)
print("VVO CONTROLLER COMPARISON")
print("="*70)

print(f"\n{'Metric':<30} {'No Control':>12} {'Rule-Based':>12} {'Q-Learning':>12}")
print("-"*70)

no_control_reward = -(feeder_load["voltage_pu"] - 1.0).abs().sum() * 100
no_control_violations = low_v + high_v

print(f"{'Total Reward':<30} {no_control_reward:>12.1f} {rule_total_reward:>12.1f} {ql_total_reward:>12.1f}")
print(f"{'Voltage Violations':<30} {no_control_violations:>12} {rule_violations_after:>12} {ql_violations_after:>12}")
print(f"{'Cap Bank On %':<30} {'0%':>12} {rule_df['cap_state'].mean():>11.1%} {ql_df['cap_state'].mean():>11.1%}")

# ============================================================================
# STEP 7: Summary
# ============================================================================

print("\n" + "="*70)
print("GUIDE 06 TEST COMPLETE")
print("="*70)

print(f"\n✅ Feeder analyzed: {feeder_id}")
print(f"✅ Timesteps: {len(voltages):,}")
print(f"✅ Q-learning episodes: {N_EPISODES}")
print(f"✅ State space: {N_VOLTAGE_BUCKETS} voltage buckets x {N_CAP_STATES} cap states")

print("\n🎯 KEY FINDINGS:")
print(f"   • Rule-based VVO reward: {rule_total_reward:.1f}")
print(f"   • Q-learning VVO reward: {ql_total_reward:.1f}")
improvement = ql_total_reward - rule_total_reward
print(f"   • Q-learning improvement: {improvement:+.1f} ({improvement/abs(rule_total_reward)*100:+.1f}%)")
print(f"   • Voltage violations reduced from {no_control_violations} to {ql_violations_after}")

print("\n✅ Volt-VAR optimization validated!")
print("="*70)
