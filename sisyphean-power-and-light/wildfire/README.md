# SP&L Wildfire Substrate

Sisyphean Power & Light is fictional synthetic utility data. This wildfire pillar extends the Dynamic Network Model with fictional Sonoran desert scrub, suburban WUI, invasive grassland, and scattered chaparral-pocket conditions over the existing Phoenix-offset footprint.

The datasets are generated for open research notebooks and examples. They are not real ecology, utility operations, fire history, or public-safety data.

## Datasets

| Dataset | Rows | Primary columns |
| --- | ---: | --- |
| `fuel_models.parquet` | 4,900 | `cell_id`, `lat`, `lon`, `fbfm_code`, `fuel_load_tons_per_acre`, `canopy_cover_pct`, `canopy_height_m`, `biome` |
| `terrain.parquet` | 4,900 | `cell_id`, `elevation_m`, `slope_deg`, `aspect_deg`, `ruggedness_index` |
| `fuel_moisture_daily.parquet` | 365 | `date`, `temp_f`, `rh_pct`, `emc_pct`, `fm_1h_pct`, `fm_10h_pct`, `fm_100h_pct`, `live_herb_pct`, `live_woody_pct` |
| `wind_direction_hourly.parquet` | 52,608 | `timestamp`, `station_id`, `wind_direction_deg`, `wind_gust_mph`, `wind_steadiness` |
| `fire_weather_indices_hourly.parquet` | 2,807,040 | `timestamp`, `cell_id`, `erc`, `bi`, `kbdi`, `ffwi`, `red_flag_flag` |
| `fire_history.parquet` | 120 | `ignition_id`, `timestamp`, `lat`, `lon`, `cause`, `final_acres`, `suppression_hours`, `structures_lost`, `outage_event_id` |
| `asset_vegetation_proximity.parquet` | 47,538 | `asset_id`, `asset_type`, `nearest_veg_cell_id`, `distance_m`, `clearance_class`, `last_patrol_date`, `last_trim_date` |
| `psps_events.parquet` | 28 | `event_id`, `start_time`, `end_time`, `feeder_ids`, `customers_deenergized`, `peak_wind_mph`, `peak_erc`, `decision_rationale`, `post_event_ignitions_avoided_est` |

## Generation Assumptions

- Fuel cells are a 70 by 70 grid over the synthetic SP&L service footprint.
- Terrain is a synthetic relief surface aligned to fuel cells, with higher ruggedness on invented northwestern and eastern corridors.
- Fuel moisture is daily and system-wide for the first release. Fire-weather indices join it by date, then apply cell-level fuel and biome factors.
- Wind direction extends the existing hourly weather feed with generated direction, gust, and steadiness fields.
- Fire-weather indices cover 2024-2025 hourly weather over 160 representative cells. This keeps the parquet small enough for local notebooks while preserving cell-level variation.
- Ignition history spans 2015-2025 at 8-15 events per year. Causes are normalized to `powerline`, `lightning`, `human`, and `unknown`; some powerline events can reference vegetation outage rows when available.
- Asset vegetation proximity covers transformers, overhead line spans, and synthetic poles placed along feeder routes.
- PSPS events span 2020-2025 at 3-6 events per year and include feeder lists for decision-support backtests.

## Loaders

All wildfire datasets are available through `demo_data.load_demo_data`:

```python
from demo_data.load_demo_data import (
    load_asset_vegetation_proximity,
    load_fire_history,
    load_fire_weather_indices,
    load_fuel_models,
    load_fuel_moisture,
    load_psps_events,
    load_terrain,
    load_wind_direction,
)
```

## Validation

Run the wildfire validation suite from the repository root:

```bash
python -m pytest tests/wildfire/
```

The integration test checks that all eight loaders return data, cell references resolve to `fuel_models.parquet`, red-flag records occur in summer, fuel moisture is seasonally plausible, fire history stays within the intended annual ignition-rate range, and PSPS events have positive customer impact.
