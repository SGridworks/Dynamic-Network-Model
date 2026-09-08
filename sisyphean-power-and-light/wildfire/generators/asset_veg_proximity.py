#!/usr/bin/env python3
"""Generate synthetic asset-to-vegetation proximity records for SP&L.

SYNTHETIC DATA NOTICE
    Sisyphean Power & Light (SP&L) is an entirely fictional utility.
    Vegetation clearances generated here are synthetic and Phoenix-offset.
    No real utility inspection, vegetation management, or ecological data is
    included.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
WILDFIRE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = WILDFIRE_DIR / "asset_vegetation_proximity.parquet"
DEFAULT_FUEL_MODELS_PATH = WILDFIRE_DIR / "fuel_models.parquet"
DEFAULT_TRANSFORMERS_PATH = REPO_ROOT / "demo_data" / "transformers.csv"
DEFAULT_FEEDERS_PATH = REPO_ROOT / "demo_data" / "feeders.csv"
DEFAULT_NETWORK_NODES_PATH = REPO_ROOT / "demo_data" / "network_nodes.csv"
DEFAULT_NETWORK_EDGES_PATH = REPO_ROOT / "demo_data" / "network_edges.csv"

ASSET_TYPES = ("transformer", "line_span", "pole")
CLEARANCE_CLASSES = ("critical", "watch", "normal", "wide")


def _haversine_m(
    lat1: np.ndarray,
    lon1: np.ndarray,
    lat2: np.ndarray,
    lon2: np.ndarray,
) -> np.ndarray:
    """Return great-circle distances in meters."""
    radius_m = 6_371_000.0
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    d_phi = np.radians(lat2 - lat1)
    d_lambda = np.radians(lon2 - lon1)
    a = (
        np.sin(d_phi / 2.0) ** 2
        + np.cos(phi1) * np.cos(phi2) * np.sin(d_lambda / 2.0) ** 2
    )
    return radius_m * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))


def _nearest_fuel_cells(assets: pd.DataFrame, fuels: pd.DataFrame) -> pd.DataFrame:
    fuel_lat = fuels["lat"].to_numpy(dtype=float)
    fuel_lon = fuels["lon"].to_numpy(dtype=float)
    fuel_ids = fuels["cell_id"].to_numpy()

    nearest_ids: list[str] = []
    nearest_distances: list[float] = []
    chunk_size = 2_000

    for start in range(0, len(assets), chunk_size):
        chunk = assets.iloc[start : start + chunk_size]
        asset_lat = chunk["lat"].to_numpy(dtype=float)[:, None]
        asset_lon = chunk["lon"].to_numpy(dtype=float)[:, None]
        distances = _haversine_m(asset_lat, asset_lon, fuel_lat[None, :], fuel_lon[None, :])
        idx = np.argmin(distances, axis=1)
        nearest_ids.extend(fuel_ids[idx].tolist())
        nearest_distances.extend(distances[np.arange(len(chunk)), idx].round(1).tolist())

    result = assets.copy()
    result["nearest_veg_cell_id"] = nearest_ids
    result["distance_m"] = nearest_distances
    return result


def _clearance_class(distance_m: float) -> str:
    if distance_m < 12:
        return "critical"
    if distance_m < 30:
        return "watch"
    if distance_m < 75:
        return "normal"
    return "wide"


def _inspection_dates(
    n_rows: int,
    distances_m: pd.Series,
    seed: int,
) -> tuple[pd.Series, pd.Series]:
    rng = np.random.default_rng(seed)
    base_date = pd.Timestamp("2025-12-31")

    distance_factor = np.clip(distances_m.to_numpy(dtype=float) / 125.0, 0.0, 1.0)
    patrol_age_days = rng.integers(15, 365, n_rows) * (0.55 + distance_factor)
    trim_age_days = rng.integers(45, 730, n_rows) * (0.65 + distance_factor)

    last_patrol = base_date - pd.to_timedelta(patrol_age_days.round().astype(int), unit="D")
    last_trim = base_date - pd.to_timedelta(trim_age_days.round().astype(int), unit="D")
    return pd.Series(last_patrol).dt.date.astype(str), pd.Series(last_trim).dt.date.astype(str)


def _transformer_assets(path: Path) -> pd.DataFrame:
    transformers = pd.read_csv(path)
    if not {"transformer_id", "latitude", "longitude"}.issubset(transformers.columns):
        raise ValueError(f"{path} must include transformer_id, latitude, and longitude")
    return pd.DataFrame(
        {
            "asset_id": transformers["transformer_id"],
            "asset_type": "transformer",
            "lat": transformers["latitude"],
            "lon": transformers["longitude"],
        }
    )


def _line_span_assets(edges_path: Path, nodes_path: Path) -> pd.DataFrame:
    edges = pd.read_csv(edges_path)
    nodes = pd.read_csv(nodes_path)
    node_coords = nodes.set_index("node_id")[["latitude", "longitude"]]

    spans = edges[edges.get("is_overhead", 0).astype(str).isin(["1", "True", "true"])].copy()
    spans = spans.head(8_000)

    from_coords = node_coords.reindex(spans["from_node_id"]).reset_index(drop=True)
    to_coords = node_coords.reindex(spans["to_node_id"]).reset_index(drop=True)
    valid = (from_coords["latitude"].notna() & to_coords["latitude"].notna()).to_numpy()
    spans = spans.loc[valid].reset_index(drop=True)
    from_coords = from_coords.loc[valid].reset_index(drop=True)
    to_coords = to_coords.loc[valid].reset_index(drop=True)

    return pd.DataFrame(
        {
            "asset_id": spans["edge_id"],
            "asset_type": "line_span",
            "lat": (from_coords["latitude"] + to_coords["latitude"]) / 2.0,
            "lon": (from_coords["longitude"] + to_coords["longitude"]) / 2.0,
        }
    )


def _pole_assets(feeders_path: Path) -> pd.DataFrame:
    feeders = pd.read_csv(feeders_path)
    required = {
        "feeder_id",
        "latitude_head",
        "longitude_head",
        "latitude_tail",
        "longitude_tail",
        "length_miles",
    }
    if not required.issubset(feeders.columns):
        raise ValueError(f"{feeders_path} must include feeder endpoints and length_miles")

    rows: list[dict[str, object]] = []
    for feeder in feeders.itertuples(index=False):
        pole_count = max(2, int(round(float(feeder.length_miles) / 0.18)))
        for idx in range(1, pole_count + 1):
            frac = idx / (pole_count + 1)
            rows.append(
                {
                    "asset_id": f"POLE-{feeder.feeder_id}-{idx:03d}",
                    "asset_type": "pole",
                    "lat": float(feeder.latitude_head)
                    + frac * (float(feeder.latitude_tail) - float(feeder.latitude_head)),
                    "lon": float(feeder.longitude_head)
                    + frac * (float(feeder.longitude_tail) - float(feeder.longitude_head)),
                }
            )
    return pd.DataFrame(rows)


def generate_asset_vegetation_proximity(
    fuel_models_path: str | Path = DEFAULT_FUEL_MODELS_PATH,
    transformers_path: str | Path = DEFAULT_TRANSFORMERS_PATH,
    feeders_path: str | Path = DEFAULT_FEEDERS_PATH,
    network_nodes_path: str | Path = DEFAULT_NETWORK_NODES_PATH,
    network_edges_path: str | Path = DEFAULT_NETWORK_EDGES_PATH,
    output_path: str | Path | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate nearest vegetation cell and clearance metadata for grid assets."""
    fuels = pd.read_parquet(fuel_models_path)
    if not {"cell_id", "lat", "lon"}.issubset(fuels.columns):
        raise ValueError("fuel_models_path must contain cell_id, lat, and lon columns")

    assets = pd.concat(
        [
            _transformer_assets(Path(transformers_path)),
            _line_span_assets(Path(network_edges_path), Path(network_nodes_path)),
            _pole_assets(Path(feeders_path)),
        ],
        ignore_index=True,
    )
    assets = assets.dropna(subset=["lat", "lon"]).drop_duplicates("asset_id")
    proximity = _nearest_fuel_cells(assets, fuels)
    proximity["clearance_class"] = proximity["distance_m"].map(_clearance_class)
    last_patrol, last_trim = _inspection_dates(len(proximity), proximity["distance_m"], seed)
    proximity["last_patrol_date"] = last_patrol
    proximity["last_trim_date"] = last_trim

    output = proximity[
        [
            "asset_id",
            "asset_type",
            "nearest_veg_cell_id",
            "distance_m",
            "clearance_class",
            "last_patrol_date",
            "last_trim_date",
        ]
    ].sort_values(["asset_type", "asset_id"], kind="stable").reset_index(drop=True)

    destination = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(destination, index=False)
    return output


def load_asset_vegetation_proximity(path: str | Path | None = None) -> pd.DataFrame:
    """Load generated asset-to-vegetation proximity records."""
    source = Path(path) if path is not None else DEFAULT_OUTPUT_PATH
    if not source.exists():
        raise FileNotFoundError(f"asset_vegetation_proximity.parquet not found at {source}")
    return pd.read_parquet(source)


if __name__ == "__main__":
    generated = generate_asset_vegetation_proximity()
    print(
        "Generated "
        f"{len(generated)} asset vegetation proximity records at {DEFAULT_OUTPUT_PATH}"
    )
