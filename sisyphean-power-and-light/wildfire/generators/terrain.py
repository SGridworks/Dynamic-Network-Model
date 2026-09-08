#!/usr/bin/env python3
"""Generate synthetic terrain for the SP&L wildfire footprint."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


WILDFIRE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FUEL_MODELS_PATH = WILDFIRE_DIR / "fuel_models.parquet"
DEFAULT_OUTPUT_PATH = WILDFIRE_DIR / "terrain.parquet"


def generate_terrain(
    fuel_models_path: str | Path = DEFAULT_FUEL_MODELS_PATH,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Generate a coherent synthetic DEM aligned to fuel-model cells."""
    fuels = pd.read_parquet(fuel_models_path)
    required = {"cell_id", "lat", "lon"}
    missing = required.difference(fuels.columns)
    if missing:
        raise ValueError(f"fuel models missing columns: {sorted(missing)}")

    lat = fuels["lat"].astype(float)
    lon = fuels["lon"].astype(float)
    lat_norm = (lat - lat.min()) / max(lat.max() - lat.min(), 1e-9)
    lon_norm = (lon - lon.min()) / max(lon.max() - lon.min(), 1e-9)

    elevation = (
        295
        + 360 * lat_norm
        + 170 * (1 - lon_norm)
        + 55 * np.sin(lon_norm * np.pi * 4)
        + 35 * np.cos(lat_norm * np.pi * 3)
    )
    slope = np.clip(2.5 + 21 * np.abs(np.sin((lat_norm + lon_norm) * np.pi * 2)), 0, 45)
    aspect = (np.degrees(np.arctan2(lat_norm - 0.5, lon_norm - 0.5)) + 360) % 360
    ruggedness = np.clip(slope / 45 + np.abs(np.sin(lat_norm * np.pi * 5)) * 0.45, 0, 1.5)

    df = pd.DataFrame(
        {
            "cell_id": fuels["cell_id"],
            "elevation_m": elevation.round(1),
            "slope_deg": slope.round(2),
            "aspect_deg": aspect.round(2),
            "ruggedness_index": ruggedness.round(3),
        }
    )

    destination = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destination, index=False)
    return df


def load_terrain(path: str | Path | None = None) -> pd.DataFrame:
    """Load generated wildfire terrain records."""
    source = Path(path) if path is not None else DEFAULT_OUTPUT_PATH
    if not source.exists():
        raise FileNotFoundError(f"terrain.parquet not found at {source}")
    return pd.read_parquet(source)


if __name__ == "__main__":
    generated = generate_terrain()
    print(f"Generated {len(generated)} terrain records at {DEFAULT_OUTPUT_PATH}")
