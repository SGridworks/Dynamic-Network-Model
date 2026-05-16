"""Validation tests for the synthetic fuel moisture dataset."""

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
    / "fuel_moisture.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("fuel_moisture_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_generate_fuel_moisture_schema_and_ranges(tmp_path):
    module = load_module()
    output_path = tmp_path / "fuel_moisture_daily.parquet"

    df = module.generate_fuel_moisture(n_days=90, seed=42, output_path=output_path)

    assert output_path.exists()
    assert list(df.columns) == [
        "date",
        "temp_f",
        "rh_pct",
        "emc_pct",
        "fm_1h_pct",
        "fm_10h_pct",
        "fm_100h_pct",
        "live_herb_pct",
        "live_woody_pct",
    ]
    assert len(df) == 90
    assert df["date"].is_monotonic_increasing
    assert df["temp_f"].between(30.0, 140.0).all()
    assert df["rh_pct"].between(5.0, 95.0).all()
    assert df["emc_pct"].between(0.0, 40.0).all()
    assert df["fm_1h_pct"].between(1.0, 35.0).all()
    assert df["fm_10h_pct"].between(1.0, 35.0).all()
    assert df["fm_100h_pct"].between(2.0, 30.0).all()
    assert df["live_herb_pct"].between(30.0, 200.0).all()
    assert df["live_woody_pct"].between(50.0, 200.0).all()


def test_generate_fuel_moisture_reproducible(tmp_path):
    module = load_module()

    first = module.generate_fuel_moisture(
        n_days=60,
        seed=7,
        output_path=tmp_path / "first.parquet",
    )
    second = module.generate_fuel_moisture(
        n_days=60,
        seed=7,
        output_path=tmp_path / "second.parquet",
    )

    pd.testing.assert_frame_equal(first, second)


def test_generate_fuel_moisture_row_count(tmp_path):
    module = load_module()
    df = module.generate_fuel_moisture(
        n_days=365, seed=0, output_path=tmp_path / "year.parquet"
    )
    assert len(df) == 365


def test_generate_fuel_moisture_daily_cadence(tmp_path):
    module = load_module()
    df = module.generate_fuel_moisture(
        n_days=30, seed=1, output_path=tmp_path / "month.parquet"
    )
    diffs = pd.to_datetime(df["date"]).diff().dropna()
    assert (diffs == pd.Timedelta("1D")).all()


def test_10h_lags_100h_moisture(tmp_path):
    """10-h fuel variance should exceed 100-h fuel variance (faster tracking)."""
    module = load_module()
    df = module.generate_fuel_moisture(
        n_days=365, seed=3, output_path=tmp_path / "lag.parquet"
    )
    assert df["fm_10h_pct"].std() >= df["fm_100h_pct"].std()


def test_load_fuel_moisture(tmp_path):
    module = load_module()
    output_path = tmp_path / "fuel_moisture_daily.parquet"
    generated = module.generate_fuel_moisture(n_days=20, seed=11, output_path=output_path)

    loaded = module.load_fuel_moisture(output_path)

    pd.testing.assert_frame_equal(generated, loaded)


def test_load_fuel_moisture_missing_file(tmp_path):
    module = load_module()

    with pytest.raises(FileNotFoundError):
        module.load_fuel_moisture(tmp_path / "missing.parquet")


def test_invalid_n_days(tmp_path):
    module = load_module()

    with pytest.raises(ValueError):
        module.generate_fuel_moisture(n_days=0, output_path=tmp_path / "x.parquet")
