#!/usr/bin/env python3
"""Generate OpenDSS model from SP&L network data."""

from pathlib import Path
import argparse
import json
import math

import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "demo_data"
parser = argparse.ArgumentParser(description="Export complete synthetic SP&L feeders")
parser.add_argument("--feeders", nargs="+", default=["FDR-0001", "FDR-0002"])
parser.add_argument("--output-dir", type=Path, default=ROOT / "sisyphean-power-and-light/network")
parser.add_argument("--reference-hour", default="2024-01-15 12:00:00")
args = parser.parse_args()
OUT_DIR = args.output_dir.resolve()

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

def sanitize_code(name: str) -> str:
    return name.replace(" ", "_").replace(".", "p").replace("/", "_")


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print("Loading SP&L network data...")
nodes = pd.read_csv(DATA_DIR / "network_nodes.csv", low_memory=False)
edges = pd.read_csv(DATA_DIR / "network_edges.csv")
transformers = pd.read_csv(DATA_DIR / "transformers.csv").rename(columns={"rated_kva": "kva_rating"})
solar = pd.read_csv(DATA_DIR / "solar_installations.csv")
battery = pd.read_csv(DATA_DIR / "battery_installations.csv")
feeder_registry = pd.read_csv(DATA_DIR / "feeders.csv").set_index("feeder_id")
substations = pd.read_csv(DATA_DIR / "substations.csv").set_index("substation_id")

feeders = args.feeders
selected = feeder_registry.loc[feeders]
if selected.substation_id.nunique() != 1 or selected.voltage_kv.nunique() != 1:
    raise ValueError("A demo export must contain feeders from one substation and voltage level")
substation_id = selected.substation_id.iloc[0]
substation = substations.loc[substation_id]
primary_kv = float(selected.voltage_kv.iloc[0])
source_kv = float(substation.voltage_high_kv)
source_kva = float(substation.rated_capacity_mva) * 1000
edges_sub = edges[edges["feeder_id"].isin(feeders) & edges.edge_type.ne("tie")].copy()

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
        f"normamps={int(params['normamps'])} units=mi"
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
    phase_suffix = "." + ".".join(str("ABC".index(p) + 1) for p in row["phase"])

    lines.append(
        f"New Line.line_{row['edge_id']} bus1={from_bus}{phase_suffix} bus2={to_bus}{phase_suffix} "
        f"linecode={code} length={length_mi:.8f} units=mi phases={nphases} "
        f"r1={row['impedance_r_ohm_per_mile']} x1={row['impedance_x_ohm_per_mile']} "
        f"normamps={row['rated_amps']}"
    )

(OUT_DIR / "lines.dss").write_text("\n".join(lines) + "\n")
print(f"  lines.dss: {len(edges_sub)} segments, {len(xfmr_bus_ids)} XFMR endpoints")

# ---------------------------------------------------------------------------
# 2. transformers.dss -- match transformer_id to XFMR bus endpoints
# ---------------------------------------------------------------------------
matched_xfmrs = transformers[transformers["transformer_id"].isin(xfmr_bus_ids)]
xfmr_ids_in_model: list[str] = []
xfmr_kva: dict[str, float] = {}
connections: dict[str, dict] = {}
voltage_bases = {source_kv, primary_kv}
xfmr_lines: list[str] = ["! SP&L Distribution Transformers", ""]

for _, row in matched_xfmrs.iterrows():
    xid = row["transformer_id"]
    kva = row["kva_rating"]
    xfmr_ids_in_model.append(xid)
    xfmr_kva[xid] = kva
    phase = str(row["phase"])
    nphases = len(phase)
    suffix = "." + ".".join(str("ABC".index(p) + 1) for p in phase)
    # Registry primary voltage is line-line; one-phase winding ratings are L-N.
    winding_primary = primary_kv / math.sqrt(3) if nphases == 1 else primary_kv
    secondary_kv = float(row["secondary_voltage_v"]) / 1000
    voltage_bases.add(secondary_kv * math.sqrt(3) if nphases == 1 else secondary_kv)
    connections[xid] = {"bus": f"bus_{xid}_sec{suffix}", "phases": nphases,
                        "kv": secondary_kv, "feeder_id": row["feeder_id"], "kva": float(kva)}
    xfmr_lines.append(
        f"New Transformer.{xid} phases={nphases} windings=2 "
        f"buses=[bus_{xid}{suffix}.0 bus_{xid}_sec{suffix}.0] conns=[wye wye] "
        f"kvs=[{winding_primary:.9f} {secondary_kv}] kvas=[{kva} {kva}] XHL=2.5"
    )

(OUT_DIR / "transformers.dss").write_text("\n".join(xfmr_lines) + "\n")
print(f"  transformers.dss: {len(xfmr_ids_in_model)} transformers")

# ---------------------------------------------------------------------------
# 3. loads.dss -- customer loads on transformer secondaries
# ---------------------------------------------------------------------------
load_lines: list[str] = ["! Customer Loads", ""]
customers = pd.read_csv(DATA_DIR / "customers.csv")
weights = customers.groupby("transformer_id").contracted_demand_kw.sum()
matched_xfmrs = matched_xfmrs.assign(weight=matched_xfmrs.transformer_id.map(weights))
feeder_weights = matched_xfmrs.groupby("feeder_id").weight.sum()
profiles = pd.read_parquet(ROOT / "sisyphean-power-and-light/timeseries/substation_load_hourly.parquet")
reference = profiles[profiles.timestamp.eq(pd.Timestamp(args.reference_hour))].set_index("feeder_id")
if not set(feeders).issubset(reference.index) or reference.loc[feeders, ["total_load_mw", "load_mvar"]].isna().any().any():
    raise ValueError("Reference hour must have complete load data for every exported feeder")

for xid in xfmr_ids_in_model:
    connection = connections[xid]
    fid = connection["feeder_id"]
    weight = float(weights[xid] / feeder_weights[fid])
    load_kw = float(reference.loc[fid, "total_load_mw"]) * 1000 * weight
    load_kvar = float(reference.loc[fid, "load_mvar"]) * 1000 * weight
    connection.update({"load_kw": load_kw, "load_kvar": load_kvar, "load_weight": weight})
    load_lines.append(
        f"New Load.load_{xid} bus1={connection['bus']} phases={connection['phases']} "
        f"kv={connection['kv']} kw={load_kw:.8f} kvar={load_kvar:.8f}"
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
    connection = connections[xid]
    pv_lines.append(
        f"New PVSystem.pv_{xid} bus1={connection['bus']} phases={connection['phases']} "
        f"kV={connection['kv']} "
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
    connection = connections[xid]
    stor_lines.append(
        f"New Storage.batt_{xid} bus1={connection['bus']} phases={connection['phases']} "
        f"kV={connection['kv']} kWRated={row['total_kw']:.1f} "
        f"kWhRated={row['total_kwh']:.1f} %stored=50 state=idling"
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
        f"New Capacitor.cap_{i + 1:04d} bus1={bus} phases=3 kvar={cap_kvars[i]} kv={primary_kv}"
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

! Synthetic source; voltage and capacity follow the substation registry.
New Circuit.SPL bus1=sourcebus basekV={source_kv} pu=1.04 phases=3 MVAsc3=2000 MVAsc1=2100
New Transformer.sub_xfmr phases=3 windings=2 buses=[sourcebus {source_bus}] conns=[delta wye] kvs=[{source_kv} {primary_kv}] kvas=[{source_kva} {source_kva}] XHL=7

Redirect lines.dss
Redirect transformers.dss
Redirect loads.dss
Redirect pvsystems.dss
Redirect storage.dss
Redirect capacitors.dss

Set voltagebases={sorted(voltage_bases)}
Calcvoltagebases

Redirect coordinates.dss

Set tolerance=0.0001
Set maxiterations=100

Solve
"""

(OUT_DIR / "master.dss").write_text(master)
(OUT_DIR / "model_manifest.json").write_text(json.dumps({
    "synthetic": True, "substation_id": substation_id, "feeders": feeders,
    "complete_feeders": True, "line_count": len(edges_sub),
    "transformer_count": len(connections), "connections": connections,
    "reference_hour": args.reference_hour,
    "load_basis": "Source hourly feeder MW/Mvar allocated by customer contracted demand; modeled as gross load before DER",
    "secondary_voltage_basis": "Single-phase actual winding kV; multiphase line-line kV",
    "tie_policy": "Inter-feeder ties excluded (normally open radial snapshot)",
}, indent=2) + "\n")
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
