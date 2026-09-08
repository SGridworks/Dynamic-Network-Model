"""Validation tests for the synthetic wildfire terrain dataset."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPO_ROOT / "sisyphean-power-and-light" / "wildfire" / "generators" / "terrain.py"


def load_module():
    spec = importlib.util.spec_from_file_location("terrain_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_fuels(tmp_path: Path) -> Path:
    fuels = pd.DataFrame(
        {
            "cell_id": ["FUEL-00001", "FUEL-00002", "FUEL-00003"],
            "lat": [33.50, 33.55, 33.60],
            "lon": [-112.10, -112.15, -112.20],
        }
    )
    path = tmp_path / "fuel_models.parquet"
    fuels.to_parquet(path, index=False)
    return path


def test_generate_terrain_schema_and_ranges(tmp_path):
    module = load_module()
    output_path = tmp_path / "terrain.parquet"

    df = module.generate_terrain(
        fuel_models_path=write_fuels(tmp_path),
        output_path=output_path,
    )

    assert output_path.exists()
    assert list(df.columns) == [
        "cell_id",
        "elevation_m",
        "slope_deg",
        "aspect_deg",
        "ruggedness_index",
    ]
    assert len(df) == 3
    assert df["cell_id"].is_unique
    assert df["elevation_m"].between(200, 1_000).all()
    assert df["slope_deg"].between(0, 45).all()
    assert df["aspect_deg"].between(0, 360).all()
    assert df["ruggedness_index"].between(0, 1.5).all()


def test_load_terrain(tmp_path):
    module = load_module()
    output_path = tmp_path / "terrain.parquet"
    generated = module.generate_terrain(
        fuel_models_path=write_fuels(tmp_path),
        output_path=output_path,
    )

    loaded = module.load_terrain(output_path)

    pd.testing.assert_frame_equal(generated, loaded)


def test_load_terrain_missing_file(tmp_path):
    module = load_module()

    with pytest.raises(FileNotFoundError):
        module.load_terrain(tmp_path / "missing.parquet")
