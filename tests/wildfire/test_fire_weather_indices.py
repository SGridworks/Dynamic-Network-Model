"""Validation tests for synthetic hourly fire-weather indices."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = (
    REPO_ROOT
    / "sisyphean-power-and-light"
    / "wildfire"
    / "generators"
    / "fire_weather_indices.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("fire_weather_indices_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_fixture_inputs(tmp_path: Path) -> dict[str, Path]:
    fuels = pd.DataFrame(
        {
            "cell_id": ["FUEL-00001", "FUEL-00002", "FUEL-00003", "FUEL-00004"],
            "lat": [33.50, 33.51, 33.52, 33.53],
            "lon": [-112.10, -112.11, -112.12, -112.13],
            "fbfm_code": [5, 8, 3, 13],
            "fuel_load_tons_per_acre": [1.2, 0.8, 1.1, 6.2],
            "canopy_cover_pct": [16.0, 10.0, 5.0, 62.0],
            "canopy_height_m": [1.0, 0.8, 0.4, 3.2],
            "biome": ["desert-scrub", "wui", "grassland", "chaparral-pocket"],
        }
    )
    weather = pd.DataFrame(
        {
            "timestamp": ["2024-01-15 12:00:00", "2024-07-15 15:00:00"],
            "temperature": [58.0, 109.0],
            "wind_speed": [8.0, 32.0],
            "precipitation": [0.15, 0.0],
            "humidity": [55.0, 12.0],
        }
    )
    moisture = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-15", "2024-07-15"]),
            "dead_1hr": [8.0, 2.2],
            "dead_10hr": [10.0, 3.0],
            "dead_100hr": [13.0, 4.4],
            "live_herbaceous": [150.0, 42.0],
            "live_woody": [145.0, 61.0],
        }
    )

    paths = {
        "fuel_models_path": tmp_path / "fuel_models.parquet",
        "weather_path": tmp_path / "weather.csv",
        "fuel_moisture_path": tmp_path / "fuel_moisture_daily.parquet",
    }
    fuels.to_parquet(paths["fuel_models_path"], index=False)
    weather.to_csv(paths["weather_path"], index=False)
    moisture.to_parquet(paths["fuel_moisture_path"], index=False)
    return paths


def test_generate_fire_weather_indices_schema_and_ranges(tmp_path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path)
    output_path = tmp_path / "fire_weather_indices_hourly.parquet"

    df = module.generate_fire_weather_indices(
        **paths,
        output_path=output_path,
        start="2024-01-01",
        end="2024-12-31 23:00:00",
        max_cells=4,
    )

    assert output_path.exists()
    assert list(df.columns) == [
        "timestamp",
        "cell_id",
        "erc",
        "bi",
        "kbdi",
        "ffwi",
        "red_flag_flag",
    ]
    assert len(df) == 8
    assert df["cell_id"].str.match(r"^FUEL-\d{5}$").all()
    assert df["erc"].between(0, 100).all()
    assert df["bi"].between(0, 120).all()
    assert df["kbdi"].between(0, 800).all()
    assert df["ffwi"].between(0, 50).all()
    assert df["red_flag_flag"].dtype == bool


def test_red_flags_prefer_hot_dry_windy_hours(tmp_path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path)

    df = module.generate_fire_weather_indices(
        **paths,
        output_path=tmp_path / "indices.parquet",
        start="2024-01-01",
        end="2024-12-31 23:00:00",
        max_cells=4,
    )
    df["month"] = pd.to_datetime(df["timestamp"]).dt.month

    assert not df.loc[df["month"] == 1, "red_flag_flag"].any()
    assert df.loc[df["month"] == 7, "red_flag_flag"].any()
    assert df.loc[df["month"] == 7, "erc"].mean() > df.loc[df["month"] == 1, "erc"].mean()


def test_generate_fire_weather_indices_reproducible(tmp_path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path)

    first = module.generate_fire_weather_indices(
        **paths,
        output_path=tmp_path / "first.parquet",
        start="2024-01-01",
        end="2024-12-31 23:00:00",
        max_cells=3,
        seed=7,
    )
    second = module.generate_fire_weather_indices(
        **paths,
        output_path=tmp_path / "second.parquet",
        start="2024-01-01",
        end="2024-12-31 23:00:00",
        max_cells=3,
        seed=7,
    )

    pd.testing.assert_frame_equal(first, second)


def test_load_fire_weather_indices(tmp_path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path)
    output_path = tmp_path / "fire_weather_indices_hourly.parquet"
    generated = module.generate_fire_weather_indices(
        **paths,
        output_path=output_path,
        start="2024-01-01",
        end="2024-12-31 23:00:00",
        max_cells=4,
    )

    loaded = module.load_fire_weather_indices(output_path)

    pd.testing.assert_frame_equal(generated, loaded)


def test_load_fire_weather_indices_missing_file(tmp_path):
    module = load_module()

    with pytest.raises(FileNotFoundError):
        module.load_fire_weather_indices(tmp_path / "missing.parquet")


def test_missing_weather_columns(tmp_path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path)
    pd.DataFrame({"timestamp": ["2024-01-01 00:00:00"]}).to_csv(
        paths["weather_path"], index=False
    )

    with pytest.raises(ValueError):
        module.generate_fire_weather_indices(
            **paths,
            output_path=tmp_path / "bad.parquet",
            start="2024-01-01",
            end="2024-12-31 23:00:00",
            max_cells=4,
        )
