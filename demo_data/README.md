# Demo Datasets

Synthetic datasets representing a mid-size electric utility serving ~110,000
customers in a Phoenix-like service territory. All data is generated
deterministically (seed=42) by `generate_demo_data.py`.

## Datasets

| File | Rows | Description |
|------|------|-------------|
| `substations.csv` | 15 | Substations with capacity, voltage levels, and coordinates |
| `feeders.csv` | 53 | Distribution feeders linked to substations |
| `transformers.csv` | 17,076 | Distribution transformers linked to feeders |
| `customers.csv` | 110,599 | Customers linked to transformers with DER flags |
| `load_profiles.csv` | 35,616 | Hourly feeder load (representative week per season) |
| `solar_installations.csv` | 13,357 | Solar PV systems linked to customers |
| `solar_profiles.csv` | 288 | Monthly representative hourly generation curves |
| `ev_chargers.csv` | 8,803 | EV chargers linked to customers |
| `ev_charging_profiles.csv` | 48 | Typical hourly charging load shapes |
| `weather_data.csv` | 8,760 | Hourly weather for a full year with heatwave flags |
| `growth_scenarios.csv` | 85 | 5 scenarios projected 2024-2040 |
| `outage_history.csv` | 270 | Feeder outage events for reliability analysis |

## Network Hierarchy

```
Substation (15)
  └─ Feeder (53)
       └─ Transformer (17,076)
            └─ Customer (110,599)
                 ├─ Solar Installation (13,357)
                 ├─ EV Charger (8,803)
                 └─ Battery (~3,300)
```

## Quick Start

```python
from demo_data.load_demo_data import load_all, summary

# Print summary of all datasets
summary()

# Load everything into a dict of DataFrames
data = load_all()
substations = data["substations"]
feeders = data["feeders"]

# Load only specific datasets
data = load_all(["substations", "feeders", "load_profiles"])
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
