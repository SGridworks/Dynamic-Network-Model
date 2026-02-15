# Dynamic Network Model

**Scenario Planning Engine** — a lightweight distribution system model for
stress-testing against EV adoption, solar growth, heatwave scenarios, and
policy changes.

## Sisyphean Power & Light — Synthetic Utility Dataset

This repository includes a complete synthetic dataset modeled after
**Sisyphean Power & Light (SP&L)**, a fictional mid-size electric utility
serving approximately 140,500 customers across a Phoenix, AZ-area service
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

- **Load forecasting models** — 15-minute profiles across seasons with weather correlation
- **Hosting capacity analysis** — solar/EV saturation on feeders and transformers
- **Reliability analytics** — outage prediction from weather (storm/heatwave), equipment age, and load
- **Network optimization** — graph analysis on the GIS node/edge topology with switching
- **Scenario planning tools** — stress-test the grid against 5 growth projections
- **Geospatial dashboards** — coordinates aligned to Phoenix street grid, immediately mappable
- **Digital twin prototypes** — the full substation-to-meter hierarchy is modeled
- **Power flow approximations** — impedance, conductor specs, and phase data included
- **AMI analytics** — 15-minute customer interval data with realistic load shapes

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
ami = data["customer_interval_data"]
```

See [`demo_data/USERS_GUIDE.md`](demo_data/USERS_GUIDE.md) for the full
walkthrough, dataset schemas, and example analyses.

## Repository Structure

```
Dynamic-Network-Model/
├── README.md                          # This file
├── LICENSE                            # MIT License
├── CONTRIBUTING.md                    # Contribution guidelines
├── CODE_OF_CONDUCT.md                 # Community standards
├── SECURITY.md                        # Security policy
├── PLAN.md                            # Product vision & roadmap
├── COMPREHENSIVE_TEST_RESULTS.md      # ML Playground validation results
├── demo_data/                         # V1.0 dataset (original)
│   ├── USERS_GUIDE.md                 # Comprehensive guide for power engineers
│   ├── README.md                      # Dataset reference card
│   ├── generate_demo_data.py          # Deterministic data generator (seed=42)
│   ├── load_demo_data.py              # Combined data loader (pandas)
│   ├── __init__.py
│   ├── substations.csv                # 15 substations
│   ├── feeders.csv                    # 65 feeders
│   ├── transformers.csv               # 21,545 transformers
│   ├── customers.csv                  # 140,459 customers
│   ├── load_profiles.csv.gz           # 174,720 fifteen-minute load records
│   ├── customer_interval_data.csv.gz  # 336,000 AMI interval records
│   ├── solar_installations.csv        # 17,242 solar PV systems
│   ├── solar_profiles.csv             # 288 generation curves
│   ├── ev_chargers.csv                # 11,076 EV chargers
│   ├── ev_charging_profiles.csv       # 48 charging load shapes
│   ├── battery_installations.csv      # 4,180 battery storage systems
│   ├── weather_data.csv               # 43,848 hourly weather records (5 years)
│   ├── growth_scenarios.csv           # 85 scenario projections
│   ├── outage_history.csv             # 2,306 outage events (2020-2024)
│   ├── network_nodes.csv              # 43,827 GIS point features
│   └── network_edges.csv              # 43,826 GIS polyline features
├── sisyphean-power-and-light/         # V2.0 dataset (restructured for ML Playground)
│   ├── README.md                      # V2.0 documentation
│   ├── assets/                        # Transformer & switching device data
│   ├── network/                       # OpenDSS power flow model
│   ├── outages/                       # Expanded outage & crew dispatch records
│   ├── scenarios/                     # JSON scenario configurations
│   ├── timeseries/                    # Parquet load & AMI data
│   └── weather/                       # Extended weather observations
├── validate_demo_data.py              # Dataset validation suite
├── test_guide_*.py                    # ML Playground guide test scripts
├── convert_*.py                       # V1.0 → V2.0 conversion scripts
├── generate_opendss_model.py          # OpenDSS model generator
└── .github/                           # Issue/PR templates & CI
```

## License

This synthetic dataset is provided for educational and experimental use.
Sisyphean Power & Light is a fictional entity. No real utility data is
included.
