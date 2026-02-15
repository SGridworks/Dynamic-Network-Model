# Sisyphean Power & Light — Dataset User's Guide

A comprehensive guide for power engineers exploring machine learning,
AI-enabled tools, and modern data science with realistic distribution
system data.

> **SYNTHETIC DATA NOTICE**
>
> Sisyphean Power & Light (SP&L) is an entirely fictional utility. Every
> record in this dataset — customer accounts, network topology, load
> measurements, DER installations, geographic coordinates, and outage
> events — is computationally generated. No real customer, infrastructure,
> or operational data from any actual utility is included. Any resemblance
> to real utilities, persons, or locations is coincidental.
>
> This data is provided solely for educational and experimental purposes.

---

## Table of Contents

1. [Who This Is For](#who-this-is-for)
2. [The Utility at a Glance](#the-utility-at-a-glance)
3. [Getting Started](#getting-started)
4. [Dataset Catalog](#dataset-catalog)
5. [Data Model & Relationships](#data-model--relationships)
6. [Common Keys](#common-keys)
7. [Spatial Model](#spatial-model)
8. [GIS Network Model](#gis-network-model)
9. [Working with the Data](#working-with-the-data)
10. [Example Projects](#example-projects)
11. [Using with Claude Code](#using-with-claude-code)
12. [Data Generation & Reproducibility](#data-generation--reproducibility)
13. [Known Simplifications](#known-simplifications)

---

## Who This Is For

You are a power systems engineer, distribution planner, data scientist,
or student who wants to experiment with modern analytical tools on
realistic grid data — without the months-long process of extracting,
cleaning, and anonymizing production data.

This dataset is specifically designed for use with **AI-enabled
development tools like Claude Code**. The idea is simple: you have a
realistic sandbox, you have an AI assistant that can write code, and
you can just build things now.

Want to train a load forecasting model? Ask Claude Code to build one
using the load profiles and weather data. Curious about hosting capacity?
Have it analyze solar saturation by transformer. Need a reliability
dashboard? Point it at the outage history and let it build one.

The data is structured the way real utility data is structured — with
the same hierarchy, the same key relationships, the same GIS conventions
— so the patterns you learn here transfer directly to production systems.

---

## The Utility at a Glance

**Sisyphean Power & Light (SP&L)** is a fictional mid-size electric utility
serving a suburban/rural territory in the Phoenix, Arizona metropolitan
area.

| Characteristic | Value |
|----------------|-------|
| Service territory | Phoenix, AZ metro (~20 mi x 20 mi) |
| Customers | ~140,500 |
| Substations | 15 (at named Phoenix intersections) |
| Distribution feeders | 65 (follow N/S/E/W streets) |
| Distribution transformers | ~21,500 |
| Solar PV installations | ~17,200 (~12% adoption) |
| EV chargers | ~11,100 (~8% adoption) |
| Battery storage | ~4,200 (~3% adoption) |
| Climate | Hot desert (summer peaks, heatwave events, monsoon storms) |
| Voltage levels | 69/115/230 kV transmission; 12.47/13.8/24.9 kV distribution |

### Customer Mix

| Type | Share |
|------|-------|
| Residential | ~82% |
| Commercial | ~13% |
| Industrial | ~3% |
| Municipal | ~2% |

---

## Getting Started

### Prerequisites

- Python 3.8+
- pandas (`pip install pandas`)

### Load the Data

```python
from demo_data.load_demo_data import load_all, summary

# See what's available
summary()

# Load everything
data = load_all()

# Or load specific datasets
from demo_data.load_demo_data import (
    load_substations,
    load_feeders,
    load_customers,
    load_customer_interval_data,
    load_network_nodes,
    load_network_edges,
)

subs = load_substations()
feeders = load_feeders()
customers = load_customers()
ami = load_customer_interval_data()
```

### Regenerate from Scratch

The CSVs are pre-generated, but you can recreate them at any time:

```bash
python demo_data/generate_demo_data.py
```

The generator uses `random.seed(42)` so output is deterministic and
reproducible.

---

## Dataset Catalog

### Infrastructure

| File | Rows | Description |
|------|------|-------------|
| `substations.csv` | 15 | Substations at real Phoenix intersections with capacity (MVA), voltage |
| `feeders.csv` | 65 | Feeders with head/tail coords, direction (N/S/E/W), conductor type, capacity |
| `transformers.csv` | 21,545 | Distribution transformers with kVA rating, phase, manufacturer |
| `customers.csv` | 140,459 | Customers with type, rate class, demand, DER adoption flags |

### DER Assets

| File | Rows | Description |
|------|------|-------------|
| `solar_installations.csv` | 17,242 | PV systems with capacity, panel type, inverter, install date |
| `solar_profiles.csv` | 288 | Hourly generation curves per month (clear-sky, GHI, temperature) |
| `ev_chargers.csv` | 11,076 | Chargers with type (L1/L2/DCFC), power rating, network operator |
| `ev_charging_profiles.csv` | 48 | Typical hourly load shapes by charger type and day type |

### Operations

| File | Rows | Description |
|------|------|-------------|
| `load_profiles.csv` | 174,720 | 15-minute feeder load with MW, MVAR, voltage, power factor |
| `customer_interval_data.csv` | 336,000 | 15-minute AMI metering for ~500 sampled customers (summer week) |
| `weather_data.csv` | 43,848 | 5-year hourly (2020-2024): temperature, humidity, wind, GHI, heatwave + storm flags |
| `outage_history.csv` | 2,306 | Outage events (2020-2024) clustered during storms and heatwaves |

### Planning

| File | Rows | Description |
|------|------|-------------|
| `growth_scenarios.csv` | 85 | 5 scenarios projected 2024-2040 (EV, solar, load growth, etc.) |

### GIS Network Model

| File | Rows | Description |
|------|------|-------------|
| `network_nodes.csv` | 43,827 | Point features: every network location with switching devices |
| `network_edges.csv` | 43,826 | Polyline features: every conductor segment including tie connections |

---

## Data Model & Relationships

The data follows the standard utility asset hierarchy:

```
Substation (15)  — at named Phoenix intersections
  └── Feeder (65)  — follow N/S/E/W streets
       ├── Recloser  — every ~1/3 of feeder length
       ├── Sectionalizer  — at selected junctions
       └── Junction (trunk tap points)
            └── Fuse → Transformer (21,545)
                 └── Customer (140,459)
                      ├── Solar Installation (17,242)
                      ├── EV Charger (11,076)
                      └── Battery (~4,200)
  Tie Switch  — normally-open connection to adjacent feeder tail
```

### Entity-Relationship Summary

```
substations  1───N  feeders
feeders      1───N  transformers
transformers 1───N  customers
customers    1───1  solar_installations  (where has_solar=True)
customers    1───1  ev_chargers          (where has_ev=True)
feeders      1───N  load_profiles        (15-min time-series)
customers    N───N  customer_interval_data (15-min AMI, sampled)
feeders      1───N  outage_history
feeders      1───N  network_nodes
feeders      1───N  network_edges
network_nodes 1───N network_edges        (via from_node_id, to_node_id)
```

---

## Common Keys

Every infrastructure table carries `substation_id` and `feeder_id` so you
can join across any combination without intermediate lookups.

| Key | Present On |
|-----|-----------|
| `substation_id` | All infrastructure tables, nodes, edges, load profiles, outage history, customer interval data |
| `feeder_id` | Feeders, transformers, customers, solar, EV, load profiles, outages, customer interval data, nodes, edges |
| `transformer_id` | Transformers, customers, solar, EV chargers, customer interval data |
| `customer_id` | Customers, solar installations, EV chargers, customer interval data |
| `node_id` | Network nodes (referenced by edges as `from_node_id` / `to_node_id`) |

### Join Examples

```python
# All customers on a specific feeder
fdr_custs = customers[customers["feeder_id"] == "FDR-0001"]

# All solar capacity by substation
solar = data["solar_installations"]
solar.groupby("substation_id")["capacity_kw"].sum()

# Transformer loading: join customers to their transformer
cust_demand = customers.groupby("transformer_id")["contracted_demand_kw"].sum()
xfmr_loading = data["transformers"].join(cust_demand.rename("total_demand_kw"))

# Feeder outage frequency
data["outage_history"].groupby("feeder_id").size().sort_values(ascending=False)
```

---

## Spatial Model

All coordinates use **WGS 84 (EPSG:4326)** and are aligned to the
**Phoenix, AZ street grid** so assets render correctly on a map.

### Street Grid Reference

The coordinate system is based on the Phoenix grid:
- **Origin**: Central Ave & Washington St (33.4484°N, 112.0740°W)
- **Scale**: 1 mile ≈ 0.01449° latitude, 0.01737° longitude (at 33.45°N)
- **E-W streets**: Baseline Rd, Broadway Rd, McDowell Rd, Thomas Rd,
  Indian School Rd, Camelback Rd, Northern Ave, Dunlap Ave, etc.
- **N-S streets**: 59th Ave through 56th St

### Placement Rules

| Element | Placement Rule |
|---------|---------------|
| Substations | At named intersections (e.g., "Camelback Rd & 35th Ave") |
| Feeders | Follow cardinal directions (N/S/E/W) along streets, 2-8 miles long |
| Transformers | At intervals along the feeder route with ~30 ft perpendicular offset |
| Customers | Offset 40-120 ft perpendicular to the street (like house lots) |
| Solar/EV | Co-located with their parent customer |
| Junctions | Along the feeder trunk line |

This means you can:
- Plot the entire network on a map and it looks like a real distribution system
- See feeders following actual Phoenix streets
- Compute geographic distances that are physically meaningful
- Build spatial queries (e.g., "all transformers within 1 mile of this substation")
- Feed coordinates directly into GIS tools (QGIS, ArcGIS, Leaflet, Folium)

---

## GIS Network Model

The network topology uses a normalized **node/edge database** following
ESRI geodatabase conventions. This is the same structure used by utility
GIS systems like ArcGIS Utility Network, GE Smallworld, and Schneider ArcFM.

### Nodes (`network_nodes.csv`)

Every distinct location in the network. Think of these as the **point
feature class** in a geodatabase.

| Node Type | Description |
|-----------|-------------|
| `substation_bus` | High-side bus at each substation |
| `feeder_breaker` | Feeder head breaker |
| `junction` | Trunk-line tap point (may host recloser or sectionalizer) |
| `protective_device` | Fuse on each lateral serving a transformer |
| `transformer` | Distribution transformer |
| `tie_switch` | Normally-open tie between adjacent feeder tails |
| `feeder_endpoint` | Normally-open feeder tail |

Key attributes: `node_id`, `node_type`, `latitude`, `longitude`,
`nominal_voltage_kv`, `equipment_class`, `rated_capacity`, `phase`,
`installation_year`, `status`.

### Edges (`network_edges.csv`)

Every conductor segment connecting two nodes. Think of these as the
**polyline feature class** in a geodatabase.

| Edge Type | Description |
|-----------|-------------|
| `bus_tie` | Substation bus to feeder breaker |
| `primary_overhead` | Overhead trunk conductor |
| `primary_underground` | Underground trunk conductor |
| `lateral_overhead` | Overhead service lateral (junction → fuse → transformer) |
| `lateral_underground` | Underground service lateral |
| `tie` | Normally-open tie between feeder tails (via tie switch) |

Key attributes: `edge_id`, `from_node_id`, `to_node_id`, `conductor_type`,
`impedance_r_ohm_per_mile`, `impedance_x_ohm_per_mile`,
`impedance_z0_ohm_per_mile`, `rated_amps`, `num_phases`, `is_overhead`,
`installation_year`.

### Switching Devices

The network includes realistic switching configurations:
- **Reclosers** at every ~1/3 of the feeder length
- **Sectionalizers** at every 4th junction
- **Fuses** on every lateral (junction → fuse → transformer)
- **Tie switches** (normally open) connecting adjacent feeder tails
  at the same voltage — used for load transfer during outages

### Building a Graph

```python
import networkx as nx
from demo_data.load_demo_data import load_network_nodes, load_network_edges

nodes = load_network_nodes()
edges = load_network_edges()

# Build directed graph
G = nx.from_pandas_edgelist(
    edges.reset_index(),
    source="from_node_id",
    target="to_node_id",
    edge_attr=True,
    create_using=nx.DiGraph,
)

# Add node attributes
for node_id, row in nodes.iterrows():
    if node_id in G:
        G.nodes[node_id].update(row.to_dict())

# Analyze a single feeder
fdr_edges = edges[edges["feeder_id"] == "FDR-0001"]
F = nx.from_pandas_edgelist(
    fdr_edges.reset_index(),
    source="from_node_id",
    target="to_node_id",
    edge_attr=True,
    create_using=nx.DiGraph,
)
print(f"Nodes: {F.number_of_nodes()}, Edges: {F.number_of_edges()}")

# Find all tie switches (normally-open connections between feeders)
ties = nodes[nodes["node_type"] == "tie_switch"]
print(f"Tie switches: {len(ties)}")
```

---

## Working with the Data

### Loading Subsets

The `load_all()` function accepts a list of dataset names:

```python
# Load only what you need
data = load_all(["feeders", "load_profiles", "weather_data"])
```

### Filtering by Feeder

Since every table has `feeder_id`, you can quickly slice any dataset:

```python
fdr = "FDR-0012"
fdr_customers = customers[customers["feeder_id"] == fdr]
fdr_solar = solar[solar["feeder_id"] == fdr]
fdr_load = load_profiles[load_profiles["feeder_id"] == fdr]
fdr_outages = outages[outages["feeder_id"] == fdr]
fdr_nodes = nodes[nodes["feeder_id"] == fdr]
fdr_edges = edges[edges["feeder_id"] == fdr]
```

### 15-Minute Interval Data

Load profiles use 15-minute intervals (4 per hour). The feeder-level
profiles cover one representative week per season (2,688 intervals per
feeder). Customer-level AMI data covers a summer week for ~500 sampled
customers.

```python
# Feeder-level 15-min load
load = data["load_profiles"]
summer = load[load["timestamp"].dt.month == 7]
summer_peaks = summer.groupby("feeder_id")["load_mw"].max()

# Customer AMI data — 15-min demand by customer type
ami = data["customer_interval_data"]
residential = ami[ami["customer_type"] == "residential"]
daily_shape = residential.groupby(residential["timestamp"].dt.hour)["demand_kw"].mean()
```

### Weather and Outage Correlation

Weather data includes both `is_heatwave` and `is_storm` flags. Outage
events cluster during these weather events.

```python
weather = data["weather_data"]
outages = data["outage_history"]

# Storm and heatwave days
storm_days = weather[weather["is_storm"]]["timestamp"].dt.date.unique()
heat_days = weather[weather["is_heatwave"]]["timestamp"].dt.date.unique()

# Outage distribution by weather type
outages["date"] = outages["start_time"].dt.date
outages["weather_type"] = "normal"
outages.loc[outages["weather_related"], "weather_type"] = "weather"
outages.groupby("weather_type").size()
```

### Growth Scenarios

Five planning scenarios project adoption rates and load growth from
2024 through 2040:

| ID | Scenario | Key Driver |
|----|----------|-----------|
| SCN-001 | Reference Case | Current policy trajectory |
| SCN-002 | High EV Adoption | Aggressive EV incentives |
| SCN-003 | High Solar Growth | Net metering 2.0 expansion |
| SCN-004 | Extreme Heat | Climate-driven cooling demand |
| SCN-005 | Full Electrification | Building + transportation mandate |

```python
scenarios = data["growth_scenarios"]

# Compare EV adoption across scenarios in 2035
yr_2035 = scenarios.xs(2035, level="year")
print(yr_2035[["scenario_name", "ev_adoption_pct", "peak_demand_growth_pct"]])
```

---

## Example Projects

Here are concrete things you can build with this data. Each is a good
prompt for Claude Code or similar AI tools.

### 1. Transformer Overload Screening

> "Identify transformers where total connected customer demand exceeds
> 80% of the transformer's kVA rating. Flag the ones that also have
> high solar penetration as candidates for reverse power flow issues."

Datasets: `transformers`, `customers`, `solar_installations`

### 2. Feeder Load Forecasting

> "Build a random forest model that predicts 15-minute feeder load from
> time of day, day of week, season, and temperature. Train on summer
> and winter weeks, test on spring and fall."

Datasets: `load_profiles`, `weather_data`

### 3. EV Impact Assessment

> "For each feeder, calculate the additional peak demand if all EV
> chargers operate simultaneously at rated power. Compare to feeder
> capacity and flag feeders that would be overloaded under the High EV
> Adoption scenario in 2030."

Datasets: `feeders`, `ev_chargers`, `ev_charging_profiles`, `growth_scenarios`

### 4. Outage Prediction Model

> "Train a classifier that predicts whether a feeder will experience
> an outage on a given day based on weather conditions (temperature,
> wind, heatwave/storm flags), feeder age, length, and historical
> outage rate."

Datasets: `outage_history`, `weather_data`, `feeders`

### 5. Hosting Capacity Analysis

> "For each transformer, calculate the maximum additional solar PV that
> can be interconnected before the transformer reaches 100% of nameplate.
> Map the results geospatially."

Datasets: `transformers`, `solar_installations`, `customers`

### 6. Network Graph Analysis

> "Find the longest path from any substation to a feeder endpoint.
> Calculate total impedance along that path. Identify the most critical
> junction nodes (highest betweenness centrality). Identify all tie
> switches and which feeders they connect."

Datasets: `network_nodes`, `network_edges`

### 7. Reliability Dashboard

> "Build an interactive dashboard showing SAIDI, SAIFI, and CAIDI
> metrics by feeder and substation. Include cause breakdowns, weather
> correlation (storm vs heatwave vs normal), and seasonal trends."

Datasets: `outage_history`, `feeders`, `weather_data`

### 8. Scenario Comparison Tool

> "Create a visualization that shows how each growth scenario affects
> feeder loading over time. Highlight which feeders exceed capacity
> first under each scenario."

Datasets: `growth_scenarios`, `feeders`, `load_profiles`

### 9. AMI Load Shape Clustering

> "Cluster the ~500 customers in the AMI interval data by their weekly
> load shape. Identify typical residential, commercial, and industrial
> profiles. Look for HVAC cycling patterns in the residential data."

Datasets: `customer_interval_data`

### 10. Switching Analysis

> "For each feeder, identify all protective devices (reclosers,
> sectionalizers, fuses) and their positions along the trunk. Calculate
> the number of customers downstream of each device. Find all tie
> switches and determine which feeders could accept load transfer."

Datasets: `network_nodes`, `network_edges`, `customers`

---

## Using with Claude Code

This dataset is designed to be explored with AI-assisted coding. Here
are some effective prompts:

### Exploration

- *"Summarize the SP&L dataset. What tables are available and how are
  they related?"*
- *"Show me the top 10 most loaded feeders as a percentage of their
  rated capacity."*
- *"How many customers per transformer on average? Show the distribution."*

### Analysis

- *"Correlate summer peak load with temperature across all feeders.
  What's the R-squared?"*
- *"Find transformers that serve more than 10 customers with solar.
  What's the total solar capacity vs transformer rating?"*
- *"Build a heatmap of outage frequency by month and cause. Show how
  outages cluster during storms and heatwaves."*

### Building Tools

- *"Create a Python function that takes a feeder ID and returns a
  complete profile: load summary, customer count, DER penetration,
  reliability metrics, switching devices, and a one-line network diagram."*
- *"Build a Folium map showing all substations and feeders aligned to
  the Phoenix street grid, color-coded by loading percentage."*
- *"Write a script that exports a single feeder's node/edge data as a
  NetworkX graph and computes basic graph metrics including tie switches."*

### Tips

1. **Start with `load_all()`** — it gives you everything in one dict
2. **Use feeder_id as your main filter** — it's the natural unit of
   analysis for most distribution engineering questions
3. **The node/edge model is graph-ready** — `from_node_id`/`to_node_id`
   map directly to NetworkX, igraph, or any graph library
4. **All coordinates are mappable** — they follow the Phoenix street
   grid and render correctly in Folium, Plotly, or any mapping library
5. **15-min data for detailed analysis** — `load_profiles` has feeder-level
   15-min data; `customer_interval_data` has AMI-level customer data
6. **Outages correlate with weather** — use `is_heatwave` and `is_storm`
   from weather data to explain outage patterns

---

## Data Generation & Reproducibility

All data is generated by `generate_demo_data.py` using `random.seed(42)`.
Running the generator always produces identical output.

### Modifying the Data

Want a bigger or smaller utility? Edit the generator:

- Change the number of substations in `SUBSTATION_DEFS`
- Adjust `n_feeders = random.randint(3, 6)` for more or fewer feeders
- Change `n_cust = random.randint(1, 12)` for customer density
- Modify DER adoption rates (currently 12% solar, 8% EV, 3% battery)
- Edit the Phoenix grid coordinates to reshape the service territory

After editing, run `python demo_data/generate_demo_data.py` to regenerate
all CSVs.

---

## Known Simplifications

This is synthetic data designed for experimentation. The following
simplifications are intentional:

| Area | Simplification | Real-World Difference |
|------|---------------|----------------------|
| Load shapes | Smooth diurnal curves with random noise | Real loads have sharper peaks, weather spikes, and demand response events |
| Solar generation | Clear-sky model with random cloud factor | Real generation depends on panel orientation, shading, inverter clipping |
| Impedance | Per-mile values with random variation | Real impedance depends on exact conductor geometry and spacing |
| Phasing | Random phase assignment | Real phase balancing follows engineering rules |
| Customer interval data | ~500 sampled customers, summer week only | Real AMI covers all customers for a full year |
| Tie switches | Based on geographic proximity of feeder tails | Real tie placement considers load transfer capacity and switching studies |

These simplifications are fine for learning, prototyping, and
experimentation. If you need production-grade accuracy for any of these
areas, the data model is structured so you can swap in real data for
specific tables while keeping the rest of the synthetic dataset as
scaffolding.

---

*Sisyphean Power & Light is a fictional utility. This dataset is synthetic
and provided for educational and experimental purposes only.*
