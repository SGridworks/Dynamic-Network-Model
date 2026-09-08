"""Regression checks for the real V1-to-V2 data path."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from demo_data import load_demo_data as loader  # noqa: E402


@pytest.fixture(scope="module")
def data():
    return loader.load_all(["feeders", "transformers", "customers", "load_profiles", "customer_interval_data"])


def test_substation_hierarchy_follows_registry(data):
    for name in ("transformers", "customers", "load_profiles"):
        frame = data[name]
        expected = frame.feeder_id.map(data["feeders"].substation_id)
        assert expected.notna().all()
        assert frame.substation_id.eq(expected).all(), name


def test_transformer_attributes_survive_conversion(data):
    original = pd.read_csv(ROOT / "demo_data/transformers.csv").set_index("transformer_id")
    for column in ("latitude", "longitude", "phase", "primary_voltage_kv", "secondary_voltage_v"):
        pd.testing.assert_series_equal(data["transformers"][column], original[column])


def test_hourly_profiles_preserve_sample_coverage_and_energy(data):
    source = pd.read_csv(ROOT / "demo_data/load_profiles.csv.gz", parse_dates=["timestamp"])
    source["timestamp"] = source.timestamp.dt.floor("h")
    expected = source.groupby(["feeder_id", "timestamp"])["load_mw"].mean()
    actual = data["load_profiles"].set_index(["feeder_id", "timestamp"]).load_mw.sort_index()
    pd.testing.assert_series_equal(actual, expected, check_freq=False)
    assert np.isfinite(actual).all()
    assert np.isclose(actual.sum(), source.load_mw.sum() * 0.25)


def test_hourly_electrical_values_come_from_source(data):
    source = pd.read_csv(ROOT / "demo_data/load_profiles.csv.gz", parse_dates=["timestamp"])
    source["timestamp"] = source.timestamp.dt.floor("h")
    expected = source.groupby(["feeder_id", "timestamp"])[["load_mvar", "voltage_pu"]].mean()
    actual = data["load_profiles"].set_index(["feeder_id", "timestamp"]).sort_index()
    pd.testing.assert_frame_equal(actual[expected.columns], expected, check_freq=False)
    expected_pf = actual.load_mw / np.hypot(actual.load_mw, actual.load_mvar)
    np.testing.assert_allclose(actual.power_factor, expected_pf)


def test_unknown_feeders_raise_instead_of_inventing_substations():
    with pytest.raises(ValueError, match="[Uu]nknown feeder"):
        loader._feeder_to_substation("FDR-NOT-REAL")


def test_validator_detects_valid_but_wrong_foreign_key_and_missing_load(data):
    from validate_demo_data import Report, validate_data_contract

    broken = {name: frame.copy() for name, frame in data.items()}
    broken["transformers"].iloc[0, broken["transformers"].columns.get_loc("substation_id")] = "SUB-023"
    broken["load_profiles"].loc[0, "load_mw"] = np.nan
    report = Report()
    validate_data_contract(broken, report)
    failures = [check for _, check, status, _ in report.results if status == "FAIL"]
    assert "transformers: feeder/substation hierarchy" in failures
    assert "load profiles: finite electrical values" in failures


def test_converter_rejects_incomplete_hour():
    from convert_load_profiles import convert_profiles

    source = pd.DataFrame({
        "feeder_id": ["FDR-1"] * 3,
        "timestamp": pd.date_range("2024-01-01", periods=3, freq="15min"),
        "load_mw": [1.0] * 3, "load_mvar": [0.3] * 3, "voltage_pu": [1.0] * 3,
    })
    with pytest.raises(ValueError, match="four 15-minute"):
        convert_profiles(source, pd.DataFrame())


def test_ami_matches_current_customer_registry(data):
    ami = data["customer_interval_data"]
    for column in ("transformer_id", "feeder_id", "substation_id", "customer_type"):
        assert ami[column].eq(ami.customer_id.map(data["customers"][column])).all()
    assert not ami.duplicated(["customer_id", "timestamp"]).any()
    assert ami.groupby("customer_id").size().eq(7 * 24 * 4).all()
