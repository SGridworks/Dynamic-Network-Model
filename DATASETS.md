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
