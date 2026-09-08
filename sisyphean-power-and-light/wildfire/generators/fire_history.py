#!/usr/bin/env python3
"""Generate synthetic wildfire ignition history for SP&L."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
WILDFIRE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_FUEL_MODELS_PATH = WILDFIRE_DIR / "fuel_models.parquet"
DEFAULT_OUTAGE_EVENTS_PATH = REPO_ROOT / "sisyphean-power-and-light" / "outages" / "outage_events.csv"
DEFAULT_OUTPUT_PATH = WILDFIRE_DIR / "fire_history.parquet"

CAUSES = ("powerline", "lightning", "human", "unknown")


def _vegetation_outages(path: Path) -> list[str]:
    if not path.exists():
        return []
    outages = pd.read_csv(path)
    if "cause" not in outages.columns:
        return []
    id_col = "outage_id" if "outage_id" in outages.columns else outages.columns[0]
    mask = outages["cause"].astype(str).str.lower().str.contains("vegetation", na=False)
    return outages.loc[mask, id_col].astype(str).head(30).tolist()


def generate_fire_history(
    fuel_models_path: str | Path = DEFAULT_FUEL_MODELS_PATH,
    outage_events_path: str | Path = DEFAULT_OUTAGE_EVENTS_PATH,
    output_path: str | Path | None = None,
    start_year: int = 2015,
    end_year: int = 2025,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate 8-15 ignition events per year over the synthetic footprint."""
    rng = np.random.default_rng(seed)
    fuels = pd.read_parquet(fuel_models_path)
    required = {"cell_id", "lat", "lon", "biome", "fuel_load_tons_per_acre"}
    missing = required.difference(fuels.columns)
    if missing:
        raise ValueError(f"fuel models missing columns: {sorted(missing)}")

    vegetation_outages = _vegetation_outages(Path(outage_events_path))
    events: list[dict[str, object]] = []
    event_num = 1

    for year in range(start_year, end_year + 1):
        n_events = int(rng.integers(8, 16))
        for _ in range(n_events):
            fire_season = rng.random() < 0.78
            month = int(rng.integers(5, 11) if fire_season else rng.integers(1, 13))
            day = int(rng.integers(1, 29))
            hour = int(rng.integers(10, 23) if fire_season else rng.integers(0, 24))
            timestamp = pd.Timestamp(year=year, month=month, day=day, hour=hour)

            high_fuel = fuels.sort_values("fuel_load_tons_per_acre", ascending=False).head(1500)
            cell = high_fuel.sample(1, random_state=int(rng.integers(0, 1_000_000))).iloc[0]

            cause = str(rng.choice(CAUSES, p=[0.20, 0.28, 0.38, 0.14]))
            final_acres = float(np.clip(rng.lognormal(mean=3.2, sigma=1.25), 0.1, 50_000))
            suppression_hours = float(np.clip(2.5 + final_acres ** 0.48 + rng.normal(0, 6), 1, 240))
            structures_lost = int(max(0, rng.poisson(final_acres / 850) - (0 if cause == "powerline" else 1)))
            outage_event_id = None
            if cause == "powerline" and vegetation_outages and rng.random() < 0.35:
                outage_event_id = vegetation_outages[event_num % len(vegetation_outages)]

            events.append(
                {
                    "ignition_id": f"IGN-{year}-{event_num:05d}",
                    "timestamp": timestamp,
                    "lat": round(float(cell["lat"]) + rng.normal(0, 0.0015), 6),
                    "lon": round(float(cell["lon"]) + rng.normal(0, 0.0015), 6),
                    "cause": cause,
                    "final_acres": round(final_acres, 2),
                    "suppression_hours": round(suppression_hours, 1),
                    "structures_lost": structures_lost,
                    "outage_event_id": outage_event_id,
                }
            )
            event_num += 1

    df = pd.DataFrame(events).sort_values("timestamp").reset_index(drop=True)
    destination = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destination, index=False)
    return df


def load_fire_history(path: str | Path | None = None) -> pd.DataFrame:
    """Load generated fire history records."""
    source = Path(path) if path is not None else DEFAULT_OUTPUT_PATH
    if not source.exists():
        raise FileNotFoundError(f"fire_history.parquet not found at {source}")
    return pd.read_parquet(source)


if __name__ == "__main__":
    generated = generate_fire_history()
    print(f"Generated {len(generated)} fire history records at {DEFAULT_OUTPUT_PATH}")
