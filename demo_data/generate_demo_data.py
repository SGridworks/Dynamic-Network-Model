#!/usr/bin/env python3
"""
Generate synthetic demo datasets for the Dynamic Network Model.

SYNTHETIC DATA NOTICE
    Sisyphean Power & Light (SP&L) is an entirely fictional utility.
    All data produced by this script is computationally generated.
    No real customer, infrastructure, or operational data is included.

Creates realistic utility distribution system data modeled after SP&L,
a fictional mid-size electric utility serving ~166,000 customers across
a mixed suburban/rural service territory (Phoenix, AZ area).

Coordinates cascade through the network hierarchy:
  Substation -> Feeder head -> Transformer -> Customer -> DER
so that all lat/long values are spatially rational.

Every downstream record carries feeder_id and substation_id as common keys
to enable easy joins across all datasets.

Each dataset is written to a separate CSV file in the demo_data/ directory.
"""

import csv
import math
import os
import random
from datetime import datetime, timedelta

random.seed(42)

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Service territory center (Phoenix, AZ metro)
# ---------------------------------------------------------------------------
CENTER_LAT = 33.45
CENTER_LON = -112.07

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def write_csv(filename, headers, rows):
    """Write rows to a CSV file in the demo_data directory."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"  wrote {len(rows):>6,} rows -> {filename}")


def offset_coord(lat, lon, radius_deg):
    """Return a (lat, lon) randomly offset from a center within radius_deg."""
    angle = random.uniform(0, 2 * math.pi)
    dist = random.uniform(0, radius_deg)
    new_lat = lat + dist * math.sin(angle)
    new_lon = lon + dist * math.cos(angle)
    return round(new_lat, 6), round(new_lon, 6)


def point_along_line(lat1, lon1, lat2, lon2, fraction):
    """Return a point at *fraction* of the way from (lat1,lon1) to (lat2,lon2)
    with a small perpendicular jitter to avoid a perfectly straight line."""
    lat = lat1 + fraction * (lat2 - lat1)
    lon = lon1 + fraction * (lon2 - lon1)
    # Small perpendicular jitter (~30 m)
    jitter = random.uniform(-0.0003, 0.0003)
    return round(lat + jitter, 6), round(lon + jitter, 6)


# ---------------------------------------------------------------------------
# 1. Substations — spread across the service territory
# ---------------------------------------------------------------------------

def generate_substations():
    print("Generating substations...")
    headers = [
        "substation_id", "name", "latitude", "longitude",
        "voltage_high_kv", "voltage_low_kv", "rated_capacity_mva",
        "peak_load_mva", "num_transformers", "age_years", "status",
    ]
    names = [
        "Riverside", "Mesa Grande", "Copper Hills", "Ironwood",
        "Desert View", "Palo Verde", "Saguaro", "Sunridge",
        "Cottonwood", "Red Mountain", "Baseline", "Tempe Junction",
        "Gilbert Road", "Chandler Heights", "Ocotillo",
    ]
    # Place substations in a rough grid so they are well-distributed
    grid_positions = [
        (-0.15, -0.15), (-0.15, 0.0), (-0.15, 0.15),
        (-0.05, -0.20), (-0.05, -0.07), (-0.05, 0.07), (-0.05, 0.20),
        (0.05, -0.20), (0.05, -0.07), (0.05, 0.07), (0.05, 0.20),
        (0.15, -0.15), (0.15, 0.0), (0.15, 0.10), (0.15, 0.20),
    ]
    rows = []
    for i, name in enumerate(names, start=1):
        dlat, dlon = grid_positions[i - 1]
        lat = round(CENTER_LAT + dlat + random.uniform(-0.02, 0.02), 6)
        lon = round(CENTER_LON + dlon + random.uniform(-0.02, 0.02), 6)
        v_high = random.choice([69, 115, 230])
        v_low = random.choice([12.47, 13.8, 24.9])
        capacity = random.choice([20, 30, 40, 50, 60, 80])
        peak = round(capacity * random.uniform(0.55, 0.92), 1)
        n_xfmrs = random.randint(1, 3)
        age = random.randint(5, 55)
        status = "active" if random.random() > 0.05 else "planned"
        rows.append([
            f"SUB-{i:03d}", name, lat, lon,
            v_high, v_low, capacity, peak, n_xfmrs, age, status,
        ])
    write_csv("substations.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 2. Feeders — radiate outward from their parent substation
# ---------------------------------------------------------------------------

def generate_feeders(substations):
    print("Generating feeders...")
    headers = [
        "feeder_id", "substation_id", "name", "voltage_kv",
        "latitude_head", "longitude_head",
        "latitude_tail", "longitude_tail",
        "length_miles", "conductor_type", "rated_capacity_mw",
        "peak_load_mw", "num_customers", "status",
    ]
    conductors = [
        "336 ACSR", "477 ACSR", "795 ACSR", "1/0 AL", "4/0 AL", "397.5 AAC",
    ]
    rows = []
    feeder_num = 0
    for sub in substations:
        sub_id = sub[0]
        sub_lat, sub_lon = float(sub[2]), float(sub[3])
        v_low = sub[5]
        n_feeders = random.randint(2, 6)
        # Spread feeders evenly around the substation
        base_angle = random.uniform(0, 2 * math.pi)
        for j in range(n_feeders):
            feeder_num += 1
            angle = base_angle + (2 * math.pi * j / n_feeders) + random.uniform(-0.3, 0.3)
            length_miles = round(random.uniform(2.0, 18.0), 1)
            # Convert miles to approximate degrees (1 deg lat ≈ 69 miles)
            reach_deg = length_miles / 69.0
            tail_lat = round(sub_lat + reach_deg * math.sin(angle), 6)
            tail_lon = round(sub_lon + reach_deg * math.cos(angle), 6)
            conductor = random.choice(conductors)
            capacity = round(random.uniform(8, 20), 1)
            peak = round(capacity * random.uniform(0.4, 0.88), 1)
            customers = random.randint(400, 4500)
            rows.append([
                f"FDR-{feeder_num:04d}", sub_id,
                f"{sub[1]} Fdr {j + 1}", v_low,
                sub_lat, sub_lon, tail_lat, tail_lon,
                length_miles, conductor, capacity, peak, customers, "active",
            ])
    write_csv("feeders.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 3. Transformers — placed along their feeder's route
# ---------------------------------------------------------------------------

def generate_transformers(feeders):
    print("Generating transformers...")
    headers = [
        "transformer_id", "feeder_id", "substation_id",
        "latitude", "longitude",
        "rated_kva", "phase", "primary_voltage_kv", "secondary_voltage_v",
        "age_years", "manufacturer", "status",
    ]
    kva_sizes = [10, 15, 25, 37.5, 50, 75, 100, 167, 250, 333, 500]
    phases = ["A", "B", "C", "AB", "BC", "AC", "ABC"]
    manufacturers = [
        "ABB", "Eaton", "GE", "Siemens", "Howard Industries", "Prolec",
    ]
    rows = []
    xfmr_num = 0
    for fdr in feeders:
        fdr_id = fdr[0]
        sub_id = fdr[1]
        head_lat, head_lon = float(fdr[4]), float(fdr[5])
        tail_lat, tail_lon = float(fdr[6]), float(fdr[7])
        primary_kv = fdr[3]
        num_customers = fdr[12]
        n_xfmrs = max(5, num_customers // random.randint(5, 10))
        for k in range(n_xfmrs):
            xfmr_num += 1
            # Distribute transformers along the feeder route
            fraction = (k + 1) / (n_xfmrs + 1)
            lat, lon = point_along_line(
                head_lat, head_lon, tail_lat, tail_lon, fraction,
            )
            kva = random.choice(kva_sizes)
            phase = random.choice(phases)
            sec_v = random.choice([120, 240, 208, 480])
            age = random.randint(1, 45)
            mfr = random.choice(manufacturers)
            status = "active" if random.random() > 0.02 else "failed"
            rows.append([
                f"XFMR-{xfmr_num:06d}", fdr_id, sub_id, lat, lon,
                kva, phase, primary_kv, sec_v, age, mfr, status,
            ])
    write_csv("transformers.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 4. Customers — clustered around their service transformer
# ---------------------------------------------------------------------------

def generate_customers(transformers):
    print("Generating customers...")
    headers = [
        "customer_id", "transformer_id", "feeder_id", "substation_id",
        "customer_type", "rate_class", "contracted_demand_kw",
        "latitude", "longitude",
        "has_solar", "has_ev", "has_battery",
    ]
    types_weights = [
        ("residential", 0.82),
        ("commercial", 0.13),
        ("industrial", 0.03),
        ("municipal", 0.02),
    ]
    rate_classes = {
        "residential": ["R-1", "R-TOU", "R-EV"],
        "commercial": ["C-1", "C-TOU", "C-DEMAND"],
        "industrial": ["I-1", "I-DEMAND"],
        "municipal": ["M-1"],
    }
    rows = []
    cust_num = 0
    for xfmr in transformers:
        xfmr_id = xfmr[0]
        fdr_id = xfmr[1]
        sub_id = xfmr[2]
        xfmr_lat, xfmr_lon = float(xfmr[3]), float(xfmr[4])
        n_cust = random.randint(1, 12)
        for _ in range(n_cust):
            cust_num += 1
            r = random.random()
            cum = 0
            ctype = "residential"
            for ct, w in types_weights:
                cum += w
                if r <= cum:
                    ctype = ct
                    break
            rate = random.choice(rate_classes[ctype])
            if ctype == "residential":
                demand = round(random.uniform(3, 15), 1)
            elif ctype == "commercial":
                demand = round(random.uniform(20, 500), 1)
            elif ctype == "industrial":
                demand = round(random.uniform(200, 5000), 1)
            else:
                demand = round(random.uniform(10, 200), 1)
            # Customers within ~150 m of their transformer
            lat, lon = offset_coord(xfmr_lat, xfmr_lon, 0.0015)
            has_solar = 1 if random.random() < 0.12 else 0
            has_ev = 1 if random.random() < 0.08 else 0
            has_battery = 1 if random.random() < 0.03 else 0
            rows.append([
                f"CUST-{cust_num:07d}", xfmr_id, fdr_id, sub_id,
                ctype, rate, demand, lat, lon,
                has_solar, has_ev, has_battery,
            ])
    write_csv("customers.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 5. Load profiles (hourly, one representative week per season)
# ---------------------------------------------------------------------------

def generate_load_profiles(feeders):
    print("Generating load profiles (this may take a moment)...")
    headers = [
        "feeder_id", "substation_id", "timestamp",
        "load_mw", "load_mvar", "voltage_pu", "power_factor",
    ]
    seasons = {
        "winter": datetime(2024, 1, 15),
        "spring": datetime(2024, 4, 15),
        "summer": datetime(2024, 7, 15),
        "fall": datetime(2024, 10, 15),
    }
    rows = []
    for fdr in feeders:
        fdr_id = fdr[0]
        sub_id = fdr[1]
        peak_mw = float(fdr[11])
        for season, start_dt in seasons.items():
            if season == "summer":
                season_mult = 1.0
            elif season == "winter":
                season_mult = 0.70
            elif season == "spring":
                season_mult = 0.60
            else:
                season_mult = 0.65
            for hour_offset in range(168):
                ts = start_dt + timedelta(hours=hour_offset)
                hour = ts.hour
                dow = ts.weekday()
                if 0 <= hour < 6:
                    diurnal = 0.45 + 0.05 * math.sin(math.pi * hour / 6)
                elif 6 <= hour < 9:
                    diurnal = 0.50 + 0.25 * ((hour - 6) / 3)
                elif 9 <= hour < 15:
                    diurnal = 0.75 + 0.10 * math.sin(math.pi * (hour - 9) / 6)
                elif 15 <= hour < 20:
                    diurnal = 0.80 + 0.20 * math.sin(math.pi * (hour - 15) / 5)
                else:
                    diurnal = 0.70 - 0.15 * ((hour - 20) / 4)
                if dow >= 5:
                    diurnal *= 0.85
                load_mw = round(
                    peak_mw * season_mult * diurnal * random.uniform(0.92, 1.08), 3
                )
                pf = round(random.uniform(0.88, 0.98), 3)
                load_mvar = round(load_mw * math.tan(math.acos(pf)), 3)
                voltage_pu = round(random.uniform(0.95, 1.05), 4)
                rows.append([
                    fdr_id, sub_id, ts.strftime("%Y-%m-%d %H:%M"),
                    load_mw, load_mvar, voltage_pu, pf,
                ])
    write_csv("load_profiles.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 6. Solar installations — co-located with their customer
# ---------------------------------------------------------------------------

def generate_solar_installations(customers):
    print("Generating solar installations...")
    headers = [
        "solar_id", "customer_id", "transformer_id", "feeder_id",
        "substation_id", "latitude", "longitude",
        "capacity_kw", "panel_type", "azimuth_deg", "tilt_deg",
        "install_date", "inverter_type", "status",
    ]
    panel_types = ["monocrystalline", "polycrystalline", "thin-film"]
    inverter_types = ["string", "micro", "hybrid"]
    rows = []
    sol_num = 0
    solar_custs = [c for c in customers if c[9] == 1]
    for cust in solar_custs:
        sol_num += 1
        cust_id = cust[0]
        xfmr_id = cust[1]
        fdr_id = cust[2]
        sub_id = cust[3]
        lat, lon = float(cust[7]), float(cust[8])
        ctype = cust[4]
        if ctype == "residential":
            capacity = round(random.uniform(3, 12), 1)
        elif ctype == "commercial":
            capacity = round(random.uniform(25, 500), 1)
        else:
            capacity = round(random.uniform(5, 100), 1)
        panel = random.choice(panel_types)
        azimuth = random.randint(150, 210)
        tilt = random.randint(15, 35)
        year = random.randint(2016, 2024)
        month = random.randint(1, 12)
        install_date = f"{year}-{month:02d}-01"
        inverter = random.choice(inverter_types)
        status = "active" if random.random() > 0.02 else "inactive"
        rows.append([
            f"SOL-{sol_num:06d}", cust_id, xfmr_id, fdr_id, sub_id,
            lat, lon, capacity, panel, azimuth, tilt,
            install_date, inverter, status,
        ])
    write_csv("solar_installations.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 7. Solar generation profiles (hourly, representative days)
# ---------------------------------------------------------------------------

def generate_solar_profiles():
    print("Generating solar generation profiles...")
    headers = [
        "timestamp", "clear_sky_factor", "generation_pct_of_capacity",
        "temperature_c", "ghi_w_per_m2",
    ]
    rows = []
    for month in range(1, 13):
        dt = datetime(2024, month, 15)
        sunrise = 5 + 2 * math.cos(math.pi * (month - 6) / 6)
        sunset = 19 - 2 * math.cos(math.pi * (month - 6) / 6)
        day_length = sunset - sunrise
        for hour in range(24):
            ts = dt + timedelta(hours=hour)
            if sunrise <= hour <= sunset and day_length > 0:
                solar_angle = math.pi * (hour - sunrise) / day_length
                clear_sky = round(max(0, math.sin(solar_angle)), 3)
            else:
                clear_sky = 0.0
            cloud_factor = random.uniform(0.7, 1.0) if clear_sky > 0 else 1.0
            gen_pct = round(clear_sky * cloud_factor * 100, 1)
            base_temp = 10 + 20 * math.sin(math.pi * (month - 1) / 11)
            diurnal_temp = (
                8 * math.sin(math.pi * (hour - 6) / 12) if 6 <= hour <= 18 else -3
            )
            temp = round(base_temp + diurnal_temp + random.uniform(-2, 2), 1)
            ghi = round(clear_sky * cloud_factor * 1000, 1)
            rows.append([
                ts.strftime("%Y-%m-%d %H:%M"),
                round(clear_sky * cloud_factor, 3),
                gen_pct, temp, ghi,
            ])
    write_csv("solar_profiles.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 8. EV chargers — co-located with their customer
# ---------------------------------------------------------------------------

def generate_ev_chargers(customers):
    print("Generating EV chargers...")
    headers = [
        "charger_id", "customer_id", "transformer_id", "feeder_id",
        "substation_id", "latitude", "longitude",
        "charger_type", "power_kw", "connector", "install_date",
        "network", "status",
    ]
    charger_types = [
        ("Level 1", 1.4, "NEMA 5-15"),
        ("Level 2", 7.7, "J1772"),
        ("Level 2", 11.5, "J1772"),
        ("Level 2", 19.2, "J1772"),
        ("DCFC", 50, "CCS"),
        ("DCFC", 150, "CCS"),
        ("DCFC", 350, "CCS"),
    ]
    networks = [
        "ChargePoint", "Tesla", "EVgo", "Blink", "Electrify America", "private",
    ]
    rows = []
    ev_num = 0
    ev_custs = [c for c in customers if c[10] == 1]
    for cust in ev_custs:
        ev_num += 1
        cust_id = cust[0]
        xfmr_id = cust[1]
        fdr_id = cust[2]
        sub_id = cust[3]
        lat, lon = float(cust[7]), float(cust[8])
        ctype = cust[4]
        if ctype == "residential":
            ct = random.choice(charger_types[:4])
        else:
            ct = random.choice(charger_types[1:])
        year = random.randint(2019, 2024)
        month = random.randint(1, 12)
        install_date = f"{year}-{month:02d}-01"
        network = random.choice(networks)
        status = "active" if random.random() > 0.03 else "offline"
        rows.append([
            f"EV-{ev_num:06d}", cust_id, xfmr_id, fdr_id, sub_id,
            lat, lon, ct[0], ct[1], ct[2],
            install_date, network, status,
        ])
    write_csv("ev_chargers.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 9. EV charging profiles (hourly)
# ---------------------------------------------------------------------------

def generate_ev_profiles():
    print("Generating EV charging profiles...")
    headers = [
        "hour_of_day", "day_type",
        "residential_load_pct", "commercial_load_pct", "dcfc_load_pct",
    ]
    rows = []
    for day_type in ["weekday", "weekend"]:
        for hour in range(24):
            if day_type == "weekday":
                if 17 <= hour <= 22:
                    res = round(
                        60 + 30 * math.sin(math.pi * (hour - 17) / 5)
                        + random.uniform(-5, 5), 1,
                    )
                elif 0 <= hour < 6:
                    res = round(15 + random.uniform(-3, 3), 1)
                else:
                    res = round(10 + random.uniform(-3, 3), 1)
            else:
                if 10 <= hour <= 20:
                    res = round(
                        30 + 20 * math.sin(math.pi * (hour - 10) / 10)
                        + random.uniform(-5, 5), 1,
                    )
                else:
                    res = round(12 + random.uniform(-3, 3), 1)
            if 8 <= hour <= 17:
                com = round(
                    40 + 30 * math.sin(math.pi * (hour - 8) / 9)
                    + random.uniform(-5, 5), 1,
                )
            else:
                com = round(10 + random.uniform(-3, 3), 1)
            if 7 <= hour <= 10:
                dcfc = round(
                    30 + 20 * math.sin(math.pi * (hour - 7) / 3)
                    + random.uniform(-5, 5), 1,
                )
            elif 15 <= hour <= 19:
                dcfc = round(
                    40 + 30 * math.sin(math.pi * (hour - 15) / 4)
                    + random.uniform(-5, 5), 1,
                )
            else:
                dcfc = round(8 + random.uniform(-3, 3), 1)
            rows.append([hour, day_type, max(0, res), max(0, com), max(0, dcfc)])
    write_csv("ev_charging_profiles.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 10. Weather data
# ---------------------------------------------------------------------------

def generate_weather_data():
    print("Generating weather data...")
    headers = [
        "timestamp", "temperature_f", "humidity_pct", "wind_speed_mph",
        "ghi_w_per_m2", "cloud_cover_pct", "is_heatwave",
    ]
    rows = []
    start = datetime(2024, 1, 1)
    base_temps = {
        1: 55, 2: 58, 3: 65, 4: 75, 5: 85, 6: 100,
        7: 105, 8: 103, 9: 97, 10: 82, 11: 66, 12: 55,
    }
    for day_offset in range(365):
        dt = start + timedelta(days=day_offset)
        month = dt.month
        base_t = base_temps[month]
        is_heatwave = 0
        if month in (6, 7, 8) and day_offset % 30 < 5 and random.random() < 0.6:
            is_heatwave = 1
            base_t += random.uniform(5, 15)
        for hour in range(24):
            ts = dt + timedelta(hours=hour)
            diurnal = (
                15 * math.sin(math.pi * (hour - 5) / 14) if 5 <= hour <= 19 else -8
            )
            temp_f = round(base_t + diurnal + random.uniform(-3, 3), 1)
            humidity = round(
                max(5, min(95, 30 - 0.3 * (temp_f - 70) + random.uniform(-10, 10))), 1,
            )
            wind = round(max(0, 5 + random.uniform(-4, 8)), 1)
            if 6 <= hour <= 18:
                solar_angle = math.pi * (hour - 6) / 12
                ghi = round(
                    max(0, 1000 * math.sin(solar_angle) * random.uniform(0.6, 1.0)), 1,
                )
            else:
                ghi = 0.0
            cloud = round(max(0, min(100, 20 + random.uniform(-15, 30))), 1)
            rows.append([
                ts.strftime("%Y-%m-%d %H:%M"),
                temp_f, humidity, wind, ghi, cloud, is_heatwave,
            ])
    write_csv("weather_data.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 11. Growth scenarios
# ---------------------------------------------------------------------------

def generate_growth_scenarios():
    print("Generating growth scenarios...")
    headers = [
        "scenario_id", "scenario_name", "year",
        "ev_adoption_pct", "solar_adoption_pct", "battery_adoption_pct",
        "load_growth_pct", "peak_demand_growth_pct",
        "energy_efficiency_savings_pct", "electrification_load_pct",
        "description",
    ]
    scenarios = [
        ("SCN-001", "Reference Case",
         "Moderate growth, current policy trajectory"),
        ("SCN-002", "High EV Adoption",
         "Aggressive EV adoption driven by policy incentives"),
        ("SCN-003", "High Solar Growth",
         "Rapid DER expansion with net metering 2.0"),
        ("SCN-004", "Extreme Heat",
         "Climate-driven load growth from increased cooling demand"),
        ("SCN-005", "Full Electrification",
         "Building and transportation electrification mandate"),
    ]
    params = {
        "SCN-001": dict(ev_r=2.5, sol_r=1.8, bat_r=0.8,
                        lg=1.0, lg_r=0.15, pg=1.2, pg_r=0.2,
                        ee_r=0.1, el=2, el_r=0.5),
        "SCN-002": dict(ev_r=5.0, sol_r=2.0, bat_r=1.2,
                        lg=1.5, lg_r=0.3, pg=2.0, pg_r=0.4,
                        ee_r=0.1, el=3, el_r=0.8),
        "SCN-003": dict(ev_r=2.0, sol_r=4.5, bat_r=2.5,
                        lg=0.5, lg_r=0.05, pg=0.8, pg_r=0.1,
                        ee_r=0.2, el=2, el_r=0.3),
        "SCN-004": dict(ev_r=2.5, sol_r=2.0, bat_r=1.0,
                        lg=2.0, lg_r=0.4, pg=3.0, pg_r=0.6,
                        ee_r=0.1, el=2, el_r=0.4),
        "SCN-005": dict(ev_r=4.0, sol_r=3.0, bat_r=2.0,
                        lg=2.5, lg_r=0.5, pg=3.0, pg_r=0.55,
                        ee_r=0.15, el=5, el_r=2.0),
    }
    rows = []
    for scn_id, scn_name, desc in scenarios:
        p = params[scn_id]
        for year in range(2024, 2041):
            yr = year - 2024
            rows.append([
                scn_id, scn_name, year,
                min(round(8 + yr * p["ev_r"], 1), 95),
                min(round(12 + yr * p["sol_r"], 1), 90),
                min(round(3 + yr * p["bat_r"], 1), 80),
                round(p["lg"] + yr * p["lg_r"], 2),
                round(p["pg"] + yr * p["pg_r"], 2),
                round(0.5 + yr * p["ee_r"], 2),
                min(round(p["el"] + yr * p["el_r"], 1), 95),
                desc,
            ])
    write_csv("growth_scenarios.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 12. Reliability / outage history
# ---------------------------------------------------------------------------

def generate_outage_history(feeders):
    print("Generating outage history...")
    headers = [
        "outage_id", "feeder_id", "substation_id",
        "start_time", "end_time", "duration_hours",
        "cause", "customers_affected", "equipment_involved",
        "weather_related",
    ]
    causes = [
        "tree contact", "equipment failure", "animal contact",
        "lightning", "vehicle accident", "overload",
        "underground cable fault", "scheduled maintenance",
        "storm damage", "dig-in",
    ]
    rows = []
    outage_num = 0
    start_date = datetime(2024, 1, 1)
    for fdr in feeders:
        fdr_id = fdr[0]
        sub_id = fdr[1]
        n_cust = fdr[12]
        n_outages = random.randint(2, 8)
        for _ in range(n_outages):
            outage_num += 1
            day_offset = random.randint(0, 364)
            hour = random.randint(0, 23)
            start_ts = start_date + timedelta(days=day_offset, hours=hour)
            duration = round(random.uniform(0.25, 12.0), 2)
            end_ts = start_ts + timedelta(hours=duration)
            cause = random.choice(causes)
            affected = random.randint(1, min(n_cust, 2000))
            equip = random.choice([
                "overhead line", "transformer", "switch",
                "fuse", "recloser", "cable",
            ])
            weather = 1 if cause in (
                "lightning", "storm damage", "tree contact",
            ) else 0
            rows.append([
                f"OUT-{outage_num:05d}", fdr_id, sub_id,
                start_ts.strftime("%Y-%m-%d %H:%M"),
                end_ts.strftime("%Y-%m-%d %H:%M"),
                duration, cause, affected, equip, weather,
            ])
    write_csv("outage_history.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 13. Network connectivity — GIS-style node/edge model
# ---------------------------------------------------------------------------

def generate_network_nodes_and_edges(substations, feeders, transformers):
    """Build a normalized node/edge database for the distribution network.

    Produces two tables following GIS conventions (ESRI geodatabase style):

    network_nodes.csv — Point feature class
        Every distinct network location: substations, feeder breakers,
        junction/tap points along trunk lines, transformers, and feeder
        endpoints.  Each node has a unique ID, a geometry (lat/lon),
        and attributes like voltage, equipment type, and the common
        feeder_id / substation_id keys.

    network_edges.csv — Polyline feature class
        Every conductor segment connecting two nodes.  References
        from_node_id and to_node_id (foreign keys into the nodes table).
        Carries line attributes: impedance, conductor type, length,
        rated capacity, and operating status.
    """
    print("Generating network nodes...")

    # ------------------------------------------------------------------
    # Nodes
    # ------------------------------------------------------------------
    node_headers = [
        "node_id", "node_type", "substation_id", "feeder_id",
        "latitude", "longitude",
        "nominal_voltage_kv", "equipment_class",
        "rated_capacity", "rated_capacity_units",
        "phase", "installation_year", "status",
    ]

    nodes = []  # list of row-lists
    node_set = set()  # track IDs to avoid duplicates

    def add_node(row):
        nid = row[0]
        if nid not in node_set:
            node_set.add(nid)
            nodes.append(row)

    # --- Substation bus nodes ---
    for sub in substations:
        sub_id = sub[0]
        add_node([
            sub_id, "substation_bus", sub_id, "",
            float(sub[2]), float(sub[3]),
            sub[4],  # voltage_high_kv
            "substation",
            sub[6], "MVA",  # rated_capacity_mva
            "ABC", "",
            sub[10],  # status
        ])

    # --- Feeder head (breaker) and tail (open point) nodes ---
    for fdr in feeders:
        fdr_id = fdr[0]
        sub_id = fdr[1]
        v_kv = fdr[3]
        head_lat, head_lon = float(fdr[4]), float(fdr[5])
        tail_lat, tail_lon = float(fdr[6]), float(fdr[7])

        add_node([
            f"{fdr_id}-HEAD", "feeder_breaker", sub_id, fdr_id,
            head_lat, head_lon,
            v_kv, "breaker",
            fdr[10], "MW",  # rated_capacity_mw
            "ABC", "", "closed",
        ])
        add_node([
            f"{fdr_id}-TAIL", "feeder_endpoint", sub_id, fdr_id,
            tail_lat, tail_lon,
            v_kv, "open_point",
            "", "", "ABC", "", "open",
        ])

    # --- Transformer nodes (from the existing transformers table) ---
    for xfmr in transformers:
        add_node([
            xfmr[0],  # transformer_id
            "transformer", xfmr[2], xfmr[1],  # sub_id, fdr_id
            float(xfmr[3]), float(xfmr[4]),
            xfmr[7],  # primary_voltage_kv
            "distribution_transformer",
            xfmr[5], "kVA",  # rated_kva
            xfmr[6],  # phase
            "", xfmr[11],  # status
        ])

    # --- Junction / tap nodes along feeder trunks ---
    # Built during edge generation below; we collect them first, then
    # write the nodes file after both passes.

    # ------------------------------------------------------------------
    # Edges
    # ------------------------------------------------------------------
    edge_headers = [
        "edge_id", "from_node_id", "to_node_id",
        "feeder_id", "substation_id",
        "edge_type", "conductor_type", "phase",
        "length_miles", "length_ft",
        "impedance_r_ohm_per_mile", "impedance_x_ohm_per_mile",
        "impedance_z0_ohm_per_mile",
        "rated_amps", "nominal_voltage_kv",
        "num_phases", "is_overhead",
        "installation_year", "status",
    ]

    edges = []
    edge_num = 0

    conductor_specs = {
        "336 ACSR":  (0.306, 0.444, 400),
        "477 ACSR":  (0.216, 0.420, 530),
        "795 ACSR":  (0.130, 0.390, 700),
        "1/0 AL":    (0.592, 0.477, 230),
        "4/0 AL":    (0.297, 0.434, 340),
        "397.5 AAC": (0.240, 0.430, 480),
    }
    lateral_conductors = ["1/0 AL", "4/0 AL", "#2 ACSR", "#4 CU"]
    lateral_specs = {
        "1/0 AL":   (0.592, 0.477, 230),
        "4/0 AL":   (0.297, 0.434, 340),
        "#2 ACSR":  (0.895, 0.502, 150),
        "#4 CU":    (1.503, 0.511, 100),
    }

    # Build feeder lookup
    fdr_xfmrs = {}
    for xfmr in transformers:
        fdr_xfmrs.setdefault(xfmr[1], []).append(xfmr)

    for fdr in feeders:
        fdr_id = fdr[0]
        sub_id = fdr[1]
        v_kv = fdr[3]
        head_lat, head_lon = float(fdr[4]), float(fdr[5])
        tail_lat, tail_lon = float(fdr[6]), float(fdr[7])
        length = float(fdr[8])
        trunk_conductor = fdr[9]
        trunk_r, trunk_x, trunk_amps = conductor_specs.get(
            trunk_conductor, (0.25, 0.43, 400),
        )

        # -- Substation bus -> feeder breaker --
        edge_num += 1
        edges.append([
            f"EDGE-{edge_num:06d}",
            sub_id, f"{fdr_id}-HEAD",
            fdr_id, sub_id,
            "bus_tie", trunk_conductor, "ABC",
            0.01, round(0.01 * 5280, 1),
            round(trunk_r * random.uniform(0.9, 1.1), 4),
            round(trunk_x * random.uniform(0.9, 1.1), 4),
            round((trunk_r + trunk_x) * 0.5 * random.uniform(0.9, 1.1), 4),
            trunk_amps, v_kv,
            3, 1,
            "", "closed",
        ])

        xfmrs = fdr_xfmrs.get(fdr_id, [])
        if not xfmrs:
            continue

        # Sort transformers by distance from head
        def dist_from_head(x, _hlat=head_lat, _hlon=head_lon):
            return (float(x[3]) - _hlat) ** 2 + (float(x[4]) - _hlon) ** 2
        xfmrs_sorted = sorted(xfmrs, key=dist_from_head)

        # Create junction/tap nodes along the trunk
        trunk_spacing = max(1, len(xfmrs_sorted) // 8)
        trunk_nodes = []  # (node_id, lat, lon, mile_marker)

        for idx, xfmr in enumerate(xfmrs_sorted):
            xfmr_lat, xfmr_lon = float(xfmr[3]), float(xfmr[4])
            frac = (idx + 1) / (len(xfmrs_sorted) + 1)
            mile_marker = round(frac * length, 2)

            if idx % trunk_spacing == 0:
                tap_id = f"JCT-{fdr_id}-{len(trunk_nodes) + 1:03d}"
                tap_lat, tap_lon = point_along_line(
                    head_lat, head_lon, tail_lat, tail_lon, frac,
                )
                trunk_nodes.append((tap_id, tap_lat, tap_lon, mile_marker))

                # Add junction node
                add_node([
                    tap_id, "junction", sub_id, fdr_id,
                    tap_lat, tap_lon,
                    v_kv, "pole_top" if random.random() > 0.2 else "padmount",
                    "", "",
                    "ABC", "", "active",
                ])

                # Trunk edge: previous node -> this junction
                if len(trunk_nodes) == 1:
                    prev_id = f"{fdr_id}-HEAD"
                    prev_mile = 0.0
                else:
                    prev = trunk_nodes[-2]
                    prev_id = prev[0]
                    prev_mile = prev[3]

                seg_len = round(max(mile_marker - prev_mile, 0.01), 3)
                seg_ft = round(seg_len * 5280, 1)
                is_oh = 1 if random.random() > 0.15 else 0
                edge_num += 1
                edges.append([
                    f"EDGE-{edge_num:06d}",
                    prev_id, tap_id,
                    fdr_id, sub_id,
                    "primary_overhead" if is_oh else "primary_underground",
                    trunk_conductor, "ABC",
                    seg_len, seg_ft,
                    round(trunk_r * random.uniform(0.9, 1.1), 4),
                    round(trunk_x * random.uniform(0.9, 1.1), 4),
                    round((trunk_r + trunk_x) * 0.5 * random.uniform(0.9, 1.1), 4),
                    trunk_amps, v_kv,
                    3, is_oh,
                    "", "closed",
                ])

            # Lateral edge: nearest junction -> transformer
            nearest = trunk_nodes[-1]
            lat_len = round(
                max(
                    math.sqrt(
                        (xfmr_lat - nearest[1]) ** 2
                        + (xfmr_lon - nearest[2]) ** 2
                    ) * 69,
                    0.001,
                ), 3,
            )
            lat_ft = round(lat_len * 5280, 1)
            lat_cond = random.choice(lateral_conductors)
            lat_r, lat_x, lat_amps = lateral_specs[lat_cond]
            xfmr_phase = xfmr[6]
            n_phases = len(xfmr_phase) if len(xfmr_phase) <= 3 else 3
            is_oh = 1 if random.random() > 0.25 else 0
            edge_num += 1
            edges.append([
                f"EDGE-{edge_num:06d}",
                nearest[0], xfmr[0],
                fdr_id, sub_id,
                "lateral_overhead" if is_oh else "lateral_underground",
                lat_cond, xfmr_phase,
                lat_len, lat_ft,
                round(lat_r * random.uniform(0.9, 1.1), 4),
                round(lat_x * random.uniform(0.9, 1.1), 4),
                round((lat_r + lat_x) * 0.5 * random.uniform(0.9, 1.1), 4),
                lat_amps, v_kv,
                n_phases, is_oh,
                "", "closed",
            ])

        # Final trunk segment: last junction -> feeder tail
        if trunk_nodes:
            last = trunk_nodes[-1]
            seg_len = round(max(length - last[3], 0.01), 3)
            seg_ft = round(seg_len * 5280, 1)
            is_oh = 1 if random.random() > 0.15 else 0
            edge_num += 1
            edges.append([
                f"EDGE-{edge_num:06d}",
                last[0], f"{fdr_id}-TAIL",
                fdr_id, sub_id,
                "primary_overhead" if is_oh else "primary_underground",
                trunk_conductor, "ABC",
                seg_len, seg_ft,
                round(trunk_r * random.uniform(0.9, 1.1), 4),
                round(trunk_x * random.uniform(0.9, 1.1), 4),
                round((trunk_r + trunk_x) * 0.5 * random.uniform(0.9, 1.1), 4),
                trunk_amps, v_kv,
                3, is_oh,
                "", "open",
            ])

    write_csv("network_nodes.csv", node_headers, nodes)
    print("Generating network edges...")
    write_csv("network_edges.csv", edge_headers, edges)
    return nodes, edges


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Dynamic Network Model — Demo Data Generator")
    print("=" * 60)
    print()
    substations = generate_substations()
    feeders = generate_feeders(substations)
    transformers = generate_transformers(feeders)
    customers = generate_customers(transformers)
    generate_load_profiles(feeders)
    generate_solar_installations(customers)
    generate_solar_profiles()
    generate_ev_chargers(customers)
    generate_ev_profiles()
    generate_weather_data()
    generate_growth_scenarios()
    generate_outage_history(feeders)
    generate_network_nodes_and_edges(substations, feeders, transformers)
    print()
    print("All demo datasets generated successfully.")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
