#!/usr/bin/env python3
"""Generate synthetic hourly wind direction and gust records for SP&L."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
WILDFIRE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_WEATHER_PATH = REPO_ROOT / "sisyphean-power-and-light" / "weather" / "hourly_observations.csv"
DEFAULT_OUTPUT_PATH = WILDFIRE_DIR / "wind_direction_hourly.parquet"


def generate_wind_direction(
    weather_path: str | Path = DEFAULT_WEATHER_PATH,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Generate wind direction, gust speed, and steadiness alongside weather."""
    weather = pd.read_csv(weather_path)
    required = {"timestamp", "wind_speed"}
    missing = required.difference(weather.columns)
    if missing:
        raise ValueError(f"weather data missing columns: {sorted(missing)}")

    ts = pd.to_datetime(weather["timestamp"])
    day_angle = ts.dt.dayofyear.to_numpy(dtype=float) / 365.25 * 2 * np.pi
    hour_angle = ts.dt.hour.to_numpy(dtype=float) / 24 * 2 * np.pi
    base_direction = 210 + 55 * np.sin(day_angle - 0.8) + 28 * np.cos(hour_angle)
    wind_direction = np.mod(base_direction, 360)
    wind_gust = np.clip(weather["wind_speed"].astype(float) * (1.28 + 0.18 * np.sin(hour_angle)), 1, 65)
    steadiness = np.clip(1 - np.abs(np.sin(hour_angle)) * 0.35, 0.35, 0.98)

    df = pd.DataFrame(
        {
            "timestamp": ts,
            "station_id": "WX-001",
            "wind_direction_deg": wind_direction.round(1),
            "wind_gust_mph": wind_gust.round(1),
            "wind_steadiness": steadiness.round(3),
        }
    )

    destination = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destination, index=False)
    return df


def load_wind_direction(path: str | Path | None = None) -> pd.DataFrame:
    """Load generated wind direction records."""
    source = Path(path) if path is not None else DEFAULT_OUTPUT_PATH
    if not source.exists():
        raise FileNotFoundError(f"wind_direction_hourly.parquet not found at {source}")
    return pd.read_parquet(source)


if __name__ == "__main__":
    generated = generate_wind_direction()
    print(f"Generated {len(generated)} wind direction records at {DEFAULT_OUTPUT_PATH}")
