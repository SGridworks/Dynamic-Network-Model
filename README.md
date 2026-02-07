# Dynamic Network Model

**Scenario Planning Engine** — a lightweight distribution system model for
stress-testing against EV adoption, solar growth, heatwave scenarios, and
policy changes.

## Sisyphean Power & Light — Synthetic Utility Dataset

This repository includes a complete synthetic dataset modeled after
**Sisyphean Power & Light (SP&L)**, a fictional mid-size electric utility
serving approximately 166,000 customers across a Phoenix, AZ-area service
territory.

> **SYNTHETIC DATA NOTICE**
>
> Sisyphean Power & Light is an entirely fictional utility. All data in this
> repository — including customer records, network topology, load profiles,
> DER installations, and geographic coordinates — is computationally
> generated. No real customer, infrastructure, or operational data is
> included. Any resemblance to actual utilities, persons, or locations is
> coincidental. This data is provided for educational and experimental
> purposes only.

## Purpose

This project exists as a **sandbox for power engineers** who want to
experiment with machine learning, AI-enabled tools, and modern data
science techniques applied to electric distribution systems. The dataset
is specifically designed to work with tools like **Claude Code** and other
AI assistants.

Because you can just build things now.

Instead of waiting for sanitized exports from production systems, navigating
data sharing agreements, or working with toy examples that don't reflect
real-world complexity — this gives you a realistic, interconnected dataset
you can start querying, modeling, and building against immediately.

### What You Can Build

- **Load forecasting models** — hourly profiles across seasons with weather correlation
- **Hosting capacity analysis** — solar/EV saturation on feeders and transformers
- **Reliability analytics** — outage prediction from weather, equipment age, and load
- **Network optimization** — graph analysis on the GIS node/edge topology
- **Scenario planning tools** — stress-test the grid against 5 growth projections
- **Geospatial dashboards** — all coordinates are spatially rational and mappable
- **Digital twin prototypes** — the full substation-to-meter hierarchy is modeled
- **Power flow approximations** — impedance, conductor specs, and phase data included

## Quick Start

```bash
# Clone and explore
git clone <repo-url>
cd Dynamic-Network-Model

# Generate the datasets (or use the pre-generated CSVs)
python demo_data/generate_demo_data.py

# Load into Python
python -c "from demo_data.load_demo_data import summary; summary()"
```

```python
from demo_data.load_demo_data import load_all

data = load_all()
feeders = data["feeders"]
customers = data["customers"]
nodes = data["network_nodes"]
edges = data["network_edges"]
```

See [`demo_data/USERS_GUIDE.md`](demo_data/USERS_GUIDE.md) for the full
walkthrough, dataset schemas, and example analyses.

## Repository Structure

```
Dynamic-Network-Model/
├── README.md                          # This file
├── demo_data/
│   ├── USERS_GUIDE.md                 # Comprehensive guide for power engineers
│   ├── README.md                      # Dataset reference card
│   ├── generate_demo_data.py          # Deterministic data generator (seed=42)
│   ├── load_demo_data.py              # Combined data loader (pandas)
│   ├── __init__.py
│   ├── substations.csv                # 15 substations
│   ├── feeders.csv                    # 70 feeders
│   ├── transformers.csv               # 25,682 transformers
│   ├── customers.csv                  # 166,641 customers
│   ├── load_profiles.csv              # 47,040 hourly load records
│   ├── solar_installations.csv        # 20,031 solar PV systems
│   ├── solar_profiles.csv             # 288 generation curves
│   ├── ev_chargers.csv                # 13,398 EV chargers
│   ├── ev_charging_profiles.csv       # 48 charging load shapes
│   ├── weather_data.csv               # 8,760 hourly weather records
│   ├── growth_scenarios.csv           # 85 scenario projections
│   ├── outage_history.csv             # 364 outage events
│   ├── network_nodes.csv              # 26,457 GIS point features
│   └── network_edges.csv              # 26,442 GIS polyline features
└── .gitignore
```

## License

This synthetic dataset is provided for educational and experimental use.
Sisyphean Power & Light is a fictional entity. No real utility data is
included.
