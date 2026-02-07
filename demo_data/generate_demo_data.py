#!/usr/bin/env python3
"""
Generate synthetic demo datasets for the Dynamic Network Model.

Creates realistic utility distribution system data modeled after a mid-size
electric utility serving ~50,000 customers across a mixed suburban/rural
service territory.

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


def random_coord(center_lat=33.45, center_lon=-112.07, radius_deg=0.25):
    """Return a random (lat, lon) near a center point (default: Phoenix, AZ area)."""
    lat = center_lat + random.uniform(-radius_deg, radius_deg)
    lon = center_lon + random.uniform(-radius_deg, radius_deg)
    return round(lat, 6), round(lon, 6)


# ---------------------------------------------------------------------------
# 1. Substations
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
    rows = []
    for i, name in enumerate(names, start=1):
        lat, lon = random_coord()
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
# 2. Feeders (distribution lines)
# ---------------------------------------------------------------------------

def generate_feeders(substations):
    print("Generating feeders...")
    headers = [
        "feeder_id", "substation_id", "name", "voltage_kv",
        "length_miles", "conductor_type", "rated_capacity_mw",
        "peak_load_mw", "num_customers", "status",
    ]
    conductors = ["336 ACSR", "477 ACSR", "795 ACSR", "1/0 AL", "4/0 AL", "397.5 AAC"]
    rows = []
    feeder_num = 0
    for sub in substations:
        sub_id = sub[0]
        v_low = sub[5]
        n_feeders = random.randint(2, 6)
        for j in range(1, n_feeders + 1):
            feeder_num += 1
            length = round(random.uniform(2.0, 18.0), 1)
            conductor = random.choice(conductors)
            capacity = round(random.uniform(8, 20), 1)
            peak = round(capacity * random.uniform(0.4, 0.88), 1)
            customers = random.randint(400, 4500)
            status = "active"
            rows.append([
                f"FDR-{feeder_num:04d}", sub_id,
                f"{sub[1]} Fdr {j}", v_low,
                length, conductor, capacity, peak, customers, status,
            ])
    write_csv("feeders.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 3. Transformers (distribution transformers)
# ---------------------------------------------------------------------------

def generate_transformers(feeders):
    print("Generating transformers...")
    headers = [
        "transformer_id", "feeder_id", "latitude", "longitude",
        "rated_kva", "phase", "primary_voltage_kv", "secondary_voltage_v",
        "age_years", "manufacturer", "status",
    ]
    kva_sizes = [10, 15, 25, 37.5, 50, 75, 100, 167, 250, 333, 500]
    phases = ["A", "B", "C", "AB", "BC", "AC", "ABC"]
    manufacturers = ["ABB", "Eaton", "GE", "Siemens", "Howard Industries", "Prolec"]
    rows = []
    xfmr_num = 0
    for fdr in feeders:
        fdr_id = fdr[0]
        primary_kv = fdr[3]
        num_customers = fdr[8]
        # Roughly 5-10 customers per transformer
        n_xfmrs = max(5, num_customers // random.randint(5, 10))
        for _ in range(n_xfmrs):
            xfmr_num += 1
            lat, lon = random_coord()
            kva = random.choice(kva_sizes)
            phase = random.choice(phases)
            sec_v = random.choice([120, 240, 208, 480])
            age = random.randint(1, 45)
            mfr = random.choice(manufacturers)
            status = "active" if random.random() > 0.02 else "failed"
            rows.append([
                f"XFMR-{xfmr_num:06d}", fdr_id, lat, lon,
                kva, phase, primary_kv, sec_v,
                age, mfr, status,
            ])
    write_csv("transformers.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 4. Customers
# ---------------------------------------------------------------------------

def generate_customers(transformers):
    print("Generating customers...")
    headers = [
        "customer_id", "transformer_id", "customer_type",
        "rate_class", "contracted_demand_kw", "latitude", "longitude",
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
        lat_base, lon_base = float(xfmr[2]), float(xfmr[3])
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
            lat = round(lat_base + random.uniform(-0.002, 0.002), 6)
            lon = round(lon_base + random.uniform(-0.002, 0.002), 6)
            has_solar = 1 if random.random() < 0.12 else 0
            has_ev = 1 if random.random() < 0.08 else 0
            has_battery = 1 if random.random() < 0.03 else 0
            rows.append([
                f"CUST-{cust_num:07d}", xfmr_id, ctype,
                rate, demand, lat, lon,
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
        "feeder_id", "timestamp", "load_mw", "load_mvar",
        "voltage_pu", "power_factor",
    ]
    # Generate one representative week per season (4 weeks x 168 hours = 672 hours per feeder)
    seasons = {
        "winter": datetime(2024, 1, 15),
        "spring": datetime(2024, 4, 15),
        "summer": datetime(2024, 7, 15),
        "fall": datetime(2024, 10, 15),
    }
    rows = []
    for fdr in feeders:
        fdr_id = fdr[0]
        peak_mw = float(fdr[7])
        for season, start_dt in seasons.items():
            # Seasonal multipliers
            if season == "summer":
                season_mult = 1.0
            elif season == "winter":
                season_mult = 0.70
            elif season == "spring":
                season_mult = 0.60
            else:
                season_mult = 0.65
            for hour_offset in range(168):  # one week
                ts = start_dt + timedelta(hours=hour_offset)
                hour = ts.hour
                dow = ts.weekday()  # 0=Mon
                # Diurnal load shape
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
                # Weekend reduction
                if dow >= 5:
                    diurnal *= 0.85
                load_mw = round(
                    peak_mw * season_mult * diurnal * random.uniform(0.92, 1.08), 3
                )
                pf = round(random.uniform(0.88, 0.98), 3)
                load_mvar = round(load_mw * math.tan(math.acos(pf)), 3)
                voltage_pu = round(random.uniform(0.95, 1.05), 4)
                rows.append([
                    fdr_id, ts.strftime("%Y-%m-%d %H:%M"),
                    load_mw, load_mvar, voltage_pu, pf,
                ])
    write_csv("load_profiles.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 6. Solar installations
# ---------------------------------------------------------------------------

def generate_solar_installations(customers):
    print("Generating solar installations...")
    headers = [
        "solar_id", "customer_id", "feeder_id", "latitude", "longitude",
        "capacity_kw", "panel_type", "azimuth_deg", "tilt_deg",
        "install_date", "inverter_type", "status",
    ]
    panel_types = ["monocrystalline", "polycrystalline", "thin-film"]
    inverter_types = ["string", "micro", "hybrid"]
    rows = []
    sol_num = 0
    # Get customers with solar
    solar_custs = [c for c in customers if c[7] == 1]
    for cust in solar_custs:
        sol_num += 1
        cust_id = cust[0]
        xfmr_id = cust[1]
        # Derive feeder_id from transformer — we'll use a placeholder lookup
        lat, lon = float(cust[5]), float(cust[6])
        ctype = cust[2]
        if ctype == "residential":
            capacity = round(random.uniform(3, 12), 1)
        elif ctype == "commercial":
            capacity = round(random.uniform(25, 500), 1)
        else:
            capacity = round(random.uniform(5, 100), 1)
        panel = random.choice(panel_types)
        azimuth = random.randint(150, 210)  # south-facing
        tilt = random.randint(15, 35)
        year = random.randint(2016, 2024)
        month = random.randint(1, 12)
        install_date = f"{year}-{month:02d}-01"
        inverter = random.choice(inverter_types)
        status = "active" if random.random() > 0.02 else "inactive"
        rows.append([
            f"SOL-{sol_num:06d}", cust_id, xfmr_id, lat, lon,
            capacity, panel, azimuth, tilt,
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
    # One representative day per month
    for month in range(1, 13):
        dt = datetime(2024, month, 15)
        sunrise = 5 + 2 * math.cos(math.pi * (month - 6) / 6)  # ~5-7
        sunset = 19 - 2 * math.cos(math.pi * (month - 6) / 6)  # ~17-19
        day_length = sunset - sunrise
        for hour in range(24):
            ts = dt + timedelta(hours=hour)
            if sunrise <= hour <= sunset and day_length > 0:
                solar_angle = math.pi * (hour - sunrise) / day_length
                clear_sky = round(max(0, math.sin(solar_angle)), 3)
            else:
                clear_sky = 0.0
            # Cloud variability
            cloud_factor = random.uniform(0.7, 1.0) if clear_sky > 0 else 1.0
            gen_pct = round(clear_sky * cloud_factor * 100, 1)
            # Temperature varies by month and hour
            base_temp = 10 + 20 * math.sin(math.pi * (month - 1) / 11)
            diurnal_temp = 8 * math.sin(math.pi * (hour - 6) / 12) if 6 <= hour <= 18 else -3
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
# 8. EV chargers
# ---------------------------------------------------------------------------

def generate_ev_chargers(customers):
    print("Generating EV chargers...")
    headers = [
        "charger_id", "customer_id", "latitude", "longitude",
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
    networks = ["ChargePoint", "Tesla", "EVgo", "Blink", "Electrify America", "private"]
    rows = []
    ev_num = 0
    ev_custs = [c for c in customers if c[8] == 1]
    for cust in ev_custs:
        ev_num += 1
        cust_id = cust[0]
        lat, lon = float(cust[5]), float(cust[6])
        ctype = cust[2]
        if ctype == "residential":
            ct = random.choice(charger_types[:4])  # Level 1 or 2
        else:
            ct = random.choice(charger_types[1:])  # Level 2 or DCFC
        year = random.randint(2019, 2024)
        month = random.randint(1, 12)
        install_date = f"{year}-{month:02d}-01"
        network = random.choice(networks)
        status = "active" if random.random() > 0.03 else "offline"
        rows.append([
            f"EV-{ev_num:06d}", cust_id, lat, lon,
            ct[0], ct[1], ct[2], install_date, network, status,
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
            # Residential: evening peak
            if day_type == "weekday":
                if 17 <= hour <= 22:
                    res = round(60 + 30 * math.sin(math.pi * (hour - 17) / 5) + random.uniform(-5, 5), 1)
                elif 0 <= hour < 6:
                    res = round(15 + random.uniform(-3, 3), 1)
                else:
                    res = round(10 + random.uniform(-3, 3), 1)
            else:
                if 10 <= hour <= 20:
                    res = round(30 + 20 * math.sin(math.pi * (hour - 10) / 10) + random.uniform(-5, 5), 1)
                else:
                    res = round(12 + random.uniform(-3, 3), 1)
            # Commercial: daytime peak
            if 8 <= hour <= 17:
                com = round(40 + 30 * math.sin(math.pi * (hour - 8) / 9) + random.uniform(-5, 5), 1)
            else:
                com = round(10 + random.uniform(-3, 3), 1)
            # DCFC: two peaks — morning and afternoon
            if 7 <= hour <= 10:
                dcfc = round(30 + 20 * math.sin(math.pi * (hour - 7) / 3) + random.uniform(-5, 5), 1)
            elif 15 <= hour <= 19:
                dcfc = round(40 + 30 * math.sin(math.pi * (hour - 15) / 4) + random.uniform(-5, 5), 1)
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
    for day_offset in range(365):
        dt = start + timedelta(days=day_offset)
        month = dt.month
        # Base temperature by month (Phoenix-like climate)
        base_temps = {
            1: 55, 2: 58, 3: 65, 4: 75, 5: 85, 6: 100,
            7: 105, 8: 103, 9: 97, 10: 82, 11: 66, 12: 55,
        }
        base_t = base_temps[month]
        # Add heatwave events (10 days in summer)
        is_heatwave = 0
        if month in (6, 7, 8) and day_offset % 30 < 5 and random.random() < 0.6:
            is_heatwave = 1
            base_t += random.uniform(5, 15)
        for hour in range(24):
            ts = dt + timedelta(hours=hour)
            diurnal = 15 * math.sin(math.pi * (hour - 5) / 14) if 5 <= hour <= 19 else -8
            temp_f = round(base_t + diurnal + random.uniform(-3, 3), 1)
            humidity = round(max(5, min(95, 30 - 0.3 * (temp_f - 70) + random.uniform(-10, 10))), 1)
            wind = round(max(0, 5 + random.uniform(-4, 8)), 1)
            # Solar irradiance
            if 6 <= hour <= 18:
                solar_angle = math.pi * (hour - 6) / 12
                ghi = round(max(0, 1000 * math.sin(solar_angle) * random.uniform(0.6, 1.0)), 1)
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
        ("SCN-001", "Reference Case", "Moderate growth, current policy trajectory"),
        ("SCN-002", "High EV Adoption", "Aggressive EV adoption driven by policy incentives"),
        ("SCN-003", "High Solar Growth", "Rapid DER expansion with net metering 2.0"),
        ("SCN-004", "Extreme Heat", "Climate-driven load growth from increased cooling demand"),
        ("SCN-005", "Full Electrification", "Building and transportation electrification mandate"),
    ]
    rows = []
    for scn_id, scn_name, desc in scenarios:
        for year in range(2024, 2041):
            yr_offset = year - 2024
            if scn_id == "SCN-001":
                ev = round(8 + yr_offset * 2.5, 1)
                solar = round(12 + yr_offset * 1.8, 1)
                battery = round(3 + yr_offset * 0.8, 1)
                load_g = round(1.0 + yr_offset * 0.15, 2)
                peak_g = round(1.2 + yr_offset * 0.2, 2)
                ee = round(0.5 + yr_offset * 0.1, 2)
                elec = round(2 + yr_offset * 0.5, 1)
            elif scn_id == "SCN-002":
                ev = round(8 + yr_offset * 5.0, 1)
                solar = round(12 + yr_offset * 2.0, 1)
                battery = round(3 + yr_offset * 1.2, 1)
                load_g = round(1.5 + yr_offset * 0.3, 2)
                peak_g = round(2.0 + yr_offset * 0.4, 2)
                ee = round(0.5 + yr_offset * 0.1, 2)
                elec = round(3 + yr_offset * 0.8, 1)
            elif scn_id == "SCN-003":
                ev = round(8 + yr_offset * 2.0, 1)
                solar = round(12 + yr_offset * 4.5, 1)
                battery = round(3 + yr_offset * 2.5, 1)
                load_g = round(0.5 + yr_offset * 0.05, 2)
                peak_g = round(0.8 + yr_offset * 0.1, 2)
                ee = round(1.0 + yr_offset * 0.2, 2)
                elec = round(2 + yr_offset * 0.3, 1)
            elif scn_id == "SCN-004":
                ev = round(8 + yr_offset * 2.5, 1)
                solar = round(12 + yr_offset * 2.0, 1)
                battery = round(3 + yr_offset * 1.0, 1)
                load_g = round(2.0 + yr_offset * 0.4, 2)
                peak_g = round(3.0 + yr_offset * 0.6, 2)
                ee = round(0.5 + yr_offset * 0.1, 2)
                elec = round(2 + yr_offset * 0.4, 1)
            else:  # Full Electrification
                ev = round(8 + yr_offset * 4.0, 1)
                solar = round(12 + yr_offset * 3.0, 1)
                battery = round(3 + yr_offset * 2.0, 1)
                load_g = round(2.5 + yr_offset * 0.5, 2)
                peak_g = round(3.0 + yr_offset * 0.55, 2)
                ee = round(1.0 + yr_offset * 0.15, 2)
                elec = round(5 + yr_offset * 2.0, 1)
            rows.append([
                scn_id, scn_name, year,
                min(ev, 95), min(solar, 90), min(battery, 80),
                load_g, peak_g, ee, min(elec, 95), desc,
            ])
    write_csv("growth_scenarios.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 12. Reliability / outage history
# ---------------------------------------------------------------------------

def generate_outage_history(feeders):
    print("Generating outage history...")
    headers = [
        "outage_id", "feeder_id", "start_time", "end_time",
        "duration_hours", "cause", "customers_affected",
        "equipment_involved", "weather_related",
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
        n_cust = fdr[8]
        # 2-8 outages per feeder per year
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
            equip = random.choice(["overhead line", "transformer", "switch", "fuse", "recloser", "cable"])
            weather = 1 if cause in ("lightning", "storm damage", "tree contact") else 0
            rows.append([
                f"OUT-{outage_num:05d}", fdr_id,
                start_ts.strftime("%Y-%m-%d %H:%M"),
                end_ts.strftime("%Y-%m-%d %H:%M"),
                duration, cause, affected, equip, weather,
            ])
    write_csv("outage_history.csv", headers, rows)
    return rows


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
    print()
    print("All demo datasets generated successfully.")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
