#!/usr/bin/env python3
"""
Combined data loader for the Dynamic Network Model demo datasets.

Provides functions to load each dataset individually or all at once.
Returns pandas DataFrames with appropriate dtypes and indices.

Common keys across all infrastructure datasets:
  - substation_id  (present on every table)
  - feeder_id      (present on feeders and all downstream tables)
  - transformer_id (present on transformers and all downstream tables)
  - customer_id    (present on customers, solar, and EV chargers)

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

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def _csv_path(filename: str) -> str:
    """Return the full path to a CSV file in the demo data directory."""
    return os.path.join(DATA_DIR, filename)


# ---------------------------------------------------------------------------
# Individual loaders
# ---------------------------------------------------------------------------


def load_substations() -> pd.DataFrame:
    """Load the substations dataset.

    Contains 15 substations with capacity, voltage levels, and location data.
    """
    df = pd.read_csv(_csv_path("substations.csv"))
    df.set_index("substation_id", inplace=True)
    return df


def load_feeders() -> pd.DataFrame:
    """Load the feeders (distribution lines) dataset.

    Contains ~70 feeders linked to substations with head/tail coordinates,
    conductor specs, capacity, and customer counts.
    """
    df = pd.read_csv(_csv_path("feeders.csv"))
    df.set_index("feeder_id", inplace=True)
    return df


def load_transformers() -> pd.DataFrame:
    """Load the distribution transformers dataset.

    Contains ~25,000 transformers linked to feeders and substations with
    ratings, phase configuration, and manufacturer info.
    """
    df = pd.read_csv(_csv_path("transformers.csv"))
    df.set_index("transformer_id", inplace=True)
    return df


def load_customers() -> pd.DataFrame:
    """Load the customers dataset.

    Contains ~166,000 customers linked to transformers, feeders, and
    substations with type classifications and DER adoption flags.
    """
    df = pd.read_csv(_csv_path("customers.csv"))
    df.set_index("customer_id", inplace=True)
    df["has_solar"] = df["has_solar"].astype(bool)
    df["has_ev"] = df["has_ev"].astype(bool)
    df["has_battery"] = df["has_battery"].astype(bool)
    return df


def load_load_profiles() -> pd.DataFrame:
    """Load the feeder-level hourly load profiles.

    Contains representative weeks for each season (winter, spring,
    summer, fall) for every feeder — 672 hours per feeder.
    """
    df = pd.read_csv(_csv_path("load_profiles.csv"), parse_dates=["timestamp"])
    return df


def load_solar_installations() -> pd.DataFrame:
    """Load the solar PV installation registry.

    Contains ~20,000 solar installations linked through the full hierarchy:
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

    Contains ~13,000 EV chargers linked through the full hierarchy:
    customer -> transformer -> feeder -> substation.
    """
    df = pd.read_csv(_csv_path("ev_chargers.csv"),
                      parse_dates=["install_date"])
    df.set_index("charger_id", inplace=True)
    return df


def load_ev_charging_profiles() -> pd.DataFrame:
    """Load the typical EV charging load shape profiles.

    Contains hourly load percentages for residential, commercial, and
    DCFC charger types on weekdays and weekends.
    """
    df = pd.read_csv(_csv_path("ev_charging_profiles.csv"))
    return df


def load_weather_data() -> pd.DataFrame:
    """Load the hourly weather dataset (full year).

    Contains 8,760 hourly records with temperature, humidity, wind,
    solar irradiance, and heatwave flags for a Phoenix-like climate.
    """
    df = pd.read_csv(_csv_path("weather_data.csv"), parse_dates=["timestamp"])
    df["is_heatwave"] = df["is_heatwave"].astype(bool)
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

    Contains outage events for 2024 linked to feeders and substations,
    with cause, duration, customers affected, and equipment involved.
    """
    df = pd.read_csv(_csv_path("outage_history.csv"),
                      parse_dates=["start_time", "end_time"])
    df["weather_related"] = df["weather_related"].astype(bool)
    df.set_index("outage_id", inplace=True)
    return df


def load_network_nodes() -> pd.DataFrame:
    """Load the network nodes (point features) table.

    Contains ~26,000 nodes representing every distinct network location:
    substation buses, feeder breakers, junction/tap points, transformers,
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

    Contains ~26,000 edges representing every conductor segment:
    bus ties, primary trunk (overhead/underground), laterals, etc.
    References from_node_id / to_node_id (foreign keys into the
    nodes table).  Carries impedance (R, X, Z0), conductor type,
    phase, length, and rated amps.

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
            load_profiles, solar_installations, solar_profiles, ev_chargers,
            ev_charging_profiles, weather_data, growth_scenarios,
            outage_history, network_nodes, network_edges

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
        "solar_installations": load_solar_installations,
        "solar_profiles": load_solar_profiles,
        "ev_chargers": load_ev_chargers,
        "ev_charging_profiles": load_ev_charging_profiles,
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
    print("Dynamic Network Model — Demo Datasets")
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
