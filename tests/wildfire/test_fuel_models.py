"""Validation tests for the synthetic wildfire fuel-model dataset."""

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
    / "fuel_models.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("fuel_models_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_generate_fuel_models_schema_and_ranges(tmp_path):
    module = load_module()
    output_path = tmp_path / "fuel_models.parquet"

    df = module.generate_fuel_models(grid_size=12, seed=42, output_path=output_path)

    assert output_path.exists()
    assert list(df.columns) == [
        "cell_id",
        "lat",
        "lon",
        "fbfm_code",
        "fuel_load_tons_per_acre",
        "canopy_cover_pct",
        "canopy_height_m",
        "biome",
    ]
    assert len(df) == 144
    assert df["cell_id"].is_unique
    assert df["cell_id"].str.match(r"^FUEL-\d{5}$").all()
    assert df["lat"].between(33.25, 33.70).all()
    assert df["lon"].between(-112.30, -111.85).all()
    assert df["fbfm_code"].between(1, 13).all()
    assert df["fuel_load_tons_per_acre"].between(0, 8).all()
    assert df["canopy_cover_pct"].between(0, 85).all()
    assert df["canopy_height_m"].between(0, 6).all()
    assert set(df["biome"]).issubset({"desert-scrub", "wui", "grassland", "chaparral-pocket"})


def test_generate_fuel_models_reproducible(tmp_path):
    module = load_module()

    first = module.generate_fuel_models(
        grid_size=10,
        seed=7,
        output_path=tmp_path / "first.parquet",
    )
    second = module.generate_fuel_models(
        grid_size=10,
        seed=7,
        output_path=tmp_path / "second.parquet",
    )

    pd.testing.assert_frame_equal(first, second)


def test_load_fuel_models(tmp_path):
    module = load_module()
    output_path = tmp_path / "fuel_models.parquet"
    generated = module.generate_fuel_models(grid_size=8, seed=11, output_path=output_path)

    loaded = module.load_fuel_models(output_path)

    pd.testing.assert_frame_equal(generated, loaded)


def test_load_fuel_models_missing_file(tmp_path):
    module = load_module()

    with pytest.raises(FileNotFoundError):
        module.load_fuel_models(tmp_path / "missing.parquet")
