# Sisyphean Power & Light — Demo Datasets

> **SYNTHETIC DATA** — Sisyphean Power & Light is a fictional utility.
> All data is computationally generated. No real customer, infrastructure,
> or operational data is included.

Synthetic datasets representing SP&L, a fictional mid-size electric utility
serving ~140,500 customers in a Phoenix, AZ-area service territory. All
data is generated deterministically (seed=42) by `generate_demo_data.py`.

For the full walkthrough, example projects, and tips for using with Claude
Code and other AI tools, see **[USERS_GUIDE.md](USERS_GUIDE.md)**.

## Common Keys

Every infrastructure dataset carries `substation_id` and `feeder_id` so you
can join across any combination of tables without intermediate lookups:

```
substation_id  ->  present on ALL datasets (except weather/solar profiles)
feeder_id      ->  feeders, transformers, customers, solar, EV, load profiles,
                   customer interval data, outage history, network nodes,
                   network edges
transformer_id ->  transformers, customers, solar, EV chargers,
                   customer interval data
customer_id    ->  customers, solar installations, EV chargers,
                   customer interval data
node_id        ->  network_nodes (referenced by network_edges via from/to)
```

## Datasets

| File | Rows | Description |
|------|------|-------------|
| `substations.csv` | 15 | Substations at real Phoenix intersections with capacity and voltage levels |
| `feeders.csv` | 65 | Distribution feeders following N/S/E/W streets from substations |
| `transformers.csv` | 21,545 | Distribution transformers placed along feeder routes |
| `customers.csv` | 140,459 | Customers clustered around their service transformer |
| `load_profiles.csv` | 174,720 | 15-minute feeder load (representative week per season) |
| `customer_interval_data.csv` | 336,000 | 15-minute AMI metering for ~500 sampled customers |
| `solar_installations.csv` | 17,242 | Solar PV systems co-located with customers |
| `solar_profiles.csv` | 288 | Monthly representative hourly generation curves |
| `ev_chargers.csv` | 11,076 | EV chargers co-located with customers |
| `ev_charging_profiles.csv` | 48 | Typical hourly charging load shapes |
| `weather_data.csv` | 43,848 | 5-year hourly weather (2020-2024) with heatwave and storm flags |
| `growth_scenarios.csv` | 85 | 5 scenarios projected 2024-2040 |
| `outage_history.csv` | 2,306 | Feeder outage events (2020-2024) clustered during storms and heatwaves |
| `network_nodes.csv` | 43,827 | GIS point features — every network location including switches |
| `network_edges.csv` | 43,826 | GIS polyline features — every conductor segment and tie |

## Network Hierarchy

```
Substation (15)  — placed at real Phoenix street intersections
  └── Feeder (65)  — follow N/S/E/W streets from substation
       ├── Recloser (every ~1/3 of feeder length)
       ├── Sectionalizer (at selected junctions)
       └── Junction (trunk nodes along feeder route)
            └── Fuse → Transformer (21,545)  — placed along feeder path
                 └── Customer (140,459)  — clustered within ~150 m
                      ├── Solar Installation (17,242)
                      ├── EV Charger (11,076)
                      └── Battery (~4,200)
  Tie Switches — normally-open connections between adjacent feeder tails
```

## Spatial Model

Coordinates are aligned to the **Phoenix, AZ street grid** so assets render
correctly on a map.  The grid origin is Central Ave & Washington St.

- **Substations** are placed at named intersections (e.g., Camelback Rd & 35th Ave)
- **Feeders** follow cardinal directions along streets (N/S along avenues, E/W along roads)
- **Transformers** are distributed at intervals along the feeder route
- **Customers** are offset perpendicular to the street (~40-120 ft from centerline)
- **Solar/EV** assets inherit their customer's coordinates

## GIS Network Model (Node/Edge Database)

The network topology uses a normalized **node/edge** structure following
ESRI geodatabase and GIS conventions — two separate feature classes that
together define the full distribution network graph.

### `network_nodes.csv` — Point Feature Class

Every distinct network location. Nodes are the join target for edges via
`from_node_id` / `to_node_id`.

| Column | Description |
|--------|-------------|
| `node_id` | Unique identifier (PK) |
| `node_type` | `substation_bus`, `feeder_breaker`, `junction`, `transformer`, `protective_device`, `tie_switch`, `feeder_endpoint` |
| `substation_id` | FK to substations |
| `feeder_id` | FK to feeders |
| `latitude`, `longitude` | WGS 84 point geometry |
| `nominal_voltage_kv` | Operating voltage |
| `equipment_class` | `substation`, `breaker`, `pole_top`, `padmount`, `recloser`, `sectionalizer`, `fuse`, `distribution_transformer`, `tie_switch`, `open_point` |
| `rated_capacity` | Rating value |
| `rated_capacity_units` | `MVA`, `MW`, `kVA` |
| `phase` | Phase designation (`A`, `AB`, `ABC`, etc.) |
| `installation_year` | Year installed |
| `status` | `active`, `closed`, `open`, `failed` |

### `network_edges.csv` — Polyline Feature Class

Every conductor segment connecting two nodes. Geometry is implied by the
from/to node coordinates (or can be drawn as straight lines between them).

| Column | Description |
|--------|-------------|
| `edge_id` | Unique identifier (PK) |
| `from_node_id` | FK to network_nodes |
| `to_node_id` | FK to network_nodes |
| `feeder_id` | FK to feeders |
| `substation_id` | FK to substations |
| `edge_type` | `bus_tie`, `primary_overhead`, `primary_underground`, `lateral_overhead`, `lateral_underground`, `tie` |
| `conductor_type` | Wire spec (`477 ACSR`, `4/0 AL`, `#2 ACSR`, etc.) |
| `phase` | Phase designation |
| `length_miles`, `length_ft` | Segment length in both units |
| `impedance_r_ohm_per_mile` | Positive-sequence resistance |
| `impedance_x_ohm_per_mile` | Positive-sequence reactance |
| `impedance_z0_ohm_per_mile` | Zero-sequence impedance |
| `rated_amps` | Thermal rating |
| `nominal_voltage_kv` | Operating voltage |
| `num_phases` | 1, 2, or 3 |
| `is_overhead` | Boolean — overhead vs underground |
| `installation_year` | Year installed |
| `status` | `closed` (energized) or `open` (de-energized) |

### Topology Example

```
SUB-001 (substation_bus)
  │  bus_tie
  ▼
FDR-0001-HEAD (feeder_breaker)
  │  primary_overhead
  ▼
JCT-FDR-0001-001 (junction, recloser)
  ├── primary_overhead ──▶ JCT-FDR-0001-002 (junction) ──▶ ...
  ├── lateral ──▶ FUSE-XFMR-000001 (fuse) ──▶ XFMR-000001 (transformer)
  ├── lateral ──▶ FUSE-XFMR-000002 (fuse) ──▶ XFMR-000002 (transformer)
  └── lateral ──▶ FUSE-XFMR-000003 (fuse) ──▶ XFMR-000003 (transformer)
  ...
  ▼
FDR-0001-TAIL (feeder_endpoint, normally open)
  │  tie (normally open)
  ▼
TIE-0001 (tie_switch) ──▶ FDR-0002-TAIL
```

## Quick Start

```python
from demo_data.load_demo_data import load_all, summary

# Print summary of all datasets
summary()

# Load everything into a dict of DataFrames
data = load_all()
nodes = data["network_nodes"]
edges = data["network_edges"]

# Build a NetworkX graph from the node/edge tables
import networkx as nx
G = nx.from_pandas_edgelist(
    edges.reset_index(),
    source="from_node_id", target="to_node_id",
    edge_attr=True, create_using=nx.DiGraph,
)

# Find all nodes on a specific feeder
fdr_nodes = nodes[nodes["feeder_id"] == "FDR-0001"]
fdr_edges = edges[edges["feeder_id"] == "FDR-0001"]

# Load 15-minute AMI interval data
ami = data["customer_interval_data"]
```

## Regenerating Data

```bash
python demo_data/generate_demo_data.py
```

## Growth Scenarios

| ID | Name | Description |
|----|------|-------------|
| SCN-001 | Reference Case | Moderate growth, current policy trajectory |
| SCN-002 | High EV Adoption | Aggressive EV adoption driven by policy incentives |
| SCN-003 | High Solar Growth | Rapid DER expansion with net metering 2.0 |
| SCN-004 | Extreme Heat | Climate-driven load growth from increased cooling |
| SCN-005 | Full Electrification | Building and transportation electrification mandate |
