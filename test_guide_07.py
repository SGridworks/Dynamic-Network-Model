#!/usr/bin/env python3
"""
Guide 07: DER Scenario Planning
Testing with restructured dataset
"""

import pandas as pd
import numpy as np
import json

DATA_DIR = "sisyphean-power-and-light/"

print("="*70)
print("GUIDE 07: DER SCENARIO PLANNING")
print("="*70)

# ============================================================================
# STEP 1: Load Scenario Files
# ============================================================================

print("\n[STEP 1] Loading DER scenarios...")

scenarios = []
scenario_files = [
    "baseline_2025.json",
    "high_der_2030.json",
    "ev_adoption_2030.json",
    "extreme_weather.json"
]

for filename in scenario_files:
    with open(DATA_DIR + f"scenarios/{filename}", "r") as f:
        scenario = json.load(f)
        scenarios.append(scenario)
        print(f"✅ Loaded: {scenario['name']}")

# ============================================================================
# STEP 2: Load Feeder Data
# ============================================================================

print("\n[STEP 2] Loading feeder summary...")

feeders = pd.read_csv(DATA_DIR + "network/feeder_summary.csv")

print(f"✅ Feeders loaded: {len(feeders)}")
print(f"✅ Total capacity: {feeders['rated_capacity_mw'].sum():.1f} MW")
print(f"✅ Total customers: {feeders['customer_count'].sum():,}")

# ============================================================================
# STEP 3: Calculate DER Impacts
# ============================================================================

print("\n[STEP 3] Calculating DER impacts for each scenario...")

results = []

for scenario in scenarios:
    # Extract scenario parameters
    solar_pct = scenario.get("solar_penetration_pct", 0)
    ev_pct = scenario.get("ev_penetration_pct", 0)
    battery_pct = scenario.get("battery_storage_pct", 0)
    peak_load_mult = scenario.get("peak_load_multiplier", 1.0)
    solar_derate = scenario.get("solar_derate_factor", 1.0)

    # Calculate per-feeder impacts
    for _, feeder in feeders.iterrows():
        peak_load_mw = feeder["peak_mw"] * peak_load_mult
        customers = feeder["customer_count"]

        # Solar generation (reduces net load during day)
        solar_capacity_mw = customers * solar_pct * 0.005  # 5kW avg per customer
        solar_gen_mw = solar_capacity_mw * 0.75 * solar_derate  # capacity factor at peak, derated for weather

        # EV load (increases load, with 25% coincidence)
        ev_count = customers * ev_pct
        ev_load_mw = ev_count * 0.007 * 0.25  # 7kW charger, 25% coincidence

        # Battery storage (can offset peak)
        battery_capacity_mw = customers * battery_pct * 0.010  # 10kW avg per customer
        battery_discharge_mw = battery_capacity_mw * 0.8  # 80% availability

        # Net load calculation
        net_load_mw = peak_load_mw - solar_gen_mw + ev_load_mw - battery_discharge_mw

        # Hosting capacity check (>95% of capacity = overloaded)
        capacity_mw = feeder["rated_capacity_mw"]
        utilization_pct = (net_load_mw / capacity_mw) * 100
        overloaded = utilization_pct > 95

        results.append({
            "scenario": scenario["name"],
            "year": scenario.get("year", 2025),
            "feeder_id": feeder["feeder_id"],
            "peak_load_mw": peak_load_mw,
            "solar_gen_mw": solar_gen_mw,
            "ev_load_mw": ev_load_mw,
            "battery_discharge_mw": battery_discharge_mw,
            "net_load_mw": net_load_mw,
            "capacity_mw": capacity_mw,
            "utilization_pct": utilization_pct,
            "overloaded": overloaded
        })

results_df = pd.DataFrame(results)

print(f"✅ Scenario impacts calculated: {len(results_df):,} feeder-scenarios")

# ============================================================================
# STEP 4: Analyze Results by Scenario
# ============================================================================

print("\n[STEP 4] Analyzing scenarios...")

print("\n" + "="*70)
print("SCENARIO COMPARISON")
print("="*70)

for scenario_name in results_df["scenario"].unique():
    scenario_data = results_df[results_df["scenario"] == scenario_name]

    print(f"\n{scenario_name}:")
    print(f"  Average Net Load:       {scenario_data['net_load_mw'].mean():.2f} MW")
    print(f"  Total Solar Generation: {scenario_data['solar_gen_mw'].sum():.2f} MW")
    print(f"  Total EV Load:          {scenario_data['ev_load_mw'].sum():.2f} MW")
    print(f"  Total Battery Capacity: {scenario_data['battery_discharge_mw'].sum():.2f} MW")
    print(f"  Average Utilization:    {scenario_data['utilization_pct'].mean():.1f}%")
    print(f"  Overloaded Feeders:     {scenario_data['overloaded'].sum()} / {len(scenario_data)}")

# ============================================================================
# STEP 5: Identify Investment Needs
# ============================================================================

print("\n[STEP 5] Identifying infrastructure investment needs...")

# Find feeders that become overloaded in future scenarios
baseline = results_df[results_df["scenario"] == "Baseline 2025"]
high_der = results_df[results_df["scenario"] == "High DER 2030"]

baseline_overloaded = set(baseline[baseline["overloaded"]]["feeder_id"])
high_der_overloaded = set(high_der[high_der["overloaded"]]["feeder_id"])

new_overloads = high_der_overloaded - baseline_overloaded

print(f"\n✅ Feeders overloaded in baseline: {len(baseline_overloaded)}")
print(f"✅ Feeders overloaded in high DER: {len(high_der_overloaded)}")
print(f"✅ New overloads due to DER growth: {len(new_overloads)}")

if new_overloads:
    print(f"\nFeeders requiring upgrades:")
    upgrade_df = high_der[high_der["feeder_id"].isin(new_overloads)].sort_values(
        "utilization_pct", ascending=False
    )
    print(upgrade_df[["feeder_id", "net_load_mw", "capacity_mw",
                      "utilization_pct"]].head(10).to_string(index=False))

# ============================================================================
# STEP 6: Summary
# ============================================================================

print("\n" + "="*70)
print("GUIDE 07 TEST COMPLETE")
print("="*70)

print(f"\n✅ Scenarios analyzed: {len(scenarios)}")
print(f"✅ Feeders evaluated: {len(feeders)}")
print(f"✅ Total scenario-feeder combinations: {len(results_df):,}")

print("\n🎯 KEY FINDINGS:")
baseline_util = results_df[results_df["scenario"] == "Baseline 2025"]["utilization_pct"].mean()
high_der_util = results_df[results_df["scenario"] == "High DER 2030"]["utilization_pct"].mean()

print(f"   • Baseline 2025 avg utilization: {baseline_util:.1f}%")
print(f"   • High DER 2030 avg utilization: {high_der_util:.1f}%")
print(f"   • DER impact on utilization: {high_der_util - baseline_util:+.1f} pp")
print(f"   • Feeders needing upgrades by 2030: {len(new_overloads)}")

print("\n✅ DER scenario planning validated!")
print("="*70)
