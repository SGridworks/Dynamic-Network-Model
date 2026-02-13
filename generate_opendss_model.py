#!/usr/bin/env python3
"""Generate OpenDSS network model from network_nodes.csv and network_edges.csv"""

import pandas as pd
import numpy as np

print("Generating OpenDSS network model...")

# Read network topology
nodes = pd.read_csv("demo_data/network_nodes.csv")
edges = pd.read_csv("demo_data/network_edges.csv")
transformers_df = pd.read_csv("sisyphean-power-and-light/assets/transformers.csv")

print(f"Nodes: {len(nodes)}")
print(f"Edges: {len(edges)}")
print(f"Transformers: {len(transformers_df)}")

# Create network directory
import os
os.makedirs("sisyphean-power-and-light/network", exist_ok=True)

# ============================================================================
# MASTER.DSS - Main coordination file
# ============================================================================

master_content = """! Sisyphean Power & Light Distribution System Model
! Generated from Dynamic Network Model dataset
! Date: 2026-02-12

Clear

! Define the circuit
New Circuit.SP&L bus1=sourcebus basekV=69 pu=1.00 phases=3 MVAsc3=2000 MVAsc1=2100

! Load auxiliary model files
Redirect lines.dss
Redirect transformers.dss
Redirect loads.dss
Redirect capacitors.dss
Redirect coordinates.dss

! Set solution parameters
Set voltagebases=[69, 12.47, 0.48]
Calcvoltagebases
Set tolerance=0.0001
Set maxiterations=100

! Solve initial power flow
Solve
"""

with open("sisyphean-power-and-light/network/master.dss", "w") as f:
    f.write(master_content)

print("✅ Created master.dss")

# ============================================================================
# LINES.DSS - Distribution lines
# ============================================================================

# Sample a subset of edges for reasonable model size (use first 500 edges per feeder)
# Full model would be 43,826 edges which is too large for beginner guides

feeders = edges["feeder_id"].unique()[:12]  # Use first 12 feeders (F01-F12)
edges_subset = edges[edges["feeder_id"].isin(feeders)].head(1000)

lines_content = "! Distribution Lines\n\n"

# Define line codes based on conductor types
line_codes = {
    "477 ACSR": {"r1": 0.306, "x1": 0.627, "r0": 0.592, "x0": 1.461, "amps": 730},
    "336.4 ACSR": {"r1": 0.306, "x1": 0.626, "r0": 0.592, "x0": 1.463, "amps": 530},
    "#2 ACSR": {"r1": 1.69, "x1": 0.726, "r0": 1.978, "x0": 1.766, "amps": 180},
}

# Add default line code
lines_content += "New LineCode.Default nphases=3 r1=0.306 x1=0.627 r0=0.592 x0=1.461 normamps=730\n\n"

for conductor_type, params in line_codes.items():
    lines_content += f"New LineCode.{conductor_type.replace(' ', '_')} nphases=3 "
    lines_content += f"r1={params['r1']} x1={params['x1']} r0={params['r0']} x0={params['x0']} "
    lines_content += f"normamps={params['amps']}\n"

lines_content += "\n! Line Segments\n\n"

for idx, row in edges_subset.iterrows():
    # Convert node IDs to bus names
    from_bus = f"bus_{row['from_node_id']}"
    to_bus = f"bus_{row['to_node_id']}"

    # Determine phases (assume 3-phase for simplicity)
    phases = 3

    # Get conductor type
    conductor = row.get("conductor_type", "477 ACSR")
    linecode = conductor.replace(" ", "_") if conductor in line_codes else "Default"

    # Get length (convert feet to miles if needed)
    length_ft = row.get("length_ft", 100)
    length_mi = length_ft / 5280

    line_name = f"line_{row['edge_id']}"

    lines_content += f"New Line.{line_name} bus1={from_bus} bus2={to_bus} "
    lines_content += f"linecode={linecode} length={length_mi:.4f} units=mi phases={phases}\n"

with open("sisyphean-power-and-light/network/lines.dss", "w") as f:
    f.write(lines_content)

print(f"✅ Created lines.dss ({len(edges_subset)} line segments)")

# ============================================================================
# TRANSFORMERS.DSS - Distribution transformers
# ============================================================================

# Use a subset of transformers (sample 500 for reasonable model size)
xfmr_subset = transformers_df.sample(n=min(500, len(transformers_df)), random_state=42)

xfmr_content = "! Distribution Transformers\n\n"

for idx, row in xfmr_subset.iterrows():
    xfmr_id = row["transformer_id"]
    kva = row["kva_rating"]

    # Assign to a random bus from our nodes
    # In a real model, this would be properly mapped
    bus_num = np.random.randint(1, 1000)
    bus_name = f"bus_{bus_num}"

    # Standard transformer parameters
    prim_kv = 12.47  # Distribution primary
    sec_v = 0.240    # Secondary voltage (240V)
    pct_imped = 2.5  # Typical for distribution transformers

    xfmr_content += f"New Transformer.{xfmr_id} phases=1 windings=2 buses=[{bus_name} {bus_name}_sec] "
    xfmr_content += f"conns=[wye wye] kvs=[{prim_kv} {sec_v}] kvas=[{kva} {kva}] %imped={pct_imped}\n"

with open("sisyphean-power-and-light/network/transformers.dss", "w") as f:
    f.write(xfmr_content)

print(f"✅ Created transformers.dss ({len(xfmr_subset)} transformers)")

# ============================================================================
# LOADS.DSS - Customer loads
# ============================================================================

loads_content = "! Customer Loads\n\n"

# Create loads at transformer secondary buses
for idx, row in xfmr_subset.iterrows():
    xfmr_id = row["transformer_id"]
    kva = row["kva_rating"]

    # Load is typically 60-80% of transformer capacity at peak
    load_kw = kva * np.random.uniform(0.5, 0.8)
    pf = 0.95  # Power factor

    bus_num = np.random.randint(1, 1000)
    bus_name = f"bus_{bus_num}_sec"

    loads_content += f"New Load.load_{xfmr_id} bus1={bus_name} phases=1 kv=0.240 kw={load_kw:.2f} pf={pf}\n"

with open("sisyphean-power-and-light/network/loads.dss", "w") as f:
    f.write(loads_content)

print(f"✅ Created loads.dss ({len(xfmr_subset)} loads)")

# ============================================================================
# CAPACITORS.DSS - Capacitor banks
# ============================================================================

capacitors_content = "! Capacitor Banks\n\n"

# Add a few capacitor banks on main feeders
for i, feeder in enumerate(feeders[:5]):
    bus_name = f"bus_{i*100 + 50}"
    kvar = np.random.choice([300, 600, 900, 1200])

    capacitors_content += f"New Capacitor.cap_{feeder} bus1={bus_name} phases=3 kvar={kvar} kv=12.47\n"

with open("sisyphean-power-and-light/network/capacitors.dss", "w") as f:
    f.write(capacitors_content)

print(f"✅ Created capacitors.dss ({len(feeders[:5])} capacitors)")

# ============================================================================
# COORDINATES.DSS - Bus coordinates for visualization
# ============================================================================

# Sample nodes for coordinates
nodes_subset = nodes[nodes["feeder_id"].isin(feeders)].head(1000)

coords_content = "! Bus Coordinates\n\n"

for idx, row in nodes_subset.iterrows():
    bus_name = f"bus_{row['node_id']}"
    lat = row["latitude"]
    lon = row["longitude"]

    # OpenDSS uses x,y coordinates (we'll use lat/lon directly)
    coords_content += f"SetBusXY bus={bus_name} x={lon} y={lat}\n"

with open("sisyphean-power-and-light/network/coordinates.dss", "w") as f:
    f.write(coords_content)

print(f"✅ Created coordinates.dss ({len(nodes_subset)} bus coordinates)")

# ============================================================================
# COORDINATES.CSV - Bus coordinates for guides
# ============================================================================

coords_csv = nodes_subset[["node_id", "latitude", "longitude"]].copy()
coords_csv["bus_name"] = "bus_" + coords_csv["node_id"].astype(str)
coords_csv = coords_csv.rename(columns={"longitude": "x", "latitude": "y"})
coords_csv[["bus_name", "x", "y"]].to_csv(
    "sisyphean-power-and-light/network/coordinates.csv",
    index=False
)

print(f"✅ Created coordinates.csv ({len(coords_csv)} coordinates)")

# ============================================================================
# Summary
# ============================================================================

print("\n" + "="*60)
print("OpenDSS Model Generation Complete")
print("="*60)
print(f"  master.dss:       Main coordination file")
print(f"  lines.dss:        {len(edges_subset)} distribution line segments")
print(f"  transformers.dss: {len(xfmr_subset)} distribution transformers")
print(f"  loads.dss:        {len(xfmr_subset)} customer loads")
print(f"  capacitors.dss:   {len(feeders[:5])} capacitor banks")
print(f"  coordinates.dss:  {len(nodes_subset)} bus coordinates")
print(f"  coordinates.csv:  {len(coords_csv)} bus coordinates (CSV)")
print("="*60)

print("\n⚠️  NOTE: This is a simplified model for educational use.")
print("For production power flow, consider using the full network topology.")
print("\nTo test the model:")
print("  python3 -c \"import opendssdirect as dss; dss.Text.Command('Compile sisyphean-power-and-light/network/master.dss'); print(f'Buses: {dss.Circuit.NumBuses()}')\"")
