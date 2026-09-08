#!/usr/bin/env python3
"""Generate synthetic hourly fire-weather indices for SP&L wildfire cells.

SYNTHETIC DATA NOTICE
    Sisyphean Power & Light (SP&L) is an entirely fictional utility.
    Fire-weather indices generated here are synthetic and Phoenix-offset.
    They are intended for ML playground examples, not operational use.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
WILDFIRE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = WILDFIRE_DIR / "fire_weather_indices_hourly.parquet"
DEFAULT_FUEL_MODELS_PATH = WILDFIRE_DIR / "fuel_models.parquet"
DEFAULT_FUEL_MOISTURE_PATH = WILDFIRE_DIR / "fuel_moisture_daily.parquet"
DEFAULT_WEATHER_PATH = REPO_ROOT / "sisyphean-power-and-light" / "weather" / "hourly_observations.csv"


def _representative_cells(fuels: pd.DataFrame, max_cells: int, seed: int) -> pd.DataFrame:
    if max_cells <= 0 or max_cells >= len(fuels):
        return fuels.copy()
    per_biome = max(1, max_cells // 4)
    samples = [
        group.sample(min(len(group), per_biome), random_state=seed)
        for _, group in fuels.groupby("biome")
    ]
    sampled = pd.concat(samples, ignore_index=True)
    if len(sampled) < max_cells:
        remainder = fuels.loc[~fuels["cell_id"].isin(sampled["cell_id"])]
        sampled = pd.concat(
            [
                sampled,
                remainder.sample(max_cells - len(sampled), random_state=seed),
            ],
            ignore_index=True,
        )
    return sampled.head(max_cells).copy()


def _normalize_weather(weather: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "temperature": "temperature_f",
        "humidity": "humidity_pct",
        "wind_speed": "wind_speed_mph",
        "precipitation": "precipitation_in",
    }
    weather = weather.rename(columns=rename_map).copy()
    required = {"timestamp", "temperature_f", "humidity_pct", "wind_speed_mph", "precipitation_in"}
    missing = required.difference(weather.columns)
    if missing:
        raise ValueError(f"weather data missing columns: {sorted(missing)}")
    weather["timestamp"] = pd.to_datetime(weather["timestamp"])
    weather["date"] = weather["timestamp"].dt.normalize()
    weather["station_id"] = weather.get("station_id", "WX-001")
    weather["wind_gust_mph"] = (weather["wind_speed_mph"] * 1.38).clip(lower=0).round(1)
    weather["wind_steadiness"] = 0.65 + 0.25 * np.cos(weather["timestamp"].dt.hour / 24 * 2 * np.pi)
    weather["wind_steadiness"] = weather["wind_steadiness"].clip(0.2, 1.0).round(3)
    return weather


def _normalize_fuel_moisture(fuel_moisture: pd.DataFrame) -> pd.DataFrame:
    moisture = fuel_moisture.rename(
        columns={
            "fm_1h_pct": "dead_1hr",
            "fm_10h_pct": "dead_10hr",
            "fm_100h_pct": "dead_100hr",
            "live_herb_pct": "live_herbaceous",
            "live_woody_pct": "live_woody",
        }
    ).copy()
    required = {"date", "dead_1hr", "dead_10hr", "dead_100hr", "live_herbaceous", "live_woody"}
    missing = required.difference(moisture.columns)
    if missing:
        raise ValueError(f"fuel moisture data missing columns: {sorted(missing)}")
    moisture["date"] = pd.to_datetime(moisture["date"]).dt.normalize()
    return moisture


def _build_hourly_weather(
    weather_path: str | Path,
    fuel_moisture_path: str | Path,
    start: str,
    end: str,
) -> pd.DataFrame:
    weather = _normalize_weather(pd.read_csv(weather_path))
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    weather = weather[(weather["timestamp"] >= start_ts) & (weather["timestamp"] <= end_ts)].copy()
    if weather.empty:
        raise ValueError("weather filter produced no rows")

    moisture = _normalize_fuel_moisture(pd.read_parquet(fuel_moisture_path))
    if moisture["date"].min() > weather["date"].min() or moisture["date"].max() < weather["date"].max():
        template = moisture.copy()
        template["month_day"] = template["date"].dt.strftime("%m-%d")
        weather["month_day"] = weather["date"].dt.strftime("%m-%d")
        weather = weather.merge(
            template.drop(columns=["date"]),
            on="month_day",
            how="left",
        ).drop(columns=["month_day"])
    else:
        weather = weather.merge(moisture, on="date", how="left")

    moisture_cols = ["dead_1hr", "dead_10hr", "dead_100hr", "live_herbaceous", "live_woody"]
    weather[moisture_cols] = weather[moisture_cols].ffill().bfill()
    return weather


def generate_fire_weather_indices(
    fuel_models_path: str | Path = DEFAULT_FUEL_MODELS_PATH,
    fuel_moisture_path: str | Path = DEFAULT_FUEL_MOISTURE_PATH,
    weather_path: str | Path = DEFAULT_WEATHER_PATH,
    output_path: str | Path | None = None,
    start: str = "2024-01-01 00:00:00",
    end: str = "2025-12-31 23:00:00",
    max_cells: int = 160,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate hourly ERC, BI, KBDI, FFWI, and red-flag flags by cell."""
    fuels = pd.read_parquet(fuel_models_path)
    required_fuel_cols = {"cell_id", "fbfm_code", "fuel_load_tons_per_acre", "canopy_cover_pct", "biome"}
    missing = required_fuel_cols.difference(fuels.columns)
    if missing:
        raise ValueError(f"fuel models missing columns: {sorted(missing)}")

    cells = _representative_cells(fuels, max_cells=max_cells, seed=seed)
    hourly = _build_hourly_weather(weather_path, fuel_moisture_path, start=start, end=end)

    weather_part = hourly[
        [
            "timestamp",
            "temperature_f",
            "humidity_pct",
            "wind_speed_mph",
            "wind_gust_mph",
            "precipitation_in",
            "dead_1hr",
            "dead_10hr",
            "dead_100hr",
            "live_herbaceous",
            "live_woody",
        ]
    ].copy()
    weather_part["_join_key"] = 1

    cell_part = cells[
        ["cell_id", "fbfm_code", "fuel_load_tons_per_acre", "canopy_cover_pct", "biome"]
    ].copy()
    cell_part["_join_key"] = 1

    df = weather_part.merge(cell_part, on="_join_key", how="inner").drop(columns=["_join_key"])
    biome_factor = df["biome"].map(
        {
            "desert-scrub": 0.92,
            "wui": 0.82,
            "grassland": 1.02,
            "chaparral-pocket": 1.18,
        }
    ).fillna(1.0)
    fuel_factor = (
        0.65
        + 0.11 * df["fuel_load_tons_per_acre"].astype(float)
        + 0.003 * df["canopy_cover_pct"].astype(float)
        + 0.015 * df["fbfm_code"].astype(float)
    ) * biome_factor
    dryness = (
        100.0
        - 1.65 * df["dead_100hr"].astype(float)
        - 0.22 * df["live_woody"].astype(float)
        + 0.34 * (df["temperature_f"].astype(float) - 70.0)
        - 0.24 * (df["humidity_pct"].astype(float) - 25.0)
        - 9.5 * df["precipitation_in"].astype(float).clip(0, 1.0)
    )
    erc = np.clip(dryness * fuel_factor, 0, 100)
    bi = np.clip(erc * (0.42 + df["wind_gust_mph"].astype(float) / 85.0), 0, 120)
    kbdi = np.clip(
        120
        + 6.1 * (df["temperature_f"].astype(float) - 60.0)
        - 2.3 * df["humidity_pct"].astype(float)
        - 70 * df["precipitation_in"].astype(float).clip(0, 2.0)
        + 2.2 * erc,
        0,
        800,
    )
    ffwi = np.clip(
        (df["wind_speed_mph"].astype(float) + 0.5 * df["wind_gust_mph"].astype(float))
        * (100.0 - df["humidity_pct"].astype(float))
        / 260.0
        + erc / 28.0,
        0,
        50,
    )

    red_flag = (
        (df["timestamp"].dt.month.between(5, 10))
        & (df["wind_gust_mph"].astype(float) >= 30.0)
        & (df["humidity_pct"].astype(float) <= 45.0)
        & (erc >= 75.0)
        & (ffwi >= 9.0)
    )

    output = pd.DataFrame(
        {
            "timestamp": df["timestamp"],
            "cell_id": df["cell_id"],
            "erc": erc.round(2),
            "bi": bi.round(2),
            "kbdi": kbdi.round(1),
            "ffwi": ffwi.round(2),
            "red_flag_flag": red_flag.astype(bool),
        }
    )

    destination = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    output.to_parquet(destination, index=False)
    return output


def load_fire_weather_indices(path: str | Path | None = None) -> pd.DataFrame:
    """Load generated hourly fire-weather indices."""
    source = Path(path) if path is not None else DEFAULT_OUTPUT_PATH
    if not source.exists():
        raise FileNotFoundError(f"fire_weather_indices_hourly.parquet not found at {source}")
    return pd.read_parquet(source)


if __name__ == "__main__":
    generated = generate_fire_weather_indices()
    print(
        "Generated "
        f"{len(generated)} fire-weather index records at {DEFAULT_OUTPUT_PATH}"
    )
