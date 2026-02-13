# Sisyphean Power & Light - ML Playground Dataset

**Dataset Version:** 2.0 (Restructured for ML Playground Guides)
**Date:** February 12, 2026
**Restructured From:** Dynamic Network Model v1.0

---

## Overview

This dataset has been restructured to match the exact file structure, schemas, and requirements of the **ML Playground guides** on sgridworks.com. All 16 guides (01-16) can now run without modification.

---

## ⚠️ LEGAL DISCLAIMER - SYNTHETIC DATA

**This dataset contains ENTIRELY SYNTHETIC data for educational purposes only.**

- **NO REAL UTILITY DATA:** All customer, load, outage, and network data is computer-generated and bears no relation to actual utility operations. No real customer information, operational data, or confidential utility information is included.

- **FICTIONAL COORDINATES:** While coordinates fall within the general Phoenix, AZ geographic area for educational realism, they have been **offset from real locations** and DO NOT represent actual utility infrastructure. The network topology is simplified (1,000 buses vs 40,000+ in real systems). Any resemblance to real substations, feeders, or equipment locations is purely coincidental.

- **NOT FOR OPERATIONAL USE:** This data is for machine learning education and experimentation only. Do not use for actual utility planning, operations, infrastructure analysis, or critical decision-making.

- **CRITICAL INFRASTRUCTURE NOTICE:** This synthetic dataset is not derived from, and does not represent, any actual critical infrastructure. It should not be treated as sensitive, classified, or confidential information.

- **SISYPHEAN POWER & LIGHT IS FICTIONAL:** No utility operates under this name. The name references the Greek myth of Sisyphus and is used purely for educational storytelling.

**For questions or concerns:** adam@sgridworks.com

---

## Dataset Structure

```
sisyphean-power-and-light/
├── outages/
│   ├── outage_events.csv          # 3,247 outage events (2020-2025)
│   ├── crew_dispatch.csv          # 3,247 crew response records
│   └── reliability_metrics.csv    # 6 years of SAIFI/SAIDI/CAIDI metrics
│
├── weather/
│   └── hourly_observations.csv    # 52,608 hourly weather records (2020-2025)
│
├── assets/
│   ├── transformers.csv           # 21,545 distribution transformers
│   ├── maintenance_log.csv        # 10,002 maintenance inspection records
│   └── switches.csv               # 200 switching devices
│
├── network/
│   ├── master.dss                 # OpenDSS main coordination file
│   ├── lines.dss                  # 1,000 distribution line segments
│   ├── transformers.dss           # 500 distribution transformers
│   ├── loads.dss                  # 500 customer loads
│   ├── capacitors.dss             # 5 capacitor banks
│   ├── coordinates.dss            # 1,000 bus coordinates (OpenDSS format)
│   ├── coordinates.csv            # 1,000 bus coordinates (CSV format)
│   ├── feeder_summary.csv         # 65 feeders with capacity and customers
│   └── loads_summary.csv          # 1,000 buses with load allocations
│
├── timeseries/
│   ├── substation_load_hourly.parquet    # 174,720 hourly load records
│   └── ami_15min_sample.parquet          # 336,000 AMI 15-minute readings
│
└── scenarios/
    ├── baseline_2025.json         # Baseline DER scenario
    ├── high_der_2030.json         # High DER adoption scenario
    ├── ev_adoption_2030.json      # Accelerated EV adoption scenario
    └── extreme_weather.json       # 10-year extreme weather stress test
```

**Total Files:** 22
**Total Records:** ~600,000+ across all files

---

## Quick Start

### For ML Playground Guides

Set the `DATA_DIR` variable to point to this directory:

```python
DATA_DIR = "/path/to/sisyphean-power-and-light/"
```

All 16 guides will work immediately without modification.

### For OpenDSS Power Flow

```python
import opendssdirect as dss

dss.Text.Command("Compile /path/to/sisyphean-power-and-light/network/master.dss")
print(f"Circuit: {dss.Circuit.Name()}")
print(f"Buses: {dss.Circuit.NumBuses()}")
```

---

## Data Characteristics

### Temporal Coverage
- **Outage Events:** 2020-2025 (expanded from original 415 to 3,247 events)
- **Weather:** 2020-01-01 to 2025-12-31 (52,608 hourly records)
- **Load Profiles:** 2024 (174,720 records across 65 feeders)
- **AMI Data:** 2024-07-15 to 2024-07-21 (336,000 15-minute records)

### Cause Code Distribution
- equipment_failure: 50%
- weather: 16%
- overload: 14%
- animal_contact: 13%
- vegetation: 7%

### Transformer Health Metrics (NEW)
- **health_index:** 1-5 scale (1=Poor, 5=Excellent)
- **condition_score:** 0-100 scale
- **type:** oil (71%) or dry (29%)
- **Age range:** 1-45 years

### Weather Data (ENHANCED)
- **precipitation:** Added (Phoenix monsoon patterns)
- **temperature:** Fahrenheit (44-134°F)
- **wind_speed:** mph
- **humidity:** percentage

---

## Changes from Original Dataset

### Schema Changes

#### outage_events.csv
- `start_time` → `fault_detected`
- `end_time` → `service_restored`
- `cause` → `cause_code` (mapped to 5 standard categories)
- `customers_affected` → `affected_customers`
- **Expanded:** 415 → 3,247 outages

#### weather/hourly_observations.csv
- `temperature_f` → `temperature`
- `humidity_pct` → `humidity`
- `wind_speed_mph` → `wind_speed`
- **Added:** `precipitation` column (was missing)
- **Expanded:** 2024 only → 2020-2025 (8,760 → 52,608 rows)

#### assets/transformers.csv
- `rated_kva` → `kva_rating`
- **Added:** `health_index` (1-5 scale)
- **Added:** `condition_score` (0-100)
- **Added:** `install_year` (calculated from age_years)
- **Added:** `type` (oil/dry distribution)

#### timeseries/substation_load_hourly
- **Format:** CSV → Parquet
- `load_mw` → `total_load_mw`
- **Added:** `residential_mw`, `commercial_mw`, `industrial_mw` (class breakdowns)
- **Added:** `customer_count` (merged from feeders.csv)

### Files Added
- ✅ `outages/crew_dispatch.csv` (3,247 records)
- ✅ `outages/reliability_metrics.csv` (6 years)
- ✅ `assets/maintenance_log.csv` (10,002 records)
- ✅ `assets/switches.csv` (200 switches)
- ✅ `network/*.dss` (OpenDSS model files)
- ✅ `network/coordinates.csv` (1,000 buses)
- ✅ `network/feeder_summary.csv` (65 feeders)
- ✅ `network/loads_summary.csv` (1,000 buses)
- ✅ `scenarios/*.json` (4 scenario files)
- ✅ `timeseries/ami_15min_sample.parquet` (336,000 records)

---

## Guide Compatibility

| Guide | Status | Key Files Used |
|-------|--------|----------------|
| 01 - Outage Prediction | ✅ Ready | outages/outage_events.csv, weather/hourly_observations.csv |
| 02 - Load Forecasting | ✅ Ready | timeseries/substation_load_hourly.parquet |
| 03 - Hosting Capacity | ✅ Ready | network/master.dss, network/coordinates.csv |
| 04 - Predictive Maintenance | ✅ Ready | assets/transformers.csv, assets/maintenance_log.csv |
| 05 - FLISR Restoration | ✅ Ready | assets/switches.csv, outages/crew_dispatch.csv |
| 06 - Volt-VAR Optimization | ✅ Ready | network/master.dss, network/capacitors.dss |
| 07 - DER Scenario Planning | ✅ Ready | scenarios/*.json, network/feeder_summary.csv |
| 08 - Anomaly Detection | ✅ Ready | timeseries/ami_15min_sample.parquet |
| 09 - Advanced Outage Prediction | ✅ Ready | Inherits from Guide 01 |
| 10 - LSTM Load Forecasting | ✅ Ready | Inherits from Guide 02 |
| 11 - ML Hosting Capacity | ✅ Ready | network/coordinates.csv |
| 12 - Survival Analysis | ✅ Ready | assets/maintenance_log.csv |
| 13 - RL Service Restoration | ✅ Ready | assets/switches.csv |
| 14 - Deep RL Volt-VAR | ✅ Ready | network/capacitors.dss |
| 15 - Stochastic Planning | ✅ Ready | scenarios/*.json |
| 16 - VAE Anomaly Detection | ✅ Ready | timeseries/ami_15min_sample.parquet |

**Compatibility:** 16/16 guides (100%) ready to run

---

## Data Generation

All data was programmatically restructured from the Dynamic Network Model v1.0 dataset using deterministic scripts with `random_state=42` for reproducibility.

### Synthetic Data Additions
- **Outage expansion:** Replicated 415 base outages with time shifts and variations → 3,247
- **Weather backfill:** Sampled existing 2024 patterns by month → 2020-2025
- **Precipitation:** Generated based on Phoenix monsoon seasonality
- **Health metrics:** Correlated with transformer age and realistic distributions
- **Maintenance logs:** Generated 1-3 records per transformer with realistic patterns

### Scripts Available
All conversion scripts are available in the repository root:
- `convert_outage_data.py`
- `convert_weather_data.py`
- `convert_transformer_data.py`
- `convert_load_profiles.py`
- `generate_opendss_model.py`
- `create_missing_files.py`

---

## Known Limitations

### OpenDSS Model
- Simplified to 1,000 line segments (full model has 43,826 edges)
- 500 transformers sampled (full dataset has 21,545)
- Suitable for educational use; production analysis should use full topology

### Temporal Data
- Load profiles cover 2024 only (could be extended)
- AMI data covers 1 week (July 15-21, 2024)
- Outage time shifts may create unrealistic seasonal patterns

### Synthetic Additions
- Maintenance logs are statistically realistic but not real events
- Crew dispatch times use uniform distributions
- Health metrics correlate with age but lack real degradation curves

---

## Validation

This restructured dataset passed comprehensive validation:
- ✅ All file paths match ML Playground guide expectations
- ✅ All column schemas match guide requirements
- ✅ Row counts meet or exceed minimums (3,247 vs 3,200 outages, etc.)
- ✅ Date ranges span 2020-2025 as required
- ✅ OpenDSS model compiles without errors
- ✅ Parquet files load correctly
- ✅ JSON scenarios parse correctly
- ✅ All technical fixes (Guides 01-07) validated

**Validation Report:** See `DATASET_VALIDATION_REPORT_2026-02-12.md`

---

## Citation

When using this dataset, please cite:

```
Sisyphean Power & Light Dataset v2.0 (Restructured for ML Playground)
Sisyphean Gridworks, 2026
Derived from: Dynamic Network Model v1.0
https://github.com/SGridworks/Dynamic-Network-Model
```

---

## License

This synthetic dataset is provided for educational and experimental use. Sisyphean Power & Light is a fictional entity. No real utility data is included.

---

## Support

- **Issues:** https://github.com/SGridworks/Dynamic-Network-Model/issues
- **Email:** adam@sgridworks.com
- **Documentation:** https://sgridworks.com/ml-playground

---

*Dataset restructured on 2026-02-12 to match ML Playground guide requirements.*
*All 16 guides validated and ready to run.*
