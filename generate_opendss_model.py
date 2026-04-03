#!/usr/bin/env python3
"""Generate OpenDSS model from SP&L network data."""

from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MAX_FEEDERS = 12
MAX_LINES = 1000
DATA_DIR = Path("demo_data")
ASSET_DIR = Path("sisyphean-power-and-light/assets")
OUT_DIR = Path("sisyphean-power-and-light/network")

LINE_CODES: dict[str, dict[str, float]] = {
    "795 ACSR":   {"r1": 0.1198, "x1": 0.355,  "normamps": 700},
    "477 ACSR":   {"r1": 0.306,  "x1": 0.627,  "normamps": 730},
    "336 ACSR":   {"r1": 0.306,  "x1": 0.626,  "normamps": 530},
    "#2 ACSR":    {"r1": 1.69,   "x1": 0.726,  "normamps": 180},
    "#4 CU":      {"r1": 2.55,   "x1": 0.777,  "normamps": 135},
    "1/0 AL":     {"r1": 1.12,   "x1": 0.714,  "normamps": 200},
    "4/0 AL":     {"r1": 0.447,  "x1": 0.647,  "normamps": 340},
    "397.5 AAC":  {"r1": 0.259,  "x1": 0.612,  "normamps": 590},
}
DEFAULT_CODE = "477_ACSR"

rng = np.random.default_rng(seed=42)


def sanitize_code(name: str) -> str:
    return name.replace(" ", "_").replace(".", "p").replace("/", "_")


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print("Loading SP&L network data...")
nodes = pd.read_csv(DATA_DIR / "network_nodes.csv")
edges = pd.read_csv(DATA_DIR / "network_edges.csv")
transformers = pd.read_csv(ASSET_DIR / "transformers.csv")
solar = pd.read_csv(DATA_DIR / "solar_installations.csv")
battery = pd.read_csv(DATA_DIR / "battery_installations.csv")

feeders = edges["feeder_id"].unique()[:MAX_FEEDERS]
edges_sub = edges[edges["feeder_id"].isin(feeders)].head(MAX_LINES)

print(f"  Feeders: {len(feeders)}, Lines: {len(edges_sub)}, "
      f"Transformers: {len(transformers)}, Solar: {len(solar)}, Battery: {len(battery)}")

OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. lines.dss -- line codes + line segments
# ---------------------------------------------------------------------------
line_buses: set[str] = set()
xfmr_bus_ids: set[str] = set()

lines: list[str] = ["! SP&L Distribution Lines", ""]

for raw_name, params in LINE_CODES.items():
    code = sanitize_code(raw_name)
    lines.append(
        f"New LineCode.{code} nphases=3 r1={params['r1']} x1={params['x1']} "
        f"normamps={int(params['normamps'])}"
    )
lines.append("")

for _, row in edges_sub.iterrows():
    from_bus = f"bus_{row['from_node_id']}"
    to_bus = f"bus_{row['to_node_id']}"
    line_buses.update((from_bus, to_bus))

    to_id = str(row["to_node_id"])
    if to_id.startswith("XFMR"):
        xfmr_bus_ids.add(to_id)

    raw_cond = str(row["conductor_type"])
    code = sanitize_code(raw_cond) if raw_cond in LINE_CODES else DEFAULT_CODE
    length_mi = row["length_ft"] / 5280 if pd.notna(row["length_ft"]) else 0.01
    nphases = int(row["num_phases"]) if pd.notna(row.get("num_phases")) else 3

    lines.append(
        f"New Line.line_{row['edge_id']} bus1={from_bus} bus2={to_bus} "
        f"linecode={code} length={length_mi:.4f} units=mi phases={nphases}"
    )

(OUT_DIR / "lines.dss").write_text("\n".join(lines) + "\n")
print(f"  lines.dss: {len(edges_sub)} segments, {len(xfmr_bus_ids)} XFMR endpoints")

# ---------------------------------------------------------------------------
# 2. transformers.dss -- match transformer_id to XFMR bus endpoints
# ---------------------------------------------------------------------------
matched_xfmrs = transformers[transformers["transformer_id"].isin(xfmr_bus_ids)]
xfmr_ids_in_model: list[str] = []
xfmr_kva: dict[str, float] = {}
xfmr_lines: list[str] = ["! SP&L Distribution Transformers", ""]

for _, row in matched_xfmrs.iterrows():
    xid = row["transformer_id"]
    kva = row["kva_rating"]
    xfmr_ids_in_model.append(xid)
    xfmr_kva[xid] = kva
    xfmr_lines.append(
        f"New Transformer.{xid} phases=1 windings=2 "
        f"buses=[bus_{xid} bus_{xid}_sec] conns=[wye wye] "
        f"kvs=[12.47 0.24] kvas=[{kva} {kva}] XHL=2.5"
    )

(OUT_DIR / "transformers.dss").write_text("\n".join(xfmr_lines) + "\n")
print(f"  transformers.dss: {len(xfmr_ids_in_model)} transformers")

# ---------------------------------------------------------------------------
# 3. loads.dss -- customer loads on transformer secondaries
# ---------------------------------------------------------------------------
load_lines: list[str] = ["! Customer Loads", ""]

for xid in xfmr_ids_in_model:
    kva = xfmr_kva[xid]
    load_kw = kva * rng.uniform(0.5, 0.8)
    load_lines.append(
        f"New Load.load_{xid} bus1=bus_{xid}_sec phases=1 "
        f"kv=0.24 kw={load_kw:.2f} pf=0.95"
    )

(OUT_DIR / "loads.dss").write_text("\n".join(load_lines) + "\n")
print(f"  loads.dss: {len(xfmr_ids_in_model)} loads")

# ---------------------------------------------------------------------------
# 4. pvsystems.dss -- solar aggregated by transformer
# ---------------------------------------------------------------------------
solar_active = solar[
    (solar["status"] == "active")
    & (solar["transformer_id"].isin(xfmr_bus_ids))
]
solar_agg = solar_active.groupby("transformer_id")["capacity_kw"].sum()

pv_lines: list[str] = ["! PV Systems (aggregated by transformer)", ""]
for xid, total_kw in solar_agg.items():
    pv_lines.append(
        f"New PVSystem.pv_{xid} bus1=bus_{xid}_sec phases=1 "
        f"kVA={total_kw:.1f} Pmpp={total_kw:.1f} irradiance=1 pf=1"
    )

(OUT_DIR / "pvsystems.dss").write_text("\n".join(pv_lines) + "\n")
print(f"  pvsystems.dss: {len(solar_agg)} PV systems")

# ---------------------------------------------------------------------------
# 5. storage.dss -- battery aggregated by transformer
# ---------------------------------------------------------------------------
batt_active = battery[
    (battery["status"] == "active")
    & (battery["transformer_id"].isin(xfmr_bus_ids))
]
batt_agg = batt_active.groupby("transformer_id").agg(
    total_kwh=("capacity_kwh", "sum"),
    total_kw=("power_kw", "sum"),
)

stor_lines: list[str] = ["! Battery Storage (aggregated by transformer)", ""]
for xid, row in batt_agg.iterrows():
    stor_lines.append(
        f"New Storage.batt_{xid} bus1=bus_{xid}_sec phases=1 "
        f"kWRated={row['total_kw']:.1f} kWhRated={row['total_kwh']:.1f} %stored=50"
    )

(OUT_DIR / "storage.dss").write_text("\n".join(stor_lines) + "\n")
print(f"  storage.dss: {len(batt_agg)} storage systems")

# ---------------------------------------------------------------------------
# 6. capacitors.dss -- on feeder junction buses
# ---------------------------------------------------------------------------
jct_buses = sorted(b for b in line_buses if "JCT" in b)
cap_lines: list[str] = ["! Capacitor Banks", ""]
cap_kvars = [300, 300, 300, 600, 600]

for i, bus in enumerate(jct_buses[: len(cap_kvars)]):
    cap_lines.append(
        f"New Capacitor.cap_{i + 1:04d} bus1={bus} phases=3 kvar={cap_kvars[i]} kv=12.47"
    )

(OUT_DIR / "capacitors.dss").write_text("\n".join(cap_lines) + "\n")
print(f"  capacitors.dss: {min(len(jct_buses), len(cap_kvars))} capacitors")

# ---------------------------------------------------------------------------
# 7. coordinates.dss -- only for buses that exist in the model
# ---------------------------------------------------------------------------
sec_buses = {f"bus_{xid}_sec" for xid in xfmr_ids_in_model}
all_model_buses = line_buses | sec_buses

coord_lines: list[str] = ["! Bus Coordinates", ""]
nodes_in_feeders = nodes[nodes["node_id"].apply(lambda nid: f"bus_{nid}" in all_model_buses)]

for _, row in nodes_in_feeders.iterrows():
    bus_name = f"bus_{row['node_id']}"
    coord_lines.append(
        f"SetBusXY bus={bus_name} x={row['longitude']} y={row['latitude']}"
    )

(OUT_DIR / "coordinates.dss").write_text("\n".join(coord_lines) + "\n")
print(f"  coordinates.dss: {len(nodes_in_feeders)} coordinates")

# ---------------------------------------------------------------------------
# 8. coordinates.csv -- for external visualization
# ---------------------------------------------------------------------------
coord_df = nodes_in_feeders[["node_id", "latitude", "longitude"]].copy()
coord_df["bus_name"] = "bus_" + coord_df["node_id"].astype(str)
coord_df = coord_df.rename(columns={"longitude": "x", "latitude": "y"})
coord_df[["bus_name", "x", "y"]].to_csv(OUT_DIR / "coordinates.csv", index=False)

# ---------------------------------------------------------------------------
# 9. master.dss
# ---------------------------------------------------------------------------
sub_buses = sorted(b for b in line_buses if "SUB" in b)
source_bus = sub_buses[0] if sub_buses else "bus_SUB-001"

master = f"""\
! Sisyphean Power & Light Distribution System Model

Clear

! 69 kV source with substation transformer to 12.47 kV distribution
New Circuit.SPL bus1=sourcebus basekV=69 pu=1.04 phases=3 MVAsc3=2000 MVAsc1=2100
New Transformer.sub_xfmr phases=3 windings=2 buses=[sourcebus {source_bus}] conns=[delta wye] kvs=[69 12.47] kvas=[20000 20000] XHL=7

Redirect lines.dss
Redirect transformers.dss
Redirect loads.dss
Redirect pvsystems.dss
Redirect storage.dss
Redirect capacitors.dss

Set voltagebases=[69, 12.47, 0.24]
Calcvoltagebases

Redirect coordinates.dss

Set tolerance=0.0001
Set maxiterations=100

Solve
"""

(OUT_DIR / "master.dss").write_text(master)
print(f"  master.dss: source bus = {source_bus}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("OpenDSS Model Generation Complete")
print("=" * 60)
print(f"  Lines:        {len(edges_sub)} segments")
print(f"  Transformers: {len(xfmr_ids_in_model)}")
print(f"  Loads:        {len(xfmr_ids_in_model)}")
print(f"  PV Systems:   {len(solar_agg)}")
print(f"  Storage:      {len(batt_agg)}")
print(f"  Capacitors:   {min(len(jct_buses), len(cap_kvars))}")
print(f"  Coordinates:  {len(nodes_in_feeders)}")
print(f"  Output:       {OUT_DIR.resolve()}")
print("=" * 60)
