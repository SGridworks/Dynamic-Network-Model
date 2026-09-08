"""Validation tests for the synthetic asset vegetation proximity dataset."""

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
    / "asset_veg_proximity.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("asset_veg_proximity_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def write_fixture_inputs(tmp_path: Path) -> dict[str, Path]:
    fuels = pd.DataFrame(
        {
            "cell_id": ["FUEL-00001", "FUEL-00002", "FUEL-00003"],
            "lat": [33.50, 33.55, 33.60],
            "lon": [-112.10, -112.15, -112.20],
            "fbfm_code": [5, 8, 12],
            "fuel_load_tons_per_acre": [1.2, 0.8, 4.6],
            "canopy_cover_pct": [16.0, 10.0, 44.0],
            "canopy_height_m": [1.0, 0.8, 2.7],
            "biome": ["desert-scrub", "wui", "chaparral-pocket"],
        }
    )
    transformers = pd.DataFrame(
        {
            "transformer_id": ["XFMR-001", "XFMR-002"],
            "latitude": [33.501, 33.548],
            "longitude": [-112.099, -112.149],
        }
    )
    feeders = pd.DataFrame(
        {
            "feeder_id": ["FDR-001"],
            "latitude_head": [33.50],
            "longitude_head": [-112.10],
            "latitude_tail": [33.60],
            "longitude_tail": [-112.20],
            "length_miles": [0.72],
        }
    )
    nodes = pd.DataFrame(
        {
            "node_id": ["A", "B", "C"],
            "latitude": [33.50, 33.55, 33.60],
            "longitude": [-112.10, -112.15, -112.20],
        }
    )
    edges = pd.DataFrame(
        {
            "edge_id": ["EDGE-001", "EDGE-002"],
            "from_node_id": ["A", "B"],
            "to_node_id": ["B", "C"],
            "is_overhead": [1, 0],
        }
    )

    paths = {
        "fuel_models_path": tmp_path / "fuel_models.parquet",
        "transformers_path": tmp_path / "transformers.csv",
        "feeders_path": tmp_path / "feeders.csv",
        "network_nodes_path": tmp_path / "network_nodes.csv",
        "network_edges_path": tmp_path / "network_edges.csv",
    }
    fuels.to_parquet(paths["fuel_models_path"], index=False)
    transformers.to_csv(paths["transformers_path"], index=False)
    feeders.to_csv(paths["feeders_path"], index=False)
    nodes.to_csv(paths["network_nodes_path"], index=False)
    edges.to_csv(paths["network_edges_path"], index=False)
    return paths


def test_generate_asset_vegetation_proximity_schema_and_ranges(tmp_path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path)
    output_path = tmp_path / "asset_vegetation_proximity.parquet"

    df = module.generate_asset_vegetation_proximity(
        **paths,
        output_path=output_path,
        seed=42,
    )

    assert output_path.exists()
    assert list(df.columns) == [
        "asset_id",
        "asset_type",
        "nearest_veg_cell_id",
        "distance_m",
        "clearance_class",
        "last_patrol_date",
        "last_trim_date",
    ]
    assert len(df) >= 7
    assert df["asset_id"].is_unique
    assert set(df["asset_type"]) == {"transformer", "line_span", "pole"}
    assert df["nearest_veg_cell_id"].isin(["FUEL-00001", "FUEL-00002", "FUEL-00003"]).all()
    assert df["distance_m"].between(0, 20_000).all()
    assert set(df["clearance_class"]).issubset({"critical", "watch", "normal", "wide"})
    assert pd.to_datetime(df["last_patrol_date"]).notna().all()
    assert pd.to_datetime(df["last_trim_date"]).notna().all()


def test_generate_asset_vegetation_proximity_reproducible(tmp_path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path)

    first = module.generate_asset_vegetation_proximity(
        **paths,
        output_path=tmp_path / "first.parquet",
        seed=7,
    )
    second = module.generate_asset_vegetation_proximity(
        **paths,
        output_path=tmp_path / "second.parquet",
        seed=7,
    )

    pd.testing.assert_frame_equal(first, second)


def test_load_asset_vegetation_proximity(tmp_path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path)
    output_path = tmp_path / "asset_vegetation_proximity.parquet"
    generated = module.generate_asset_vegetation_proximity(
        **paths,
        output_path=output_path,
        seed=11,
    )

    loaded = module.load_asset_vegetation_proximity(output_path)

    pd.testing.assert_frame_equal(generated, loaded)


def test_load_asset_vegetation_proximity_missing_file(tmp_path):
    module = load_module()

    with pytest.raises(FileNotFoundError):
        module.load_asset_vegetation_proximity(tmp_path / "missing.parquet")


def test_missing_required_transformer_columns(tmp_path):
    module = load_module()
    paths = write_fixture_inputs(tmp_path)
    pd.DataFrame({"transformer_id": ["XFMR-001"]}).to_csv(
        paths["transformers_path"], index=False
    )

    with pytest.raises(ValueError):
        module.generate_asset_vegetation_proximity(
            **paths,
            output_path=tmp_path / "bad.parquet",
        )
