# Sisyphean Power & Light — Dataset Reference

## Overview

The repository contains two versions of the synthetic dataset:

| Version | Directory | Format | Description |
|---------|-----------|--------|-------------|
| **V1** | `demo_data/` | CSV / CSV.GZ | Original flat-file format with guide-friendly column names |
| **V2** | `sisyphean-power-and-light/` | CSV + Parquet | Restructured dataset with realistic column names and additional data |

## The Adapter Layer

The file `demo_data/load_demo_data.py` serves as the **adapter** between V2 data and the ML Playground guides.

**How it works:**
1. If the `sisyphean-power-and-light/` directory exists, core datasets (outages, weather, transformers, load profiles, AMI) are read from V2 files
2. Columns are automatically renamed to match the guide-friendly API contract
3. Derived columns (duration_hours, is_storm, etc.) are computed on the fly
4. If V2 is not found, all data is read from V1 CSV files as a fallback
5. Network, solar, EV, battery, and scenario datasets always read from V1

## Column Mapping

### `load_outage_history()`

| V2 Column (outage_events.csv) | Adapter Output | Notes |
|-------------------------------|----------------|-------|
| `fault_detected` | `start_time` | Renamed, parsed as datetime |
| `service_restored` | `end_time` | Renamed, parsed as datetime |
| `cause_code` | `cause` | Renamed |
| `affected_customers` | `customers_affected` | Renamed |
| `feeder_id` | `feeder_id` | Pass through |
| `transformer_id` | `equipment_involved` | Renamed |
| _(computed)_ | `duration_hours` | `(end_time - start_time) / 3600` |
| _(computed)_ | `weather_related` | `cause == "weather"` |
| _(derived)_ | `substation_id` | From feeder_id mapping |

Index: `outage_id` (generated sequential OUT-00001, etc.)

### `load_weather_data()`

| V2 Column (hourly_observations.csv) | Adapter Output | Notes |
|--------------------------------------|----------------|-------|
| `timestamp` | `timestamp` | Pass through |
| `temperature` | `temperature_f` | Renamed (units are Fahrenheit) |
| `wind_speed` | `wind_speed_mph` | Renamed |
| `humidity` | `humidity_pct` | Renamed |
| `precipitation` | `precipitation` | Pass through |
| _(computed)_ | `is_storm` | `precipitation > 0.1 OR wind_speed_mph > 35` |
| _(computed)_ | `is_heatwave` | Rolling 3-hour window where `temperature_f > 110` |

### `load_transformers()`

| V2 Column (transformers.csv) | Adapter Output | Notes |
|------------------------------|----------------|-------|
| `transformer_id` | `transformer_id` | Set as index |
| `feeder_id` | `feeder_id` | Pass through |
| `kva_rating` | `rated_kva` | Renamed |
| `age_years` | `age_years` | Pass through |
| `manufacturer` | `manufacturer` | Pass through |
| `health_index` | `health_index` | Pass through (V2 only) |
| `condition_score` | `condition_score` | Pass through (V2 only) |
| `install_year` | `install_year` | Pass through |
| `type` | `type` | Pass through |
| _(derived)_ | `substation_id` | From feeder_id mapping |
| _(derived)_ | `status`, `phase`, `primary_voltage_kv`, etc. | Generated defaults |

### `load_load_profiles()`

| V2 Column (substation_load_hourly.parquet) | Adapter Output | Notes |
|--------------------------------------------|----------------|-------|
| `timestamp` | `timestamp` | Pass through |
| `feeder_id` | `feeder_id` | Pass through |
| `total_load_mw` | `load_mw` | Renamed |
| _(derived)_ | `substation_id` | From feeder_id mapping |
| _(derived)_ | `load_mvar` | `load_mw * 0.3` |
| _(derived)_ | `voltage_pu` | `1.0 + noise` |
| _(derived)_ | `power_factor` | `0.95 + noise`, clipped to [0.85, 1.0] |

### `load_customer_interval_data()`

No renames needed — V2 columns already match guide expectations.

### Unchanged Loaders (always read from V1)

These functions always read from `demo_data/` regardless of V2 presence:

- `load_network_nodes()` — V2 uses OpenDSS `.dss` format, incompatible with DataFrame API
- `load_network_edges()` — Same as above
- `load_substations()`
- `load_feeders()`
- `load_customers()`
- `load_solar_installations()`
- `load_solar_profiles()`
- `load_ev_chargers()`
- `load_ev_charging_profiles()`
- `load_battery_installations()`
- `load_growth_scenarios()`

## Usage

```python
from demo_data.load_demo_data import load_outage_history, load_weather_data, summary

# Print dataset summary
summary()

# Load individual datasets
outages = load_outage_history()
print(outages.columns)
# Index: outage_id
# Columns: start_time, end_time, cause, customers_affected, feeder_id,
#           equipment_involved, duration_hours, weather_related, substation_id
```

---

## Generation Dataset (sisyphean-power-and-light/generation/)

One year of 1-minute operational data for the Boiler Feed Pump (BFP) train at SP&L Generating Station 1, a 300 MW 2x1 CCGT. Two 100% capacity motor-driven BFPs (KSB CHTD 8/6, 8-stage barrel-casing pumps driven by ABB 1800 kW 6.6 kV motors) with embedded fault degradation scenarios for predictive maintenance and anomaly detection work.

### File Inventory

#### Timeseries

| File | Rows | Columns | Resolution | Description |
|------|------|---------|------------|-------------|
| `timeseries/bfp_train_1min.parquet` | 527,040 | 88 | 1-minute | Full-resolution operational data, 2024-01-01 to 2024-12-31 |
| `timeseries/bfp_train_15min.parquet` | 35,136 | 88 | 15-minute | Mean rollup of 1-minute data |
| `timeseries/bfp_train_hourly.parquet` | 8,784 | 88 | Hourly | Mean rollup of 1-minute data |

#### Events

| File | Description |
|------|-------------|
| `events/alarm_log.csv` | 71 alarm events with ACTIVE/CLEARED pairs. Columns: `timestamp`, `equipment`, `alarm_code`, `message`, `state` |
| `events/trip_log.csv` | 1 trip event (BFP-B NDE bearing, Aug 20). Columns: `timestamp`, `equipment`, `trip_code`, `description`, `trigger_tag`, `trigger_value` |
| `events/operator_actions.csv` | 7 operator actions (pump start/stop/swap, unit shutdown/start). Columns: `timestamp`, `equipment`, `action`, `description` |

#### Reference

| File | Description |
|------|-------------|
| `reference/pump_curves.csv` | 27-point manufacturer pump curves. Columns: `flow_tph`, `flow_pct_bep`, `head_bar`, `efficiency_pct`, `power_kw`, `npsh_required_m` |
| `reference/heat_balance.csv` | 15-point unit load vs. BFP operating conditions. Columns: `unit_mw`, `unit_pct`, `fw_flow_tph`, `fw_temp_c`, `bfp_dp_bar`, `bfp_power_kw`, `hp_drum_press_barg` |
| `reference/design_parameters.json` | Full equipment specs, alarm/trip setpoints, and fault scenario definitions. Nested keys: `plant`, `bfp`, `alarm_setpoints`, `fault_scenarios_embedded` |

#### Metadata

| File | Description |
|------|-------------|
| `equipment_registry.csv` | 6 equipment records (2 pumps, 2 motors, 2 LO skids). Columns: `equipment_id`, `name`, `type`, `oem`, `model`, `serial`, `install_year`, `rated_power_kw`, `rated_speed_rpm`, `rated_flow_tph`, `rated_dp_bar`, `parent_system` |
| `tag_dictionary.csv` | 88 tag definitions. Columns: `tag_id`, `description`, `units`, `range_min`, `range_max`, `scan_rate_sec`, `pump` |

### Column Naming Convention

All 88 timeseries columns use flat PI-style tag names: `U1_BFPA_TAGNAME`.

| Prefix | Count | Scope |
|--------|-------|-------|
| `U1_BFPA_*` | 36 | BFP-A pump, motor, bearings, seals, lube oil, valves, status |
| `U1_BFPB_*` | 36 | BFP-B pump, motor, bearings, seals, lube oil, valves, status |
| `U1_*` (system) | 14 | FW header, unit MW, GT/ST loads, DA boundary, ambient, CW temp |
| **Total** | **88** | |

### Key Columns

**Process (per pump, shown for BFPA):**

| Column | Units | Description |
|--------|-------|-------------|
| `U1_BFPA_SUCT_PRESS` | bar(g) | Suction pressure |
| `U1_BFPA_DISCH_PRESS` | bar(g) | Discharge pressure |
| `U1_BFPA_DIFF_PRESS` | bar | Differential pressure |
| `U1_BFPA_FW_FLOW` | t/hr | Feedwater flow |
| `U1_BFPA_RECIRC_FLOW` | t/hr | Recirculation flow |
| `U1_BFPA_SPEED` | RPM | Pump speed |
| `U1_BFPA_MTR_CURRENT` | A | Motor current |
| `U1_BFPA_MTR_POWER` | kW | Motor power |

**Condition monitoring (per pump, shown for BFPA):**

| Column | Units | Description |
|--------|-------|-------------|
| `U1_BFPA_BRG_DE_TEMP` | degC | DE journal bearing temperature |
| `U1_BFPA_BRG_NDE_TEMP` | degC | NDE journal bearing temperature |
| `U1_BFPA_THR_ACT_TEMP` | degC | Thrust bearing active side temperature |
| `U1_BFPA_VIB_DE_X` | um pk-pk | Shaft vibration DE X-probe |
| `U1_BFPA_VIB_DE_Y` | um pk-pk | Shaft vibration DE Y-probe |
| `U1_BFPA_VIB_NDE_X` | um pk-pk | Shaft vibration NDE X-probe |
| `U1_BFPA_VIB_NDE_Y` | um pk-pk | Shaft vibration NDE Y-probe |
| `U1_BFPA_AXIAL_DISP` | mm | Axial displacement |
| `U1_BFPA_SEAL_DE_LEAK` | cc/min | DE seal leakage |
| `U1_BFPA_SEAL_DE_TEMP` | degC | DE seal chamber temperature |
| `U1_BFPA_LO_HDR_PRESS` | bar(g) | Lube oil header pressure |
| `U1_BFPA_LO_SUPPLY_TEMP` | degC | Lube oil supply temperature |

**System / boundary:**

| Column | Units | Description |
|--------|-------|-------------|
| `U1_FW_HDR_PRESS` | bar(g) | Feedwater header pressure |
| `U1_FW_HDR_TEMP` | degC | Feedwater header temperature |
| `U1_FW_HDR_FLOW` | t/hr | Total feedwater flow to HRSG |
| `U1_UNIT_MW_GROSS` | MW | Unit gross output |
| `U1_UNIT_MW_NET` | MW | Unit net output |
| `U1_GT_A_LOAD` | MW | Gas turbine A load |
| `U1_GT_B_LOAD` | MW | Gas turbine B load |
| `U1_ST_LOAD` | MW | Steam turbine load |
| `U1_DA_PRESS` | bar(g) | Deaerator pressure (boundary) |
| `U1_DA_TEMP` | degC | Deaerator temperature (boundary) |
| `U1_DA_LEVEL` | % | Deaerator level (boundary) |
| `U1_AMBIENT_TEMP` | degC | Ambient temperature |
| `U1_CW_SUPPLY_TEMP` | degC | Cooling water supply temperature |

### Embedded Fault Scenarios

| ID | Fault | Pump | Window | Key Tags |
|----|-------|------|--------|----------|
| SEAL-001 | DE seal degradation | A | Apr 1 -- Jun 1, 2024 | `SEAL_DE_LEAK`, `SEAL_DE_TEMP` |
| BRG-001 | NDE bearing wear | B | Jul 15 -- Aug 20, 2024 | `BRG_NDE_TEMP`, `VIB_NDE_X/Y` |
| ALIGN-001 | Coupling misalignment | A | Oct 15 -- Dec 31, 2024 | `VIB_DE_X/Y`, `BRG_DE_TEMP` |

### SP&L Integration

- `U1_UNIT_MW_GROSS` follows the same diurnal/seasonal demand patterns as `timeseries/substation_load_hourly.parquet`
- Timestamps share the 2024 calendar year with load profile and AMI data
- `U1_AMBIENT_TEMP` correlates with `weather/hourly_observations.csv`
- Unit 1 serves approximately 65% of SP&L system peak demand

### Usage

```python
import pandas as pd

DATA_DIR = "/path/to/sisyphean-power-and-light/generation"

# Load hourly rollup for quick exploration
df = pd.read_parquet(f"{DATA_DIR}/timeseries/bfp_train_hourly.parquet")
tags = pd.read_csv(f"{DATA_DIR}/tag_dictionary.csv")

# Filter to BFP-A condition monitoring tags
bfpa_cm = [t for t in df.columns if "BFPA" in t and any(
    k in t for k in ["BRG", "VIB", "SEAL", "THR", "AXIAL"]
)]
print(df[bfpa_cm].describe())
```
