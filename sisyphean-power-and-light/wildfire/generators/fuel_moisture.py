#!/usr/bin/env python3
"""Generate synthetic daily fuel moisture time series for SP&L.

SYNTHETIC DATA NOTICE
    Sisyphean Power & Light (SP&L) is an entirely fictional utility.
    All fuel moisture data generated here is synthetic and Phoenix-offset.
    No real ecological, utility, or land-management data is included.

Methodology
    Dead-fuel moisture uses a simplified Nelson (1984) EMC approach:
    equilibrium moisture content driven by temperature and RH, plus a
    bounded random walk to simulate 10-h and 100-h lag classes.

    Live-fuel moisture uses a seasonal sine wave (peak mid-winter,
    trough mid-summer) typical of chaparral, with a multi-week lag
    applied via exponential smoothing.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


WILDFIRE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = WILDFIRE_DIR / "fuel_moisture_daily.parquet"

# SP&L Phoenix-offset climate baseline
_MEAN_TEMP_F = 85.0
_TEMP_AMPLITUDE_F = 22.0
_MEAN_RH_PCT = 28.0
_RH_AMPLITUDE_PCT = 14.0

# Nelson EMC constants (simplified)
_EMC_A, _EMC_B, _EMC_C = 0.618, 0.00472, 0.00035


def _emc(temp_f: np.ndarray, rh_pct: np.ndarray) -> np.ndarray:
    """Equilibrium moisture content (%) — Nelson 1984 simplified form."""
    rh = np.clip(rh_pct, 1.0, 99.0)
    return _EMC_A + _EMC_B * rh - _EMC_C * temp_f


def generate_fuel_moisture(
    n_days: int = 365,
    seed: int = 42,
    start_date: str = "2024-01-01",
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Generate daily dead-fuel and live-fuel moisture over the SP&L footprint.

    Columns
    -------
    date                    : date (daily cadence)
    temp_f                  : synthetic daily mean temperature (°F)
    rh_pct                  : synthetic daily mean relative humidity (%)
    emc_pct                 : Nelson equilibrium moisture content (%)
    fm_1h_pct               : 1-h dead-fuel moisture (%)
    fm_10h_pct              : 10-h dead-fuel moisture (%)
    fm_100h_pct             : 100-h dead-fuel moisture (%)
    live_herb_pct           : live herbaceous moisture (%)
    live_woody_pct          : live woody / chaparral moisture (%)
    """
    if n_days <= 0:
        raise ValueError("n_days must be positive")

    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start_date, periods=n_days, freq="D")
    doy = dates.day_of_year.to_numpy(dtype=float)

    # Seasonal temperature: peaks mid-summer (~DOY 196)
    temp_f = (
        _MEAN_TEMP_F
        + _TEMP_AMPLITUDE_F * np.sin(2 * np.pi * (doy - 80) / 365)
        + rng.normal(0, 3.5, n_days)
    )

    # Seasonal RH: inversely correlated with temperature
    rh_pct = np.clip(
        _MEAN_RH_PCT
        - _RH_AMPLITUDE_PCT * np.sin(2 * np.pi * (doy - 80) / 365)
        + rng.normal(0, 4.0, n_days),
        5.0,
        95.0,
    )

    emc = _emc(temp_f, rh_pct)

    # 1-h fuel: tracks EMC almost immediately (small noise)
    fm_1h = np.clip(emc + rng.normal(0, 0.8, n_days), 1.0, 35.0)

    # 10-h fuel: exponential lag (time constant ~10 days)
    fm_10h = np.empty(n_days)
    fm_10h[0] = emc[0]
    alpha_10 = 1 - np.exp(-1 / 10)
    for i in range(1, n_days):
        fm_10h[i] = fm_10h[i - 1] + alpha_10 * (emc[i] - fm_10h[i - 1])
    fm_10h = np.clip(fm_10h + rng.normal(0, 0.5, n_days), 1.0, 35.0)

    # 100-h fuel: exponential lag (time constant ~100 days)
    fm_100h = np.empty(n_days)
    fm_100h[0] = emc[0]
    alpha_100 = 1 - np.exp(-1 / 100)
    for i in range(1, n_days):
        fm_100h[i] = fm_100h[i - 1] + alpha_100 * (emc[i] - fm_100h[i - 1])
    fm_100h = np.clip(fm_100h + rng.normal(0, 0.3, n_days), 2.0, 30.0)

    # Live herbaceous: seasonal sine, peaks winter (~DOY 30), troughs summer
    live_herb = np.clip(
        80.0
        + 80.0 * np.cos(2 * np.pi * (doy - 30) / 365)
        + rng.normal(0, 8.0, n_days),
        30.0,
        200.0,
    )

    # Live woody (chaparral): deeper seasonal lag (~60-day smoothing)
    live_herb_signal = (
        80.0 + 80.0 * np.cos(2 * np.pi * (doy - 30) / 365)
    )
    live_woody = np.empty(n_days)
    live_woody[0] = live_herb_signal[0]
    alpha_woody = 1 - np.exp(-1 / 60)
    for i in range(1, n_days):
        live_woody[i] = live_woody[i - 1] + alpha_woody * (
            live_herb_signal[i] - live_woody[i - 1]
        )
    live_woody = np.clip(live_woody + rng.normal(0, 5.0, n_days), 50.0, 200.0)

    df = pd.DataFrame(
        {
            "date": dates,
            "temp_f": temp_f.round(1),
            "rh_pct": rh_pct.round(1),
            "emc_pct": emc.round(2),
            "fm_1h_pct": fm_1h.round(2),
            "fm_10h_pct": fm_10h.round(2),
            "fm_100h_pct": fm_100h.round(2),
            "live_herb_pct": live_herb.round(1),
            "live_woody_pct": live_woody.round(1),
        }
    )

    destination = Path(output_path) if output_path is not None else DEFAULT_OUTPUT_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destination, index=False)
    return df


def load_fuel_moisture(path: str | Path | None = None) -> pd.DataFrame:
    """Load generated fuel-moisture time series."""
    source = Path(path) if path is not None else DEFAULT_OUTPUT_PATH
    if not source.exists():
        raise FileNotFoundError(f"fuel_moisture_daily.parquet not found at {source}")
    return pd.read_parquet(source)


if __name__ == "__main__":
    generated = generate_fuel_moisture()
    print(f"Generated {len(generated)} daily fuel moisture records at {DEFAULT_OUTPUT_PATH}")
