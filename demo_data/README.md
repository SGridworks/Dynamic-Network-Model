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
                   outage history, network connectivity
transformer_id ->  transformers, customers, solar, EV chargers
customer_id    ->  customers, solar installations, EV chargers
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
| `network_connectivity.csv` | 26,441 | Physical network topology edge-list with impedance |

## Network Hierarchy

```
Substation (15)
  └── Feeder (70)  — head/tail coords radiate from substation
       └── Lateral Tap (trunk nodes along feeder route)
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

## Network Connectivity Model

`network_connectivity.csv` is an explicit edge-list defining the physical
network topology for power flow and graph analysis:

| Edge Type | From | To | Description |
|-----------|------|----|-------------|
| `feeder_trunk` | substation | feeder_head | Substation bus to feeder breakout |
| `feeder_trunk` | feeder_head / lateral_tap | lateral_tap | Main trunk segments |
| `lateral` | lateral_tap | transformer | Service lateral to each transformer |
| `feeder_trunk` | lateral_tap | feeder_tail | Final trunk segment |

Each edge includes impedance (R and X in ohm/mile), rated amps, length,
and from/to coordinates.

## Quick Start

```python
from demo_data.load_demo_data import load_all, summary

# Print summary of all datasets
summary()

# Load everything into a dict of DataFrames
data = load_all()
substations = data["substations"]
feeders = data["feeders"]
connectivity = data["network_connectivity"]

# Load only specific datasets
data = load_all(["substations", "feeders", "network_connectivity"])

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
