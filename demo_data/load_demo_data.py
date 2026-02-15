#!/usr/bin/env python3
"""
Combined data loader for the Sisyphean Power & Light demo datasets.

SYNTHETIC DATA NOTICE
    Sisyphean Power & Light (SP&L) is an entirely fictional utility.
    All data loaded by this module is computationally generated.
    No real customer, infrastructure, or operational data is included.

Provides functions to load each dataset individually or all at once.
Returns pandas DataFrames with appropriate dtypes and indices.

Common keys across all infrastructure datasets:
  - substation_id  (present on every table)
  - feeder_id      (present on feeders and all downstream tables)
  - transformer_id (present on transformers and all downstream tables)
  - customer_id    (present on customers, solar, and EV chargers)

Data sources:
  - If the sisyphean-power-and-light/ (V2) directory is present, core datasets
    (outages, weather, transformers, load profiles, AMI) are read from V2 files
    and columns are renamed to match the guide-friendly API contract.
  - If V2 is not found, all data is read from demo_data/ (V1) CSV files.
  - Network, solar, EV, battery, and scenario datasets always read from V1.

Usage:
    from demo_data.load_demo_data import load_all, load_substations, ...

    # Load everything
    data = load_all()
    print(data["substations"].head())

    # Load individual datasets
    subs = load_substations()
    feeders = load_feeders()
"""

import os
from typing import Dict, Optional

try:
    import pandas as pd
except ImportError:
    raise ImportError(
        "pandas is required to use the data loader. "
        "Install it with: pip install pandas"
    )

try:
    import numpy as np
except ImportError:
    np = None

V1_DIR = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.join(os.path.dirname(V1_DIR), "sisyphean-power-and-light")
USE_V2 = os.path.isdir(V2_DIR)

DATA_DIR = V1_DIR  # kept for backward compatibility


def _csv_path(filename: str) -> str:
    """Return the full path to a CSV file in the demo data directory.

    If the uncompressed CSV is not found but a .csv.gz version exists,
    returns the gzipped path (pandas reads gzip transparently).
    """
    path = os.path.join(V1_DIR, filename)
    if not os.path.exists(path):
        gz_path = path + ".gz"
        if os.path.exists(gz_path):
            return gz_path
    return path


def _feeder_to_substation(feeder_id: str) -> str:
    """Derive substation_id from feeder_id (FDR-00XX -> SUB-0XX)."""
    try:
        num = int(feeder_id.split("-")[1])
        sub_num = ((num - 1) // 5) + 1
        return f"SUB-{sub_num:03d}"
    except (IndexError, ValueError):
        return "SUB-001"


# ---------------------------------------------------------------------------
# Individual loaders
# ---------------------------------------------------------------------------


def load_substations() -> pd.DataFrame:
    """Load the substations dataset.

    Contains 15 substations with capacity, voltage levels, and location data.
    Coordinates are placed at real Phoenix, AZ street intersections.
    """
    df = pd.read_csv(_csv_path("substations.csv"))
    df.set_index("substation_id", inplace=True)
    return df


def load_feeders() -> pd.DataFrame:
    """Load the feeders (distribution lines) dataset.

    Contains ~65 feeders linked to substations with head/tail coordinates,
    direction (N/S/E/W along the Phoenix street grid), conductor specs,
    capacity, and customer counts.
    """
    df = pd.read_csv(_csv_path("feeders.csv"))
    df.set_index("feeder_id", inplace=True)
    return df


def load_transformers() -> pd.DataFrame:
    """Load the distribution transformers dataset.

    Source: sisyphean-power-and-light/assets/transformers.csv (V2)
    Falls back to demo_data/transformers.csv (V1) if V2 not found.

    Contains ~21,000 transformers placed at intervals along feeder routes
    with ratings, phase configuration, and manufacturer info.
    """
    if USE_V2:
        v2_path = os.path.join(V2_DIR, "assets", "transformers.csv")
        df = pd.read_csv(v2_path)

        # Rename columns: kva_rating -> rated_kva
        df = df.rename(columns={
            "kva_rating": "rated_kva",
        })

        # Derive substation_id from feeder_id
        if "substation_id" not in df.columns:
            df["substation_id"] = df["feeder_id"].apply(_feeder_to_substation)

        # Derive columns present in V1 but not in V2
        if "status" not in df.columns:
            df["status"] = "active"
        if "phase" not in df.columns:
            phases = ["A", "B", "C", "AB", "BC", "AC", "ABC"]
            rng = np.random.RandomState(42) if np is not None else None
            if rng is not None:
                df["phase"] = rng.choice(phases, size=len(df))
            else:
                df["phase"] = "ABC"
        if "primary_voltage_kv" not in df.columns:
            df["primary_voltage_kv"] = 12.47
        if "secondary_voltage_v" not in df.columns:
            df["secondary_voltage_v"] = df["rated_kva"].apply(
                lambda kva: 480 if kva >= 500 else (208 if kva >= 50 else 240)
            )
        if "latitude" not in df.columns:
            rng = np.random.RandomState(99) if np is not None else None
            if rng is not None:
                df["latitude"] = 33.45 + rng.normal(0, 0.05, size=len(df))
                df["longitude"] = -112.07 + rng.normal(0, 0.05, size=len(df))
            else:
                df["latitude"] = 33.45
                df["longitude"] = -112.07

        df.set_index("transformer_id", inplace=True)
        return df
    else:
        df = pd.read_csv(_csv_path("transformers.csv"))
        # Rename V1 column to match adapter contract
        df = df.rename(columns={"kva_rating": "rated_kva"})
        df.set_index("transformer_id", inplace=True)
        return df


def load_customers() -> pd.DataFrame:
    """Load the customers dataset.

    Contains ~141,000 customers clustered around their service transformers
    with type classifications and DER adoption flags.
    """
    df = pd.read_csv(_csv_path("customers.csv"))
    df.set_index("customer_id", inplace=True)
    df["has_solar"] = df["has_solar"].astype(bool)
    df["has_ev"] = df["has_ev"].astype(bool)
    df["has_battery"] = df["has_battery"].astype(bool)
    return df


def load_load_profiles() -> pd.DataFrame:
    """Load the feeder-level load profiles.

    Source: sisyphean-power-and-light/timeseries/substation_load_hourly.parquet (V2)
    Falls back to demo_data/load_profiles.csv (V1) if V2 not found.

    Contains hourly load data per feeder with derived reactive power,
    voltage, and power factor columns.
    """
    if USE_V2:
        v2_path = os.path.join(V2_DIR, "timeseries", "substation_load_hourly.parquet")
        df = pd.read_parquet(v2_path)

        # Rename columns: total_load_mw -> load_mw
        df = df.rename(columns={
            "total_load_mw": "load_mw",
        })

        # Derive substation_id from feeder_id
        if "substation_id" not in df.columns:
            df["substation_id"] = df["feeder_id"].apply(_feeder_to_substation)

        # Derive additional columns
        df["load_mvar"] = df["load_mw"] * 0.3

        if np is not None:
            rng = np.random.RandomState(42)
            df["voltage_pu"] = 1.0 + rng.normal(0, 0.01, size=len(df))
            pf_noise = rng.normal(0, 0.02, size=len(df))
            df["power_factor"] = (0.95 + pf_noise).clip(0.85, 1.0)
        else:
            df["voltage_pu"] = 1.0
            df["power_factor"] = 0.95

        return df
    else:
        df = pd.read_csv(_csv_path("load_profiles.csv"), parse_dates=["timestamp"])
        return df


def load_customer_interval_data() -> pd.DataFrame:
    """Load the 15-minute AMI customer interval data.

    Source: sisyphean-power-and-light/timeseries/ami_15min_sample.parquet (V2)
    Falls back to demo_data/customer_interval_data.csv (V1) if V2 not found.

    Contains one representative week per season per year for ~500 sampled
    customers stratified by type (residential, commercial, industrial,
    municipal). Each record includes demand_kw, energy_kwh, voltage, and
    power factor.
    """
    if USE_V2:
        v2_path = os.path.join(V2_DIR, "timeseries", "ami_15min_sample.parquet")
        df = pd.read_parquet(v2_path)
        return df
    else:
        df = pd.read_csv(_csv_path("customer_interval_data.csv"),
                          parse_dates=["timestamp"])
        return df


def load_solar_installations() -> pd.DataFrame:
    """Load the solar PV installation registry.

    Contains ~17,000 solar installations linked through the full hierarchy:
    customer -> transformer -> feeder -> substation.
    """
    df = pd.read_csv(_csv_path("solar_installations.csv"),
                      parse_dates=["install_date"])
    df.set_index("solar_id", inplace=True)
    return df


def load_solar_profiles() -> pd.DataFrame:
    """Load the solar generation profile curves.

    Contains representative hourly generation patterns for each month
    of the year with clear-sky factor and GHI.
    """
    df = pd.read_csv(_csv_path("solar_profiles.csv"), parse_dates=["timestamp"])
    return df


def load_ev_chargers() -> pd.DataFrame:
    """Load the EV charger registry.

    Contains ~11,000 EV chargers linked through the full hierarchy:
    customer -> transformer -> feeder -> substation.
    """
    df = pd.read_csv(_csv_path("ev_chargers.csv"),
                      parse_dates=["install_date"])
    df.set_index("charger_id", inplace=True)
    return df


def load_battery_installations() -> pd.DataFrame:
    """Load the battery storage installation registry.

    Contains battery installations linked through the full hierarchy:
    customer -> transformer -> feeder -> substation.
    """
    df = pd.read_csv(_csv_path("battery_installations.csv"),
                      parse_dates=["install_date"])
    df.set_index("battery_id", inplace=True)
    return df


def load_ev_charging_profiles() -> pd.DataFrame:
    """Load the typical EV charging load shape profiles.

    Contains hourly load percentages for residential, commercial, and
    DCFC charger types on weekdays and weekends.
    """
    df = pd.read_csv(_csv_path("ev_charging_profiles.csv"))
    return df


def load_weather_data() -> pd.DataFrame:
    """Load the hourly weather dataset.

    Source: sisyphean-power-and-light/weather/hourly_observations.csv (V2)
    Falls back to demo_data/weather_data.csv (V1) if V2 not found.

    Contains hourly records with temperature, humidity, wind, precipitation,
    heatwave flags, and storm flags for a Phoenix-like climate.
    """
    if USE_V2:
        v2_path = os.path.join(V2_DIR, "weather", "hourly_observations.csv")
        df = pd.read_csv(v2_path, parse_dates=["timestamp"])

        # Rename columns to match guide contract
        df = df.rename(columns={
            "temperature": "temperature_f",
            "wind_speed": "wind_speed_mph",
            "humidity": "humidity_pct",
        })

        # Compute is_storm: precipitation > 0.1 OR wind_speed_mph > 35
        df["is_storm"] = (df["precipitation"] > 0.1) | (df["wind_speed_mph"] > 35)

        # Compute is_heatwave: rolling 3-hour window where temperature_f > 110
        # Mark an hour as heatwave=True if temperature_f > 110 for that hour
        # AND the prior 2 hours
        hot = (df["temperature_f"] > 110).astype(int)
        rolling_sum = hot.rolling(window=3, min_periods=3).sum()
        df["is_heatwave"] = (rolling_sum >= 3)

        return df
    else:
        df = pd.read_csv(_csv_path("weather_data.csv"), parse_dates=["timestamp"])
        # Rename V1 columns to match adapter contract
        df = df.rename(columns={
            "temperature": "temperature_f",
            "wind_speed": "wind_speed_mph",
            "humidity": "humidity_pct",
        })
        df["is_heatwave"] = df["is_heatwave"].astype(bool)
        df["is_storm"] = df["is_storm"].astype(bool)
        return df


def load_growth_scenarios() -> pd.DataFrame:
    """Load the scenario planning projections.

    Contains 5 scenarios (Reference, High EV, High Solar, Extreme Heat,
    Full Electrification) projected from 2024 to 2040 with adoption
    rates and load growth percentages.
    """
    df = pd.read_csv(_csv_path("growth_scenarios.csv"))
    df.set_index(["scenario_id", "year"], inplace=True)
    return df


def load_outage_history() -> pd.DataFrame:
    """Load the feeder-level outage/reliability history.

    Source: sisyphean-power-and-light/outages/outage_events.csv (V2)
    Falls back to demo_data/outage_history.csv (V1) if V2 not found.

    Contains outage events linked to feeders with cause, duration,
    customers affected, and equipment involved.
    """
    if USE_V2:
        v2_path = os.path.join(V2_DIR, "outages", "outage_events.csv")
        df = pd.read_csv(v2_path, parse_dates=["fault_detected", "service_restored"])

        # Rename columns to match guide contract
        df = df.rename(columns={
            "fault_detected": "start_time",
            "service_restored": "end_time",
            "cause_code": "cause",
            "affected_customers": "customers_affected",
            "transformer_id": "equipment_involved",
        })

        # Compute duration_hours
        df["duration_hours"] = (
            (df["end_time"] - df["start_time"]).dt.total_seconds() / 3600
        )

        # Compute weather_related
        df["weather_related"] = (df["cause"] == "weather")

        # Derive substation_id from feeder_id
        # Try to join from feeder_summary if available
        feeder_summary_path = os.path.join(V2_DIR, "network", "feeder_summary.csv")
        if os.path.exists(feeder_summary_path):
            fs = pd.read_csv(feeder_summary_path)
            if "substation_id" in fs.columns:
                feeder_sub_map = fs.set_index("feeder_id")["substation_id"].to_dict()
                df["substation_id"] = df["feeder_id"].map(feeder_sub_map)
            else:
                df["substation_id"] = df["feeder_id"].apply(_feeder_to_substation)
        else:
            df["substation_id"] = df["feeder_id"].apply(_feeder_to_substation)

        # Generate sequential outage_id index
        df["outage_id"] = [f"OUT-{i+1:05d}" for i in range(len(df))]
        df.set_index("outage_id", inplace=True)

        return df
    else:
        df = pd.read_csv(_csv_path("outage_history.csv"),
                          parse_dates=["fault_detected", "service_restored"])
        # Rename V1 columns to match adapter contract
        df = df.rename(columns={
            "fault_detected": "start_time",
            "service_restored": "end_time",
            "cause_code": "cause",
            "affected_customers": "customers_affected",
        })
        # Compute duration_hours if not present
        if "duration_hours" not in df.columns:
            df["duration_hours"] = (
                (df["end_time"] - df["start_time"]).dt.total_seconds() / 3600
            )
        df["weather_related"] = df["weather_related"].astype(bool)
        df.set_index("outage_id", inplace=True)
        return df


def load_network_nodes() -> pd.DataFrame:
    """Load the network nodes (point features) table.

    Contains ~44,000 nodes representing every distinct network location:
    substation buses, feeder breakers, junctions, protective devices
    (fuses, reclosers, sectionalizers), transformers, tie switches,
    and feeder endpoints.  Each node has a geometry (lat/lon), equipment
    class, rated capacity, and the common feeder_id/substation_id keys.

    Follows ESRI geodatabase / GIS conventions — pair with
    load_network_edges() for the full topology.
    """
    df = pd.read_csv(_csv_path("network_nodes.csv"))
    df.set_index("node_id", inplace=True)
    return df


def load_network_edges() -> pd.DataFrame:
    """Load the network edges (polyline features) table.

    Contains ~44,000 edges representing every conductor segment:
    bus ties, primary trunk (overhead/underground), laterals, and
    tie connections between feeders.  References from_node_id /
    to_node_id (foreign keys into the nodes table).  Carries
    impedance (R, X, Z0), conductor type, phase, length, and rated amps.

    Follows ESRI geodatabase / GIS conventions — pair with
    load_network_nodes() for the full topology.
    """
    df = pd.read_csv(_csv_path("network_edges.csv"))
    df.set_index("edge_id", inplace=True)
    df["is_overhead"] = df["is_overhead"].astype(bool)
    return df


# ---------------------------------------------------------------------------
# Combined loader
# ---------------------------------------------------------------------------


def load_all(datasets: Optional[list] = None) -> Dict[str, pd.DataFrame]:
    """Load all (or selected) demo datasets into a dictionary.

    Args:
        datasets: Optional list of dataset names to load. If None, loads all.
            Valid names: substations, feeders, transformers, customers,
            load_profiles, customer_interval_data, solar_installations,
            solar_profiles, ev_chargers, ev_charging_profiles, weather_data,
            growth_scenarios, outage_history, network_nodes, network_edges

    Returns:
        Dictionary mapping dataset name to DataFrame.

    Example:
        >>> data = load_all()
        >>> data["substations"].head()
        >>> data = load_all(["network_nodes", "network_edges"])
    """
    loaders = {
        "substations": load_substations,
        "feeders": load_feeders,
        "transformers": load_transformers,
        "customers": load_customers,
        "load_profiles": load_load_profiles,
        "customer_interval_data": load_customer_interval_data,
        "solar_installations": load_solar_installations,
        "solar_profiles": load_solar_profiles,
        "ev_chargers": load_ev_chargers,
        "ev_charging_profiles": load_ev_charging_profiles,
        "battery_installations": load_battery_installations,
        "weather_data": load_weather_data,
        "growth_scenarios": load_growth_scenarios,
        "outage_history": load_outage_history,
        "network_nodes": load_network_nodes,
        "network_edges": load_network_edges,
    }

    if datasets is not None:
        invalid = set(datasets) - set(loaders)
        if invalid:
            raise ValueError(
                f"Unknown datasets: {invalid}. "
                f"Valid names: {sorted(loaders.keys())}"
            )
        loaders = {k: v for k, v in loaders.items() if k in datasets}

    return {name: loader() for name, loader in loaders.items()}


def summary() -> None:
    """Print a summary of all available demo datasets."""
    print("Sisyphean Power & Light — Synthetic Demo Datasets")
    print("(Fictional utility — all data is computationally generated)")
    print(f"Data source: {'V2 (sisyphean-power-and-light/)' if USE_V2 else 'V1 (demo_data/)'}")
    print("=" * 55)
    data = load_all()
    total_rows = 0
    for name, df in data.items():
        rows = len(df)
        cols = len(df.columns)
        total_rows += rows
        print(f"  {name:<25s} {rows:>8,} rows x {cols:>3} cols")
    print("-" * 55)
    print(f"  {'TOTAL':<25s} {total_rows:>8,} rows")
    print()


if __name__ == "__main__":
    summary()
