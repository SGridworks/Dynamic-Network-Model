#!/usr/bin/env python3
"""
Guide 05: FLISR (Fault Location, Isolation, Service Restoration)
Testing with restructured dataset
"""

import pandas as pd
import numpy as np

DATA_DIR = "sisyphean-power-and-light/"

print("="*70)
print("GUIDE 05: FLISR SERVICE RESTORATION")
print("="*70)

# ============================================================================
# STEP 1: Load Data
# ============================================================================

print("\n[STEP 1] Loading data...")

switches = pd.read_csv(DATA_DIR + "assets/switches.csv")
crew_dispatch = pd.read_csv(DATA_DIR + "outages/crew_dispatch.csv",
                            parse_dates=["dispatch_time", "arrival_time"])
outages = pd.read_csv(DATA_DIR + "outages/outage_events.csv",
                     parse_dates=["fault_detected", "service_restored"])

# Add a simple ID column to both datasets for merging
crew_dispatch["event_num"] = crew_dispatch.index
outages["event_num"] = outages.index

# Merge crew dispatch with outage events by index
crew_dispatch = crew_dispatch.merge(
    outages[["event_num", "affected_customers", "service_restored"]],
    on="event_num",
    how="left"
)

print(f"✅ Switches loaded: {len(switches):,}")
print(f"✅ Crew dispatches loaded: {len(crew_dispatch):,}")
print(f"✅ Outage events loaded: {len(outages):,}")

# ============================================================================
# STEP 2: Analyze Switch Capabilities
# ============================================================================

print("\n[STEP 2] Analyzing switching infrastructure...")

print(f"\nSwitch type distribution:")
print(switches["switch_type"].value_counts())

print(f"\nSCADA-controlled switch status:")
automated = switches[switches["scada_controlled"] == True]
manual = switches[switches["scada_controlled"] == False]
print(f"  SCADA-Controlled: {len(automated)} ({len(automated)/len(switches):.1%})")
print(f"  Manual:           {len(manual)} ({len(manual)/len(switches):.1%})")

# ============================================================================
# STEP 3: Calculate FLISR Benefits
# ============================================================================

print("\n[STEP 3] Calculating FLISR restoration times...")

# Calculate restoration times
crew_dispatch["response_time_min"] = (
    crew_dispatch["arrival_time"] - crew_dispatch["dispatch_time"]
).dt.total_seconds() / 60

crew_dispatch["restoration_time_min"] = (
    crew_dispatch["service_restored"] - crew_dispatch["arrival_time"]
).dt.total_seconds() / 60

crew_dispatch["total_outage_duration_min"] = (
    crew_dispatch["service_restored"] - crew_dispatch["dispatch_time"]
).dt.total_seconds() / 60

print(f"\nRestoration time statistics:")
print(f"  Mean response time: {crew_dispatch['response_time_min'].mean():.1f} minutes")
print(f"  Mean restoration time: {crew_dispatch['restoration_time_min'].mean():.1f} minutes")
print(f"  Mean total duration: {crew_dispatch['total_outage_duration_min'].mean():.1f} minutes")

# ============================================================================
# STEP 4: Simulate FLISR Performance
# ============================================================================

print("\n[STEP 4] Simulating FLISR automation benefits...")

# FLISR assumptions
FLISR_DETECTION_TIME_MIN = 1  # 1 minute to detect fault
FLISR_ISOLATION_TIME_MIN = 2  # 2 minutes to isolate
FLISR_RESTORATION_TIME_MIN = 3  # 3 minutes to restore via alternate path
FLISR_TOTAL_TIME_MIN = FLISR_DETECTION_TIME_MIN + FLISR_ISOLATION_TIME_MIN + FLISR_RESTORATION_TIME_MIN

# Restorable fraction (70% of outages can be restored via switching)
RESTORABLE_FRACTION = 0.70

# Calculate CMI (Customer Minutes Interrupted)
# Drop rows with missing data
crew_dispatch = crew_dispatch.dropna(subset=["total_outage_duration_min", "affected_customers"])

crew_dispatch["customers"] = crew_dispatch["affected_customers"]
crew_dispatch["duration_min"] = crew_dispatch["total_outage_duration_min"]

# Traditional CMI (all customers wait for crew)
total_cmi_traditional = (crew_dispatch["customers"] * crew_dispatch["duration_min"]).sum()

# FLISR CMI (restorable customers restored quickly, rest wait for crew)
crew_dispatch["restorable_customers"] = crew_dispatch["customers"] * RESTORABLE_FRACTION
crew_dispatch["permanent_fault_customers"] = crew_dispatch["customers"] * (1 - RESTORABLE_FRACTION)

crew_dispatch["cmi_flisr"] = (
    crew_dispatch["restorable_customers"] * FLISR_TOTAL_TIME_MIN +
    crew_dispatch["permanent_fault_customers"] * crew_dispatch["duration_min"]
)

total_cmi_flisr = crew_dispatch["cmi_flisr"].sum()

# Calculate improvement
cmi_reduction = total_cmi_traditional - total_cmi_flisr
cmi_reduction_pct = (cmi_reduction / total_cmi_traditional) * 100

print(f"\n" + "="*70)
print("FLISR BENEFIT ANALYSIS")
print("="*70)
print(f"\nTraditional Restoration:")
print(f"  Total CMI: {total_cmi_traditional:,.0f} customer-minutes")
print(f"  Average duration: {crew_dispatch['duration_min'].mean():.1f} minutes")

print(f"\nWith FLISR Automation:")
print(f"  Total CMI: {total_cmi_flisr:,.0f} customer-minutes")
print(f"  FLISR restoration time: {FLISR_TOTAL_TIME_MIN} minutes")
print(f"  Restorable fraction: {RESTORABLE_FRACTION:.0%}")

print(f"\nImprovement:")
print(f"  CMI Reduction: {cmi_reduction:,.0f} customer-minutes ({cmi_reduction_pct:.1f}%)")
print(f"  Equivalent to: {cmi_reduction/60:,.0f} customer-hours saved")

# ============================================================================
# STEP 5: Top Outages Benefiting from FLISR
# ============================================================================

print("\n[STEP 5] Identifying outages with highest FLISR benefit...")

crew_dispatch["cmi_saved"] = (
    crew_dispatch["restorable_customers"] *
    (crew_dispatch["duration_min"] - FLISR_TOTAL_TIME_MIN)
)

top_benefits = crew_dispatch.nlargest(10, "cmi_saved")

print(f"\nTop 10 Outages with Highest FLISR Benefit:")
print("="*70)
print(top_benefits[["outage_id", "affected_customers", "duration_min",
                    "cmi_saved"]].to_string(index=False))

# ============================================================================
# STEP 6: Summary
# ============================================================================

print("\n" + "="*70)
print("GUIDE 05 TEST COMPLETE")
print("="*70)

print(f"\n✅ Switches analyzed: {len(switches):,}")
print(f"✅ Automated switches: {len(automated):,} ({len(automated)/len(switches):.1%})")
print(f"✅ Outage events analyzed: {len(crew_dispatch):,}")
print(f"✅ CMI reduction with FLISR: {cmi_reduction_pct:.1f}%")

print("\n🎯 KEY FINDINGS:")
print(f"   • FLISR can restore service in {FLISR_TOTAL_TIME_MIN} minutes")
print(f"   • Traditional restoration takes {crew_dispatch['duration_min'].mean():.1f} minutes avg")
print(f"   • CMI savings: {cmi_reduction:,.0f} customer-minutes")
print(f"   • {RESTORABLE_FRACTION:.0%} of outages are restorable via switching")

# Sanity checks
negative_durations = (crew_dispatch["duration_min"] < 0).sum()
print(f"\n[SANITY CHECKS]")
print(f"  Negative-duration events: {negative_durations}")
all_positive = (crew_dispatch["duration_min"] > 0).all()
cmi_positive = total_cmi_traditional > 0
if negative_durations == 0 and all_positive and cmi_positive:
    print("\n✅ FLISR restoration analysis validated!")
else:
    if negative_durations > 0:
        print(f"  ❌ Found {negative_durations} negative-duration events")
    if not all_positive:
        print(f"  ❌ Not all durations are positive")
    if not cmi_positive:
        print(f"  ❌ Total CMI is not positive")
    print("\n❌ FLISR restoration analysis FAILED sanity checks")
print("="*70)
