#!/usr/bin/env python3
"""Create missing CSV files"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

np.random.seed(42)

print("Creating missing CSV files...")

# Read source data
outages = pd.read_csv("sisyphean-power-and-light/outages/outage_events.csv", parse_dates=["fault_detected", "service_restored"])
transformers = pd.read_csv("sisyphean-power-and-light/assets/transformers.csv")
feeders_df = pd.read_csv("demo_data/feeders.csv")
nodes = pd.read_csv("demo_data/network_nodes.csv")
edges = pd.read_csv("demo_data/network_edges.csv")

# ============================================================================
# 1. CREW_DISPATCH.CSV
# ============================================================================

print("\n1. Creating crew_dispatch.csv...")

crew_dispatch = []
for idx, outage in outages.iterrows():
    # Dispatch time: 2-15 minutes after fault detected
    dispatch_time = outage["fault_detected"] + pd.Timedelta(minutes=np.random.randint(2, 16))

    # Arrival time: 15-60 minutes after dispatch
    arrival_time = dispatch_time + pd.Timedelta(minutes=np.random.randint(15, 61))

    crew_dispatch.append({
        "outage_id": f"OUT-{idx+1:05d}",
        "dispatch_time": dispatch_time,
        "arrival_time": arrival_time,
        "crew_id": f"CREW-{np.random.randint(1, 21):02d}",
        "vehicle_id": f"VEH-{np.random.randint(1, 51):03d}"
    })

crew_df = pd.DataFrame(crew_dispatch)
crew_df.to_csv("sisyphean-power-and-light/outages/crew_dispatch.csv", index=False)
print(f"   ✅ Created crew_dispatch.csv ({len(crew_df)} records)")

# ============================================================================
# 2. MAINTENANCE_LOG.CSV
# ============================================================================

print("\n2. Creating maintenance_log.csv...")

maintenance_log = []
for idx, xfmr in transformers.sample(n=min(5000, len(transformers)), random_state=42).iterrows():
    # Generate 1-3 maintenance records per transformer
    num_records = np.random.randint(1, 4)

    for i in range(num_records):
        # Inspection date: random date in past 10 years
        days_ago = np.random.randint(30, 3650)
        inspection_date = datetime.now() - timedelta(days=days_ago)

        maintenance_log.append({
            "transformer_id": xfmr["transformer_id"],
            "inspection_date": inspection_date,
            "work_order_id": f"WO-{len(maintenance_log)+1:06d}",
            "inspection_type": np.random.choice(["routine", "emergency", "preventive"], p=[0.7, 0.1, 0.2]),
            "condition_before": max(1, min(5, xfmr["health_index"] + np.random.randint(-1, 2))),
            "condition_after": xfmr["health_index"]
        })

maint_df = pd.DataFrame(maintenance_log)
maint_df.to_csv("sisyphean-power-and-light/assets/maintenance_log.csv", index=False)
print(f"   ✅ Created maintenance_log.csv ({len(maint_df)} records)")

# ============================================================================
# 3. SWITCHES.CSV
# ============================================================================

print("\n3. Creating switches.csv...")

# Sample edges that will have switches (about 2% of edges)
edges_with_switches = edges.sample(n=min(200, int(len(edges) * 0.02)), random_state=42)

switches = []
for idx, edge in edges_with_switches.iterrows():
    switches.append({
        "switch_id": f"SW-{len(switches)+1:04d}",
        "bus1": f"bus_{edge['from_node_id']}",
        "bus2": f"bus_{edge['to_node_id']}",
        "feeder_id": edge["feeder_id"],
        "scada_controlled": np.random.choice([True, False], p=[0.3, 0.7]),
        "normally_open": np.random.choice([True, False], p=[0.1, 0.9]),
        "switch_type": np.random.choice(["recloser", "sectionalizer", "disconnect"], p=[0.3, 0.3, 0.4])
    })

switches_df = pd.DataFrame(switches)
switches_df.to_csv("sisyphean-power-and-light/assets/switches.csv", index=False)
print(f"   ✅ Created switches.csv ({len(switches_df)} records)")

# ============================================================================
# 4. FEEDER_SUMMARY.CSV
# ============================================================================

print("\n4. Creating feeder_summary.csv...")

feeder_summary = feeders_df[[
    "feeder_id",
    "num_customers",
    "peak_load_mw",
    "rated_capacity_mw"
]].rename(columns={
    "num_customers": "customer_count",
    "peak_load_mw": "peak_mw"
})

feeder_summary.to_csv("sisyphean-power-and-light/network/feeder_summary.csv", index=False)
print(f"   ✅ Created feeder_summary.csv ({len(feeder_summary)} feeders)")

# ============================================================================
# 5. LOADS_SUMMARY.CSV
# ============================================================================

print("\n5. Creating loads_summary.csv...")

# Aggregate customers per bus
# Sample a subset of nodes
nodes_sample = nodes.sample(n=min(1000, len(nodes)), random_state=42)

loads_summary = []
for idx, node in nodes_sample.iterrows():
    # Random customer count per bus (1-50 customers)
    customer_count = np.random.randint(1, 51)

    # Load based on customer count (average 5 kW per customer at peak)
    load_kw = customer_count * np.random.uniform(4, 7)

    loads_summary.append({
        "bus_name": f"bus_{node['node_id']}",
        "feeder_id": node["feeder_id"],
        "customer_count": customer_count,
        "load_kw": round(load_kw, 2)
    })

loads_df = pd.DataFrame(loads_summary)
loads_df.to_csv("sisyphean-power-and-light/network/loads_summary.csv", index=False)
print(f"   ✅ Created loads_summary.csv ({len(loads_df)} buses)")

# ============================================================================
# 6. RELIABILITY_METRICS.CSV
# ============================================================================

print("\n6. Creating reliability_metrics.csv...")

reliability = []
for year in range(2020, 2026):
    reliability.append({
        "year": year,
        "saifi": round(np.random.uniform(0.8, 2.5), 2),  # Interruptions per customer
        "saidi": round(np.random.uniform(90, 180), 1),   # Minutes per customer
        "caidi": round(np.random.uniform(80, 150), 1),   # Minutes per interruption
        "maifi": round(np.random.uniform(2, 8), 2)       # Momentary interruptions
    })

reliability_df = pd.DataFrame(reliability)
reliability_df.to_csv("sisyphean-power-and-light/outages/reliability_metrics.csv", index=False)
print(f"   ✅ Created reliability_metrics.csv ({len(reliability_df)} years)")

print("\n" + "="*60)
print("Missing CSV Files Created")
print("="*60)
