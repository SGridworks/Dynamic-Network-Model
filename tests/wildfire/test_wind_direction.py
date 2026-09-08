"""Validation tests for the synthetic wind direction dataset."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = (
    REPO_ROOT / "sisyphean-power-and-light" / "wildfire" / "generators" / "wind_direction.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("wind_direction_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_weather(tmp_path: Path) -> Path:
    weather = pd.DataFrame(
        {
            "timestamp": ["2024-01-01 00:00:00", "2024-01-01 01:00:00"],
            "wind_speed": [8.0, 14.0],
        }
    )
    path = tmp_path / "weather.csv"
    weather.to_csv(path, index=False)
    return path


def test_generate_wind_direction_schema_and_ranges(tmp_path):
    module = load_module()
    output_path = tmp_path / "wind_direction_hourly.parquet"

    df = module.generate_wind_direction(
        weather_path=write_weather(tmp_path),
        output_path=output_path,
    )

    assert output_path.exists()
    assert list(df.columns) == [
        "timestamp",
        "station_id",
        "wind_direction_deg",
        "wind_gust_mph",
        "wind_steadiness",
    ]
    assert len(df) == 2
    assert df["station_id"].eq("WX-001").all()
    assert df["wind_direction_deg"].between(0, 360).all()
    assert df["wind_gust_mph"].between(1, 65).all()
    assert df["wind_steadiness"].between(0.35, 0.98).all()


def test_load_wind_direction(tmp_path):
    module = load_module()
    output_path = tmp_path / "wind_direction_hourly.parquet"
    generated = module.generate_wind_direction(
        weather_path=write_weather(tmp_path),
        output_path=output_path,
    )

    loaded = module.load_wind_direction(output_path)

    pd.testing.assert_frame_equal(generated, loaded)


def test_load_wind_direction_missing_file(tmp_path):
    module = load_module()

    with pytest.raises(FileNotFoundError):
        module.load_wind_direction(tmp_path / "missing.parquet")
