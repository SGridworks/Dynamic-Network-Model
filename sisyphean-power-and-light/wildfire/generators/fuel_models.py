#!/usr/bin/env python3
"""Generate synthetic wildfire fuel-model cells for SP&L.

SYNTHETIC DATA NOTICE
    Sisyphean Power & Light (SP&L) is an entirely fictional utility.
    All fuel ecology data generated here is synthetic and Phoenix-offset.
    No real ecological, utility, or land-management data is included.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


WILDFIRE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = WILDFIRE_DIR / "fuel_models.parquet"

BIOMES = ("desert-scrub", "wui", "grassland", "chaparral-pocket")

FUEL_MODEL_PROFILES: dict[int, dict[str, float | str]] = {
    1: {"biome": "grassland", "load": 0.35, "canopy_cover": 2.0, "canopy_height": 0.2},
    2: {"biome": "grassland", "load": 0.75, "canopy_cover": 5.0, "canopy_height": 0.4},
    3: {"biome": "grassland", "load": 1.15, "canopy_cover": 8.0, "canopy_height": 0.7},
    4: {"biome": "chaparral-pocket", "load": 4.8, "canopy_cover": 48.0, "canopy_height": 2.6},
    5: {"biome": "desert-scrub", "load": 1.3, "canopy_cover": 18.0, "canopy_height": 1.1},
    6: {"biome": "desert-scrub", "load": 1.9, "canopy_cover": 24.0, "canopy_height": 1.4},
    7: {"biome": "chaparral-pocket", "load": 3.2, "canopy_cover": 38.0, "canopy_height": 2.1},
    8: {"biome": "wui", "load": 0.65, "canopy_cover": 12.0, "canopy_height": 1.0},
    9: {"biome": "wui", "load": 0.95, "canopy_cover": 18.0, "canopy_height": 1.6},
    10: {"biome": "wui", "load": 1.4, "canopy_cover": 25.0, "canopy_height": 2.2},
    11: {"biome": "desert-scrub", "load": 0.85, "canopy_cover": 14.0, "canopy_height": 0.9},
    12: {"biome": "chaparral-pocket", "load": 5.7, "canopy_cover": 55.0, "canopy_height": 3.0},
    13: {"biome": "chaparral-pocket", "load": 6.6, "canopy_cover": 62.0, "canopy_height": 3.4},
}


def _choose_fbfm_code(lat: float, lon: float, rng: np.random.Generator) -> int:
    """Assign a fictional FBFM analog from synthetic landform position."""
    urban_core = abs(lat - 33.45) < 0.07 and abs(lon + 112.07) < 0.09
    grass_corridor = (lat > 33.54 and lon > -112.12) or rng.random() < 0.18
    chaparral_pocket = (lat > 33.58 and lon < -112.18) or rng.random() < 0.08

    if urban_core:
        return int(rng.choice([8, 9, 10, 5], p=[0.38, 0.32, 0.18, 0.12]))
    if chaparral_pocket:
        return int(rng.choice([4, 7, 12, 13], p=[0.28, 0.34, 0.24, 0.14]))
    if grass_corridor:
        return int(rng.choice([1, 2, 3, 5], p=[0.34, 0.34, 0.20, 0.12]))
    return int(rng.choice([5, 6, 11, 2], p=[0.38, 0.30, 0.20, 0.12]))


def generate_fuel_models(
    grid_size: int = 70,
    seed: int = 42,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Generate gridded fictional fire ecology over the SP&L footprint."""
    if grid_size <= 0:
        raise ValueError("grid_size must be positive")

    rng = np.random.default_rng(seed)
    lat_min, lat_max = 33.25, 33.70
    lon_min, lon_max = -112.30, -111.85
    lat_step = (lat_max - lat_min) / grid_size
    lon_step = (lon_max - lon_min) / grid_size

    rows: list[dict[str, object]] = []
    for row_idx in range(grid_size):
        lat = lat_min + lat_step * (row_idx + 0.5)
        for col_idx in range(grid_size):
            lon = lon_min + lon_step * (col_idx + 0.5)
            code = _choose_fbfm_code(lat, lon, rng)
            profile = FUEL_MODEL_PROFILES[code]
            load = max(0.05, float(profile["load"]) + rng.normal(0, 0.12))
            canopy_cover = np.clip(float(profile["canopy_cover"]) + rng.normal(0, 4.0), 0, 85)
            canopy_height = np.clip(float(profile["canopy_height"]) + rng.normal(0, 0.25), 0, 6)
            rows.append(
                {
                    "cell_id": f"FUEL-{row_idx * grid_size + col_idx + 1:05d}",
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    "fbfm_code": code,
                    "fuel_load_tons_per_acre": round(load, 3),
                    "canopy_cover_pct": round(float(canopy_cover), 2),
                    "canopy_height_m": round(float(canopy_height), 2),
                    "biome": str(profile["biome"]),
                }
            )

    df = pd.DataFrame(rows)
    destination = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destination, index=False)
    return df


def load_fuel_models(path: str | Path | None = None) -> pd.DataFrame:
    """Load generated fuel-model cells."""
    source = Path(path) if path is not None else DEFAULT_OUTPUT_PATH
    if not source.exists():
        raise FileNotFoundError(f"fuel_models.parquet not found at {source}")
    return pd.read_parquet(source)


if __name__ == "__main__":
    generated = generate_fuel_models()
    print(f"Generated {len(generated)} fuel model cells at {DEFAULT_OUTPUT_PATH}")
