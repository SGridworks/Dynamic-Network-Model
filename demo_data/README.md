# Demo Datasets

Synthetic datasets representing a mid-size electric utility serving ~166,000
customers in a Phoenix, AZ-area service territory. All data is generated
deterministically (seed=42) by `generate_demo_data.py`.

## Common Keys

Every infrastructure dataset carries `substation_id` and `feeder_id` so you
can join across any combination of tables without intermediate lookups:

```
substation_id  ->  present on ALL datasets (except weather/solar profiles)
feeder_id      ->  feeders, transformers, customers, solar, EV, load profiles,
                   outage history, network nodes, network edges
transformer_id ->  transformers, customers, solar, EV chargers
customer_id    ->  customers, solar installations, EV chargers
node_id        ->  network_nodes (referenced by network_edges via from/to)
```

## Datasets

| File | Rows | Description |
|------|------|-------------|
| `substations.csv` | 15 | Substations with capacity, voltage levels, and coordinates |
| `feeders.csv` | 70 | Distribution feeders with head/tail coordinates radiating from substations |
| `transformers.csv` | 25,682 | Distribution transformers placed along feeder routes |
| `customers.csv` | 166,641 | Customers clustered around their service transformer |
| `load_profiles.csv` | 47,040 | Hourly feeder load (representative week per season) |
| `solar_installations.csv` | 20,031 | Solar PV systems co-located with customers |
| `solar_profiles.csv` | 288 | Monthly representative hourly generation curves |
| `ev_chargers.csv` | 13,398 | EV chargers co-located with customers |
| `ev_charging_profiles.csv` | 48 | Typical hourly charging load shapes |
| `weather_data.csv` | 8,760 | Hourly weather for a full year with heatwave flags |
| `growth_scenarios.csv` | 85 | 5 scenarios projected 2024-2040 |
| `outage_history.csv` | 364 | Feeder outage events for reliability analysis |
| `network_nodes.csv` | 26,457 | GIS point features — every network location |
| `network_edges.csv` | 26,442 | GIS polyline features — every conductor segment |

## Network Hierarchy

```
Substation (15)
  └── Feeder (70)  — head/tail coords radiate from substation
       └── Junction (trunk nodes along feeder route)
            └── Transformer (25,682)  — placed along feeder path
                 └── Customer (166,641)  — clustered within ~150 m
                      ├── Solar Installation (20,031)
                      ├── EV Charger (13,398)
                      └── Battery (~5,000)
```

## Spatial Model

Coordinates cascade through the hierarchy so all lat/long values are
spatially rational:

- **Substations** are placed on a grid across the Phoenix metro area
- **Feeders** radiate outward from their parent substation at evenly spaced angles
- **Transformers** are distributed along the feeder route (head to tail)
- **Customers** are clustered within ~150 m of their service transformer
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
| `node_type` | `substation_bus`, `feeder_breaker`, `junction`, `transformer`, `feeder_endpoint` |
| `substation_id` | FK to substations |
| `feeder_id` | FK to feeders |
| `latitude`, `longitude` | WGS 84 point geometry |
| `nominal_voltage_kv` | Operating voltage |
| `equipment_class` | `substation`, `breaker`, `pole_top`, `padmount`, `distribution_transformer`, `open_point` |
| `rated_capacity` | Rating value |
| `rated_capacity_units` | `MVA`, `MW`, `kVA` |
| `phase` | Phase designation (`A`, `AB`, `ABC`, etc.) |
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
| `edge_type` | `bus_tie`, `primary_overhead`, `primary_underground`, `lateral_overhead`, `lateral_underground` |
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
| `status` | `closed` (energized) or `open` (de-energized) |

### Topology Example

```
SUB-001 (substation_bus)
  │  bus_tie
  ▼
FDR-0001-HEAD (feeder_breaker)
  │  primary_overhead
  ▼
JCT-FDR-0001-001 (junction)
  ├── primary_overhead ──▶ JCT-FDR-0001-002 (junction) ──▶ ...
  ├── lateral_overhead ──▶ XFMR-000001 (transformer)
  ├── lateral_underground ──▶ XFMR-000002 (transformer)
  └── lateral_overhead ──▶ XFMR-000003 (transformer)
  ...
  ▼
FDR-0001-TAIL (feeder_endpoint, normally open)
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

# Cross-dataset join example (all solar on a specific feeder)
solar = data["solar_installations"]
fdr_solar = solar[solar["feeder_id"] == "FDR-0001"]
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
