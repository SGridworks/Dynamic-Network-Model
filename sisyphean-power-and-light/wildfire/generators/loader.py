import pandas as pd
import os

def load_wind_direction_data(path='generators/wind_direction_hourly.parquet'):
    """Load wind direction parquet file if it exists"""
    if os.path.exists(path):
        return pd.read_parquet(path)
    raise FileNotFoundError(f"Parquet file {path} not found")

if __name__ == '__main__':
    try:
        df = load_wind_direction_data()
        print("Loaded wind direction data:")
        print(df.head())
    except FileNotFoundError as e:
        print(f"Error: {e}")
        exit(1)