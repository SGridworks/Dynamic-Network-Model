"""Integration checks for the DNM wildfire substrate."""

from __future__ import annotations

import pandas as pd

from demo_data.load_demo_data import (
    load_asset_vegetation_proximity,
    load_all,
    load_fire_history,
    load_fire_weather_indices,
    load_fuel_models,
    load_fuel_moisture,
    load_psps_events,
    load_terrain,
    load_wind_direction,
)


def test_all_wildfire_loaders_return_nonempty_frames():
    loaders = {
        "fuel_models": load_fuel_models,
        "terrain": load_terrain,
        "fuel_moisture": load_fuel_moisture,
        "wind_direction": load_wind_direction,
        "fire_weather_indices": load_fire_weather_indices,
        "fire_history": load_fire_history,
        "asset_vegetation_proximity": load_asset_vegetation_proximity,
        "psps_events": load_psps_events,
    }

    for name, loader in loaders.items():
        df = loader()
        assert isinstance(df, pd.DataFrame), name
        assert not df.empty, name


def test_load_all_can_select_wildfire_datasets():
    data = load_all(["fuel_models", "terrain", "fire_weather_indices", "psps_events"])

    assert set(data) == {"fuel_models", "terrain", "fire_weather_indices", "psps_events"}
    assert all(not frame.empty for frame in data.values())


def test_wildfire_cross_references_are_valid():
    fuel_models = load_fuel_models()
    terrain = load_terrain()
    fire_weather = load_fire_weather_indices()
    asset_proximity = load_asset_vegetation_proximity()

    fuel_cells = set(fuel_models["cell_id"])
    assert set(terrain["cell_id"]).issubset(fuel_cells)
    assert set(fire_weather["cell_id"]).issubset(fuel_cells)
    assert set(asset_proximity["nearest_veg_cell_id"]).issubset(fuel_cells)
    assert fuel_models["cell_id"].is_unique
    assert terrain["cell_id"].is_unique
    assert asset_proximity["asset_id"].is_unique


def test_wildfire_plausibility_checks():
    moisture = load_fuel_moisture()
    fire_weather = load_fire_weather_indices()
    fire_history = load_fire_history()
    psps_events = load_psps_events()

    fire_weather["month"] = pd.to_datetime(fire_weather["timestamp"]).dt.month
    red_flags_by_month = fire_weather.groupby("month")["red_flag_flag"].sum()
    assert red_flags_by_month.loc[[7, 8, 9]].sum() > 0
    assert red_flags_by_month.drop(index=[7, 8, 9], errors="ignore").sum() == 0

    moisture["month"] = pd.to_datetime(moisture["date"]).dt.month
    summer_dead = moisture.loc[moisture["month"].isin([6, 7, 8]), "fm_100h_pct"].mean()
    winter_dead = moisture.loc[moisture["month"].isin([1, 2, 12]), "fm_100h_pct"].mean()
    assert summer_dead <= winter_dead

    years = pd.to_datetime(fire_history["timestamp"]).dt.year
    ignition_rate = fire_history.groupby(years).size()
    assert ignition_rate.between(8, 15).all()
    assert len(psps_events) >= 18
    assert psps_events["customers_deenergized"].gt(0).all()
