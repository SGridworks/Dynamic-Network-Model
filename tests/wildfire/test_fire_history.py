"""Validation tests for the synthetic fire history dataset."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = (
    REPO_ROOT / "sisyphean-power-and-light" / "wildfire" / "generators" / "fire_history.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("fire_history_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_fuels(tmp_path: Path) -> Path:
    fuels = pd.DataFrame(
        {
            "cell_id": [f"FUEL-{idx:05d}" for idx in range(1, 7)],
            "lat": [33.50, 33.51, 33.52, 33.53, 33.54, 33.55],
            "lon": [-112.10, -112.11, -112.12, -112.13, -112.14, -112.15],
            "biome": ["desert-scrub", "wui", "grassland", "chaparral-pocket", "wui", "grassland"],
            "fuel_load_tons_per_acre": [1.0, 0.7, 1.4, 6.0, 0.9, 1.3],
        }
    )
    path = tmp_path / "fuel_models.parquet"
    fuels.to_parquet(path, index=False)
    return path


def test_generate_fire_history_schema_and_ranges(tmp_path):
    module = load_module()
    output_path = tmp_path / "fire_history.parquet"

    df = module.generate_fire_history(
        fuel_models_path=write_fuels(tmp_path),
        outage_events_path=tmp_path / "missing.csv",
        output_path=output_path,
        start_year=2020,
        end_year=2021,
        seed=42,
    )

    assert output_path.exists()
    assert list(df.columns) == [
        "ignition_id",
        "timestamp",
        "lat",
        "lon",
        "cause",
        "final_acres",
        "suppression_hours",
        "structures_lost",
        "outage_event_id",
    ]
    assert 16 <= len(df) <= 30
    assert df["ignition_id"].str.match(r"^IGN-\d{4}-\d{5}$").all()
    assert df["lat"].between(33.20, 33.75).all()
    assert df["lon"].between(-112.35, -111.80).all()
    assert set(df["cause"]).issubset({"powerline", "lightning", "human", "unknown"})
    assert df["final_acres"].gt(0).all()
    assert df["suppression_hours"].between(1, 240).all()
    assert df["structures_lost"].ge(0).all()


def test_load_fire_history(tmp_path):
    module = load_module()
    output_path = tmp_path / "fire_history.parquet"
    generated = module.generate_fire_history(
        fuel_models_path=write_fuels(tmp_path),
        outage_events_path=tmp_path / "missing.csv",
        output_path=output_path,
        start_year=2020,
        end_year=2020,
    )

    loaded = module.load_fire_history(output_path)

    pd.testing.assert_frame_equal(generated, loaded)


def test_load_fire_history_missing_file(tmp_path):
    module = load_module()

    with pytest.raises(FileNotFoundError):
        module.load_fire_history(tmp_path / "missing.parquet")
