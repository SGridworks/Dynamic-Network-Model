"""Validation tests for synthetic PSPS events."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = (
    REPO_ROOT / "sisyphean-power-and-light" / "wildfire" / "generators" / "psps_events.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("psps_events_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_feeders(tmp_path: Path) -> Path:
    feeders = pd.DataFrame(
        {
            "feeder_id": [f"FDR-{idx:04d}" for idx in range(1, 9)],
            "num_customers": [900, 1200, 1800, 750, 2100, 1300, 1650, 980],
        }
    )
    path = tmp_path / "feeders.csv"
    feeders.to_csv(path, index=False)
    return path


def test_generate_psps_events_schema_and_ranges(tmp_path):
    module = load_module()
    output_path = tmp_path / "psps_events.parquet"

    df = module.generate_psps_events(
        feeders_path=write_feeders(tmp_path),
        output_path=output_path,
        start_year=2020,
        end_year=2021,
        seed=42,
    )

    assert output_path.exists()
    assert list(df.columns) == [
        "event_id",
        "start_time",
        "end_time",
        "feeder_ids",
        "customers_deenergized",
        "peak_wind_mph",
        "peak_erc",
        "decision_rationale",
        "post_event_ignitions_avoided_est",
    ]
    assert 6 <= len(df) <= 12
    assert df["event_id"].str.match(r"^PSPS-\d{4}-\d{4}$").all()
    assert (pd.to_datetime(df["end_time"]) > pd.to_datetime(df["start_time"])).all()
    assert df["customers_deenergized"].gt(0).all()
    assert df["peak_wind_mph"].between(31, 58).all()
    assert df["peak_erc"].between(66, 98).all()
    assert df["post_event_ignitions_avoided_est"].between(0, 3).all()
    assert df["feeder_ids"].map(len).between(2, 7).all()


def test_load_psps_events(tmp_path):
    module = load_module()
    output_path = tmp_path / "psps_events.parquet"
    generated = module.generate_psps_events(
        feeders_path=write_feeders(tmp_path),
        output_path=output_path,
        start_year=2020,
        end_year=2020,
    )

    loaded = module.load_psps_events(output_path)

    pd.testing.assert_frame_equal(generated, loaded)


def test_load_psps_events_missing_file(tmp_path):
    module = load_module()

    with pytest.raises(FileNotFoundError):
        module.load_psps_events(tmp_path / "missing.parquet")
