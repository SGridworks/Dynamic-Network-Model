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

Geographic coordinates are aligned to the Phoenix street grid so that
assets render correctly on a map.  Feeders follow real street routes
(N/S along avenues, E/W along roads).

Network topology includes ties between feeders, reclosers, sectionalizers,
and fuses — reflecting real switching configurations.

Customer interval data uses 15-minute AMI-style metering.

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
# Phoenix street grid model
# ---------------------------------------------------------------------------
# Reference point: Central Ave & Washington St
GRID_ORIGIN_LAT = 33.4484
GRID_ORIGIN_LON = -112.0740
MILE_LAT = 0.01449   # degrees latitude per mile
MILE_LON = 0.01737   # degrees longitude per mile (at 33.45°N)

# E-W arterial roads: (name, miles north of Washington)
EW_STREETS = [
    ("Baseline Rd", -6.0), ("Southern Ave", -4.5), ("Broadway Rd", -3.0),
    ("Buckeye Rd", -1.0), ("Van Buren St", 0.0), ("McDowell Rd", 2.0),
    ("Thomas Rd", 3.0), ("Indian School Rd", 4.5), ("Camelback Rd", 5.5),
    ("Bethany Home Rd", 6.5), ("Northern Ave", 7.5), ("Glendale Ave", 8.5),
    ("Dunlap Ave", 9.5), ("Peoria Ave", 10.5), ("Cactus Rd", 11.5),
    ("Thunderbird Rd", 12.5), ("Bell Rd", 13.5),
]
# N-S arterial streets/avenues: (name, miles east of Central; negative=west)
NS_STREETS = [
    ("59th Ave", -7), ("51st Ave", -6), ("43rd Ave", -5), ("35th Ave", -4),
    ("27th Ave", -3), ("19th Ave", -2), ("7th Ave", -1), ("Central Ave", 0),
    ("7th St", 1), ("16th St", 2), ("24th St", 3), ("32nd St", 4),
    ("40th St", 5), ("48th St", 6), ("56th St", 7),
]


def grid_coord(miles_north, miles_east):
    """Convert grid position to (lat, lon)."""
    lat = round(GRID_ORIGIN_LAT + miles_north * MILE_LAT, 6)
    lon = round(GRID_ORIGIN_LON + miles_east * MILE_LON, 6)
    return lat, lon


def street_jitter(lat, lon, feet=30):
    """Add small random offset (~pole placement) to a street coordinate."""
    deg = feet / 5280 * MILE_LAT
    return (
        round(lat + random.uniform(-deg, deg), 6),
        round(lon + random.uniform(-deg, deg), 6),
    )


def along_street(start_lat, start_lon, direction, distance_mi):
    """Move along a street in a cardinal direction."""
    if direction == "N":
        return round(start_lat + distance_mi * MILE_LAT, 6), start_lon
    elif direction == "S":
        return round(start_lat - distance_mi * MILE_LAT, 6), start_lon
    elif direction == "E":
        return start_lat, round(start_lon + distance_mi * MILE_LON, 6)
    else:  # W
        return start_lat, round(start_lon - distance_mi * MILE_LON, 6)


def perpendicular_offset(lat, lon, direction, feet=80):
    """Offset perpendicular to street for customer placement."""
    deg = feet / 5280
    side = random.choice([-1, 1])
    if direction in ("N", "S"):  # street runs N-S, offset E-W
        return lat, round(lon + side * deg * MILE_LON, 6)
    else:  # street runs E-W, offset N-S
        return round(lat + side * deg * MILE_LAT, 6), lon


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def write_csv(filename, headers, rows):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"  wrote {len(rows):>6,} rows -> {filename}")


def point_along_route(lat1, lon1, lat2, lon2, fraction):
    """Interpolate along a route with small jitter."""
    lat = lat1 + fraction * (lat2 - lat1)
    lon = lon1 + fraction * (lon2 - lon1)
    jitter = random.uniform(-0.00005, 0.00005)
    return round(lat + jitter, 6), round(lon + jitter, 6)


# ---------------------------------------------------------------------------
# Substation definitions (placed at real Phoenix intersections)
# ---------------------------------------------------------------------------

SUBSTATION_DEFS = [
    # (name, miles_north, miles_east, ew_street, ns_street)
    ("Riverside",        5.5, -4, "Camelback Rd", "35th Ave"),
    ("Mesa Grande",      4.5,  0, "Indian School Rd", "Central Ave"),
    ("Copper Hills",     5.5,  3, "Camelback Rd", "24th St"),
    ("Ironwood",         3.0, -1, "Thomas Rd", "7th Ave"),
    ("Desert View",      2.0,  4, "McDowell Rd", "32nd St"),
    ("Palo Verde",       7.5, -5, "Northern Ave", "43rd Ave"),
    ("Saguaro",          6.5,  2, "Bethany Home Rd", "16th St"),
    ("Sunridge",         4.5,  5, "Indian School Rd", "40th St"),
    ("Cottonwood",       2.0, -2, "McDowell Rd", "19th Ave"),
    ("Red Mountain",     3.0,  6, "Thomas Rd", "48th St"),
    ("Baseline",        -6.0,  0, "Baseline Rd", "Central Ave"),
    ("Tempe Junction",  -3.0,  1, "Broadway Rd", "7th St"),
    ("Gilbert Road",     2.0,  7, "McDowell Rd", "56th St"),
    ("Chandler Heights", -6.0,  3, "Baseline Rd", "24th St"),
    ("Ocotillo",         9.5, -4, "Dunlap Ave", "35th Ave"),
]


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
    rows = []
    for i, (name, mi_n, mi_e, _, _) in enumerate(SUBSTATION_DEFS, start=1):
        lat, lon = grid_coord(mi_n, mi_e)
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
# 2. Feeders — follow streets from substations
# ---------------------------------------------------------------------------

DIRECTIONS = ["N", "S", "E", "W"]


def generate_feeders(substations):
    print("Generating feeders...")
    headers = [
        "feeder_id", "substation_id", "name", "voltage_kv",
        "latitude_head", "longitude_head",
        "latitude_tail", "longitude_tail",
        "direction", "length_miles", "conductor_type",
        "rated_capacity_mw", "peak_load_mw", "num_customers", "status",
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
        n_feeders = random.randint(3, 6)
        # Assign directions: ensure we cover at least 2 different directions
        dirs = list(DIRECTIONS)
        random.shuffle(dirs)
        for j in range(n_feeders):
            feeder_num += 1
            d = dirs[j % 4]
            length = round(random.uniform(2.0, 8.0), 1)
            tail_lat, tail_lon = along_street(sub_lat, sub_lon, d, length)
            conductor = random.choice(conductors)
            capacity = round(random.uniform(8, 20), 1)
            peak = round(capacity * random.uniform(0.4, 0.88), 1)
            customers = random.randint(400, 4500)
            rows.append([
                f"FDR-{feeder_num:04d}", sub_id,
                f"{sub[1]} Fdr {j + 1}", v_low,
                sub_lat, sub_lon, tail_lat, tail_lon,
                d, length, conductor, capacity, peak, customers, "active",
            ])
    write_csv("feeders.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 3. Transformers — placed at intervals along feeder streets
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
        direction = fdr[8]
        num_customers = fdr[13]
        n_xfmrs = max(5, num_customers // random.randint(5, 10))
        for k in range(n_xfmrs):
            xfmr_num += 1
            frac = (k + 1) / (n_xfmrs + 1)
            lat, lon = point_along_route(
                head_lat, head_lon, tail_lat, tail_lon, frac,
            )
            # Small perpendicular offset from street centerline (~30 ft)
            lat, lon = perpendicular_offset(lat, lon, direction, feet=30)
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
# 4. Customers — offset perpendicular to the street
# ---------------------------------------------------------------------------

def generate_customers(transformers, feeders):
    print("Generating customers...")
    headers = [
        "customer_id", "transformer_id", "feeder_id", "substation_id",
        "customer_type", "rate_class", "contracted_demand_kw",
        "latitude", "longitude",
        "has_solar", "has_ev", "has_battery",
    ]
    types_weights = [
        ("residential", 0.82), ("commercial", 0.13),
        ("industrial", 0.03), ("municipal", 0.02),
    ]
    rate_classes = {
        "residential": ["R-1", "R-TOU", "R-EV"],
        "commercial": ["C-1", "C-TOU", "C-DEMAND"],
        "industrial": ["I-1", "I-DEMAND"],
        "municipal": ["M-1"],
    }
    # Build direction lookup by feeder
    fdr_dir = {f[0]: f[8] for f in feeders}
    rows = []
    cust_num = 0
    for xfmr in transformers:
        xfmr_id = xfmr[0]
        fdr_id = xfmr[1]
        sub_id = xfmr[2]
        xfmr_lat, xfmr_lon = float(xfmr[3]), float(xfmr[4])
        direction = fdr_dir.get(fdr_id, "N")
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
            # Customer lot: offset from transformer along and perpendicular to street
            along_ft = random.uniform(-150, 150)
            along_deg = along_ft / 5280
            if direction in ("N", "S"):
                c_lat = xfmr_lat + along_deg * MILE_LAT
                c_lon = xfmr_lon
            else:
                c_lat = xfmr_lat
                c_lon = xfmr_lon + along_deg * MILE_LON
            c_lat, c_lon = perpendicular_offset(c_lat, c_lon, direction, feet=random.uniform(40, 120))
            c_lat, c_lon = round(c_lat, 6), round(c_lon, 6)
            has_solar = 1 if random.random() < 0.12 else 0
            has_ev = 1 if random.random() < 0.08 else 0
            has_battery = 1 if random.random() < 0.03 else 0
            rows.append([
                f"CUST-{cust_num:07d}", xfmr_id, fdr_id, sub_id,
                ctype, rate, demand, c_lat, c_lon,
                has_solar, has_ev, has_battery,
            ])
    write_csv("customers.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 5. Load profiles (15-min intervals, one representative week per season)
# ---------------------------------------------------------------------------

def _diurnal(hour_frac, dow):
    """Return diurnal load factor for a fractional hour."""
    if 0 <= hour_frac < 6:
        d = 0.45 + 0.05 * math.sin(math.pi * hour_frac / 6)
    elif 6 <= hour_frac < 9:
        d = 0.50 + 0.25 * ((hour_frac - 6) / 3)
    elif 9 <= hour_frac < 15:
        d = 0.75 + 0.10 * math.sin(math.pi * (hour_frac - 9) / 6)
    elif 15 <= hour_frac < 20:
        d = 0.80 + 0.20 * math.sin(math.pi * (hour_frac - 15) / 5)
    else:
        d = 0.70 - 0.15 * ((hour_frac - 20) / 4)
    if dow >= 5:
        d *= 0.85
    return d


def generate_load_profiles(feeders):
    print("Generating load profiles (15-min intervals)...")
    headers = [
        "feeder_id", "substation_id", "timestamp",
        "load_mw", "load_mvar", "voltage_pu", "power_factor",
    ]
    seasons = {
        "winter": (datetime(2024, 1, 15), 0.70),
        "spring": (datetime(2024, 4, 15), 0.60),
        "summer": (datetime(2024, 7, 15), 1.00),
        "fall":   (datetime(2024, 10, 15), 0.65),
    }
    rows = []
    for fdr in feeders:
        fdr_id = fdr[0]
        sub_id = fdr[1]
        peak_mw = float(fdr[12])
        for _, (start_dt, season_mult) in seasons.items():
            # 168 hours * 4 = 672 intervals per week
            for interval in range(168 * 4):
                ts = start_dt + timedelta(minutes=15 * interval)
                hour_frac = ts.hour + ts.minute / 60.0
                dow = ts.weekday()
                d = _diurnal(hour_frac, dow)
                load_mw = round(
                    peak_mw * season_mult * d * random.uniform(0.93, 1.07), 3,
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
# 6. Customer interval data (15-min AMI metering, sample of customers)
# ---------------------------------------------------------------------------

def generate_customer_interval_data(customers):
    """Generate 15-min AMI interval data for a sample of ~500 customers
    covering one representative summer week (the peak season).
    """
    print("Generating customer interval data (15-min AMI)...")
    headers = [
        "customer_id", "transformer_id", "feeder_id", "substation_id",
        "customer_type", "timestamp",
        "demand_kw", "energy_kwh", "voltage_v", "power_factor",
    ]
    # Sample ~500 customers stratified by type
    by_type = {}
    for c in customers:
        by_type.setdefault(c[4], []).append(c)
    sample = []
    for ctype, pool in by_type.items():
        if ctype == "residential":
            n = min(400, len(pool))
        elif ctype == "commercial":
            n = min(70, len(pool))
        elif ctype == "industrial":
            n = min(20, len(pool))
        else:
            n = min(10, len(pool))
        sample.extend(random.sample(pool, n))

    start_dt = datetime(2024, 7, 15)  # Summer week
    rows = []
    for cust in sample:
        cust_id = cust[0]
        xfmr_id = cust[1]
        fdr_id = cust[2]
        sub_id = cust[3]
        ctype = cust[4]
        contracted_kw = float(cust[6])
        for interval in range(7 * 96):  # 7 days x 96 intervals
            ts = start_dt + timedelta(minutes=15 * interval)
            hour_frac = ts.hour + ts.minute / 60.0
            dow = ts.weekday()
            if ctype == "residential":
                # Morning bump, afternoon dip, evening peak + HVAC cycling
                if 0 <= hour_frac < 6:
                    base = 0.25
                elif 6 <= hour_frac < 9:
                    base = 0.35 + 0.15 * ((hour_frac - 6) / 3)
                elif 9 <= hour_frac < 15:
                    base = 0.30  # away from home
                elif 15 <= hour_frac < 21:
                    base = 0.50 + 0.40 * math.sin(math.pi * (hour_frac - 15) / 6)
                else:
                    base = 0.40 - 0.10 * ((hour_frac - 21) / 3)
                # HVAC cycling: adds spiky 15-min variation in summer
                hvac = 0.15 * abs(math.sin(math.pi * interval / 3))
                noise = random.uniform(-0.10, 0.10)
                demand = contracted_kw * max(0.05, base + hvac + noise)
            elif ctype == "commercial":
                if 7 <= hour_frac < 20 and dow < 5:
                    base = 0.55 + 0.30 * math.sin(math.pi * (hour_frac - 7) / 13)
                elif 8 <= hour_frac < 17 and dow >= 5:
                    base = 0.30
                else:
                    base = 0.15
                noise = random.uniform(-0.08, 0.08)
                demand = contracted_kw * max(0.05, base + noise)
            elif ctype == "industrial":
                # Three shifts with transition dips
                shift_hour = hour_frac % 8
                base = 0.70 + 0.10 * math.sin(math.pi * shift_hour / 8)
                if 5.5 < shift_hour < 6.5:
                    base -= 0.15  # shift change
                noise = random.uniform(-0.05, 0.05)
                demand = contracted_kw * max(0.10, base + noise)
            else:  # municipal
                if 7 <= hour_frac < 18 and dow < 5:
                    base = 0.60
                else:
                    base = 0.20
                noise = random.uniform(-0.08, 0.08)
                demand = contracted_kw * max(0.05, base + noise)

            demand = round(demand, 2)
            energy = round(demand * 0.25, 3)  # kWh for 15-min interval
            voltage = round(random.uniform(228, 244), 1) if ctype != "industrial" else round(random.uniform(470, 490), 1)
            pf = round(random.uniform(0.85, 0.99), 3)
            rows.append([
                cust_id, xfmr_id, fdr_id, sub_id, ctype,
                ts.strftime("%Y-%m-%d %H:%M"),
                demand, energy, voltage, pf,
            ])
    write_csv("customer_interval_data.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 7. Solar installations — co-located with their customer
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
        cust_id, xfmr_id, fdr_id, sub_id = cust[0], cust[1], cust[2], cust[3]
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
        inverter = random.choice(inverter_types)
        status = "active" if random.random() > 0.02 else "inactive"
        rows.append([
            f"SOL-{sol_num:06d}", cust_id, xfmr_id, fdr_id, sub_id,
            lat, lon, capacity, panel, azimuth, tilt,
            f"{year}-{month:02d}-01", inverter, status,
        ])
    write_csv("solar_installations.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 8. Solar generation profiles
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
            diurnal_temp = 8 * math.sin(math.pi * (hour - 6) / 12) if 6 <= hour <= 18 else -3
            temp = round(base_temp + diurnal_temp + random.uniform(-2, 2), 1)
            ghi = round(clear_sky * cloud_factor * 1000, 1)
            rows.append([
                ts.strftime("%Y-%m-%d %H:%M"),
                round(clear_sky * cloud_factor, 3), gen_pct, temp, ghi,
            ])
    write_csv("solar_profiles.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 9. EV chargers — co-located with their customer
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
        ("Level 1", 1.4, "NEMA 5-15"), ("Level 2", 7.7, "J1772"),
        ("Level 2", 11.5, "J1772"), ("Level 2", 19.2, "J1772"),
        ("DCFC", 50, "CCS"), ("DCFC", 150, "CCS"), ("DCFC", 350, "CCS"),
    ]
    networks = ["ChargePoint", "Tesla", "EVgo", "Blink", "Electrify America", "private"]
    rows = []
    ev_num = 0
    ev_custs = [c for c in customers if c[10] == 1]
    for cust in ev_custs:
        ev_num += 1
        cust_id, xfmr_id, fdr_id, sub_id = cust[0], cust[1], cust[2], cust[3]
        lat, lon = float(cust[7]), float(cust[8])
        ctype = cust[4]
        ct = random.choice(charger_types[:4]) if ctype == "residential" else random.choice(charger_types[1:])
        year = random.randint(2019, 2024)
        month = random.randint(1, 12)
        network = random.choice(networks)
        status = "active" if random.random() > 0.03 else "offline"
        rows.append([
            f"EV-{ev_num:06d}", cust_id, xfmr_id, fdr_id, sub_id,
            lat, lon, ct[0], ct[1], ct[2],
            f"{year}-{month:02d}-01", network, status,
        ])
    write_csv("ev_chargers.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 10. EV charging profiles
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
                res = round((60 + 30 * math.sin(math.pi * (hour - 17) / 5) + random.uniform(-5, 5)) if 17 <= hour <= 22 else (15 + random.uniform(-3, 3)) if hour < 6 else (10 + random.uniform(-3, 3)), 1)
            else:
                res = round((30 + 20 * math.sin(math.pi * (hour - 10) / 10) + random.uniform(-5, 5)) if 10 <= hour <= 20 else (12 + random.uniform(-3, 3)), 1)
            com = round((40 + 30 * math.sin(math.pi * (hour - 8) / 9) + random.uniform(-5, 5)) if 8 <= hour <= 17 else (10 + random.uniform(-3, 3)), 1)
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
# 11. Weather data
# ---------------------------------------------------------------------------

def generate_weather_data():
    print("Generating weather data...")
    headers = [
        "timestamp", "temperature_f", "humidity_pct", "wind_speed_mph",
        "ghi_w_per_m2", "cloud_cover_pct", "is_heatwave", "is_storm",
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
        is_storm = 0
        # Heatwave events: multi-day stretches in summer
        if month in (6, 7, 8) and day_offset % 30 < 5 and random.random() < 0.6:
            is_heatwave = 1
            base_t += random.uniform(5, 15)
        # Storm events: monsoon season (Jul-Sep) and winter storms
        if month in (7, 8, 9) and random.random() < 0.12:
            is_storm = 1
        elif month in (12, 1, 2) and random.random() < 0.06:
            is_storm = 1
        for hour in range(24):
            ts = dt + timedelta(hours=hour)
            diurnal = 15 * math.sin(math.pi * (hour - 5) / 14) if 5 <= hour <= 19 else -8
            temp_f = round(base_t + diurnal + random.uniform(-3, 3), 1)
            humidity = round(max(5, min(95, 30 - 0.3 * (temp_f - 70) + random.uniform(-10, 10))), 1)
            wind = round(max(0, 5 + random.uniform(-4, 8)), 1)
            if is_storm:
                wind = round(max(wind, 15 + random.uniform(0, 25)), 1)
                humidity = round(min(95, humidity + 30), 1)
            if 6 <= hour <= 18:
                solar_angle = math.pi * (hour - 6) / 12
                cloud_mult = random.uniform(0.1, 0.4) if is_storm else random.uniform(0.6, 1.0)
                ghi = round(max(0, 1000 * math.sin(solar_angle) * cloud_mult), 1)
            else:
                ghi = 0.0
            cloud = round(min(100, max(0, 20 + random.uniform(-15, 30))), 1)
            if is_storm:
                cloud = round(min(100, cloud + 40), 1)
            rows.append([
                ts.strftime("%Y-%m-%d %H:%M"),
                temp_f, humidity, wind, ghi, cloud, is_heatwave, is_storm,
            ])
    write_csv("weather_data.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 12. Growth scenarios
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
    params = {
        "SCN-001": dict(ev_r=2.5, sol_r=1.8, bat_r=0.8, lg=1.0, lg_r=0.15, pg=1.2, pg_r=0.2, ee_r=0.1, el=2, el_r=0.5),
        "SCN-002": dict(ev_r=5.0, sol_r=2.0, bat_r=1.2, lg=1.5, lg_r=0.3, pg=2.0, pg_r=0.4, ee_r=0.1, el=3, el_r=0.8),
        "SCN-003": dict(ev_r=2.0, sol_r=4.5, bat_r=2.5, lg=0.5, lg_r=0.05, pg=0.8, pg_r=0.1, ee_r=0.2, el=2, el_r=0.3),
        "SCN-004": dict(ev_r=2.5, sol_r=2.0, bat_r=1.0, lg=2.0, lg_r=0.4, pg=3.0, pg_r=0.6, ee_r=0.1, el=2, el_r=0.4),
        "SCN-005": dict(ev_r=4.0, sol_r=3.0, bat_r=2.0, lg=2.5, lg_r=0.5, pg=3.0, pg_r=0.55, ee_r=0.15, el=5, el_r=2.0),
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
# 13. Outage history — clustered during storms and heat events
# ---------------------------------------------------------------------------

def generate_outage_history(feeders, weather_rows):
    print("Generating outage history...")
    headers = [
        "outage_id", "feeder_id", "substation_id",
        "start_time", "end_time", "duration_hours",
        "cause", "customers_affected", "equipment_involved",
        "weather_related",
    ]
    # Build day-level weather index: {day_offset: (is_heatwave, is_storm, max_temp)}
    day_wx = {}
    for wr in weather_rows:
        ts = datetime.strptime(wr[0], "%Y-%m-%d %H:%M")
        doy = (ts - datetime(2024, 1, 1)).days
        temp = float(wr[1])
        hw = int(wr[6])
        st = int(wr[7])
        if doy not in day_wx:
            day_wx[doy] = {"heatwave": hw, "storm": st, "max_temp": temp}
        else:
            day_wx[doy]["max_temp"] = max(day_wx[doy]["max_temp"], temp)
            day_wx[doy]["heatwave"] = max(day_wx[doy]["heatwave"], hw)
            day_wx[doy]["storm"] = max(day_wx[doy]["storm"], st)

    heat_days = [d for d, w in day_wx.items() if w["heatwave"] or w["max_temp"] > 110]
    storm_days = [d for d, w in day_wx.items() if w["storm"]]
    normal_days = [d for d in range(365) if d not in heat_days and d not in storm_days]

    heat_causes = ["equipment failure", "overload", "underground cable fault"]
    storm_causes = ["tree contact", "lightning", "storm damage", "animal contact"]
    normal_causes = ["equipment failure", "animal contact", "vehicle accident",
                     "dig-in", "underground cable fault", "scheduled maintenance"]

    rows = []
    outage_num = 0
    start_date = datetime(2024, 1, 1)
    for fdr in feeders:
        fdr_id = fdr[0]
        sub_id = fdr[1]
        n_cust = fdr[13]
        n_outages = random.randint(3, 10)
        # Distribute: ~40% heat, ~30% storm, ~30% normal
        n_heat = max(1, round(n_outages * 0.40))
        n_storm = max(1, round(n_outages * 0.30))
        n_normal = n_outages - n_heat - n_storm

        for pool, causes, count in [
            (heat_days, heat_causes, n_heat),
            (storm_days, storm_causes, n_storm),
            (normal_days, normal_causes, n_normal),
        ]:
            if not pool:
                pool = list(range(365))
            for _ in range(max(0, count)):
                outage_num += 1
                day_offset = random.choice(pool)
                # Storm outages cluster in afternoon/evening
                if causes is storm_causes:
                    hour = random.choice([14, 15, 16, 17, 18, 19, 20])
                # Heat outages cluster in late afternoon peak
                elif causes is heat_causes:
                    hour = random.choice([13, 14, 15, 16, 17, 18])
                else:
                    hour = random.randint(0, 23)
                start_ts = start_date + timedelta(days=day_offset, hours=hour)
                cause = random.choice(causes)
                # Storm/heat outages tend to be longer and affect more customers
                if causes is storm_causes:
                    duration = round(random.uniform(1.0, 18.0), 2)
                    affected = random.randint(50, min(n_cust, 3000))
                elif causes is heat_causes:
                    duration = round(random.uniform(0.5, 8.0), 2)
                    affected = random.randint(20, min(n_cust, 1500))
                else:
                    duration = round(random.uniform(0.25, 6.0), 2)
                    affected = random.randint(1, min(n_cust, 500))
                end_ts = start_ts + timedelta(hours=duration)
                equip = random.choice(["overhead line", "transformer", "switch", "fuse", "recloser", "cable"])
                weather = 1 if causes in (storm_causes, heat_causes) else 0
                rows.append([
                    f"OUT-{outage_num:05d}", fdr_id, sub_id,
                    start_ts.strftime("%Y-%m-%d %H:%M"),
                    end_ts.strftime("%Y-%m-%d %H:%M"),
                    duration, cause, affected, equip, weather,
                ])
    write_csv("outage_history.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 14. Network nodes and edges — with switches, reclosers, ties
# ---------------------------------------------------------------------------

def generate_network_nodes_and_edges(substations, feeders, transformers):
    print("Generating network nodes...")
    node_headers = [
        "node_id", "node_type", "substation_id", "feeder_id",
        "latitude", "longitude",
        "nominal_voltage_kv", "equipment_class",
        "rated_capacity", "rated_capacity_units",
        "phase", "installation_year", "status",
    ]
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

    nodes = []
    node_set = set()
    edges = []
    edge_num = 0

    def add_node(row):
        if row[0] not in node_set:
            node_set.add(row[0])
            nodes.append(row)

    conductor_specs = {
        "336 ACSR": (0.306, 0.444, 400), "477 ACSR": (0.216, 0.420, 530),
        "795 ACSR": (0.130, 0.390, 700), "1/0 AL": (0.592, 0.477, 230),
        "4/0 AL": (0.297, 0.434, 340), "397.5 AAC": (0.240, 0.430, 480),
    }
    lateral_conductors = ["1/0 AL", "4/0 AL", "#2 ACSR", "#4 CU"]
    lateral_specs = {
        "1/0 AL": (0.592, 0.477, 230), "4/0 AL": (0.297, 0.434, 340),
        "#2 ACSR": (0.895, 0.502, 150), "#4 CU": (1.503, 0.511, 100),
    }

    # --- Substation bus nodes ---
    for sub in substations:
        add_node([
            sub[0], "substation_bus", sub[0], "",
            float(sub[2]), float(sub[3]), sub[4], "substation",
            sub[6], "MVA", "ABC", "", sub[10],
        ])

    # --- Feeder head (breaker) and tail (open point) nodes ---
    for fdr in feeders:
        fdr_id, sub_id, v_kv = fdr[0], fdr[1], fdr[3]
        head_lat, head_lon = float(fdr[4]), float(fdr[5])
        tail_lat, tail_lon = float(fdr[6]), float(fdr[7])
        add_node([
            f"{fdr_id}-HEAD", "feeder_breaker", sub_id, fdr_id,
            head_lat, head_lon, v_kv, "breaker",
            fdr[11], "MW", "ABC", "", "closed",
        ])
        add_node([
            f"{fdr_id}-TAIL", "feeder_endpoint", sub_id, fdr_id,
            tail_lat, tail_lon, v_kv, "open_point",
            "", "", "ABC", "", "open",
        ])

    # --- Transformer nodes ---
    for xfmr in transformers:
        add_node([
            xfmr[0], "transformer", xfmr[2], xfmr[1],
            float(xfmr[3]), float(xfmr[4]), xfmr[7],
            "distribution_transformer", xfmr[5], "kVA", xfmr[6], "", xfmr[11],
        ])

    # --- Build edges per feeder with switching devices ---
    fdr_xfmrs = {}
    for xfmr in transformers:
        fdr_xfmrs.setdefault(xfmr[1], []).append(xfmr)

    # Track trunk junctions per feeder for tie generation later
    fdr_junctions = {}  # fdr_id -> [(jct_id, lat, lon, mile_marker)]

    for fdr in feeders:
        fdr_id, sub_id, v_kv = fdr[0], fdr[1], fdr[3]
        head_lat, head_lon = float(fdr[4]), float(fdr[5])
        tail_lat, tail_lon = float(fdr[6]), float(fdr[7])
        length = float(fdr[9])
        trunk_conductor = fdr[10]
        trunk_r, trunk_x, trunk_amps = conductor_specs.get(
            trunk_conductor, (0.25, 0.43, 400),
        )

        # Bus tie: substation -> feeder breaker
        edge_num += 1
        edges.append([
            f"EDGE-{edge_num:06d}", sub_id, f"{fdr_id}-HEAD",
            fdr_id, sub_id, "bus_tie", trunk_conductor, "ABC",
            0.01, 52.8,
            round(trunk_r * random.uniform(0.9, 1.1), 4),
            round(trunk_x * random.uniform(0.9, 1.1), 4),
            round((trunk_r + trunk_x) * 0.5, 4),
            trunk_amps, v_kv, 3, 1, "", "closed",
        ])

        xfmrs = fdr_xfmrs.get(fdr_id, [])
        if not xfmrs:
            continue

        def dist_from_head(x, _hlat=head_lat, _hlon=head_lon):
            return (float(x[3]) - _hlat) ** 2 + (float(x[4]) - _hlon) ** 2
        xfmrs_sorted = sorted(xfmrs, key=dist_from_head)

        trunk_spacing = max(1, len(xfmrs_sorted) // 8)
        trunk_nodes = []
        recloser_interval = max(1, len(xfmrs_sorted) // 3)  # ~3 reclosers per feeder

        for idx, xfmr in enumerate(xfmrs_sorted):
            xfmr_lat, xfmr_lon = float(xfmr[3]), float(xfmr[4])
            frac = (idx + 1) / (len(xfmrs_sorted) + 1)
            mile_marker = round(frac * length, 2)

            if idx % trunk_spacing == 0:
                tap_id = f"JCT-{fdr_id}-{len(trunk_nodes) + 1:03d}"
                tap_lat, tap_lon = point_along_route(
                    head_lat, head_lon, tail_lat, tail_lon, frac,
                )
                trunk_nodes.append((tap_id, tap_lat, tap_lon, mile_marker))

                # Determine if this junction hosts a switching device
                if idx > 0 and idx % recloser_interval == 0:
                    equip_class = "recloser"
                elif len(trunk_nodes) % 4 == 0:
                    equip_class = "sectionalizer"
                else:
                    equip_class = "pole_top" if random.random() > 0.2 else "padmount"

                add_node([
                    tap_id, "junction", sub_id, fdr_id,
                    tap_lat, tap_lon, v_kv, equip_class,
                    "", "", "ABC", "", "active",
                ])

                # Trunk edge
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
                    f"EDGE-{edge_num:06d}", prev_id, tap_id,
                    fdr_id, sub_id,
                    "primary_overhead" if is_oh else "primary_underground",
                    trunk_conductor, "ABC",
                    seg_len, seg_ft,
                    round(trunk_r * random.uniform(0.9, 1.1), 4),
                    round(trunk_x * random.uniform(0.9, 1.1), 4),
                    round((trunk_r + trunk_x) * 0.5 * random.uniform(0.9, 1.1), 4),
                    trunk_amps, v_kv, 3, is_oh, "", "closed",
                ])

            # Lateral: fuse node + edge to transformer
            nearest = trunk_nodes[-1]
            fuse_id = f"FUSE-{xfmr[0]}"
            fuse_lat, fuse_lon = point_along_route(
                nearest[1], nearest[2], xfmr_lat, xfmr_lon, 0.15,
            )
            add_node([
                fuse_id, "protective_device", sub_id, fdr_id,
                fuse_lat, fuse_lon, v_kv, "fuse",
                "", "", xfmr[6], "", "closed",
            ])
            # Edge: junction -> fuse
            lat_len_total = round(max(math.sqrt(
                (xfmr_lat - nearest[1]) ** 2 + (xfmr_lon - nearest[2]) ** 2
            ) * 69, 0.001), 3)
            lat_cond = random.choice(lateral_conductors)
            lat_r, lat_x, lat_amps = lateral_specs[lat_cond]
            xfmr_phase = xfmr[6]
            n_phases = min(len(xfmr_phase), 3)
            is_oh = 1 if random.random() > 0.25 else 0
            edge_num += 1
            edges.append([
                f"EDGE-{edge_num:06d}", nearest[0], fuse_id,
                fdr_id, sub_id,
                "lateral_overhead" if is_oh else "lateral_underground",
                lat_cond, xfmr_phase,
                round(lat_len_total * 0.15, 3), round(lat_len_total * 0.15 * 5280, 1),
                round(lat_r * random.uniform(0.9, 1.1), 4),
                round(lat_x * random.uniform(0.9, 1.1), 4),
                round((lat_r + lat_x) * 0.5, 4),
                lat_amps, v_kv, n_phases, is_oh, "", "closed",
            ])
            # Edge: fuse -> transformer
            edge_num += 1
            edges.append([
                f"EDGE-{edge_num:06d}", fuse_id, xfmr[0],
                fdr_id, sub_id,
                "lateral_overhead" if is_oh else "lateral_underground",
                lat_cond, xfmr_phase,
                round(lat_len_total * 0.85, 3), round(lat_len_total * 0.85 * 5280, 1),
                round(lat_r * random.uniform(0.9, 1.1), 4),
                round(lat_x * random.uniform(0.9, 1.1), 4),
                round((lat_r + lat_x) * 0.5, 4),
                lat_amps, v_kv, n_phases, is_oh, "", "closed",
            ])

        # Final trunk segment to tail
        if trunk_nodes:
            last = trunk_nodes[-1]
            seg_len = round(max(length - last[3], 0.01), 3)
            seg_ft = round(seg_len * 5280, 1)
            is_oh = 1 if random.random() > 0.15 else 0
            edge_num += 1
            edges.append([
                f"EDGE-{edge_num:06d}", last[0], f"{fdr_id}-TAIL",
                fdr_id, sub_id,
                "primary_overhead" if is_oh else "primary_underground",
                trunk_conductor, "ABC",
                seg_len, seg_ft,
                round(trunk_r * random.uniform(0.9, 1.1), 4),
                round(trunk_x * random.uniform(0.9, 1.1), 4),
                round((trunk_r + trunk_x) * 0.5, 4),
                trunk_amps, v_kv, 3, is_oh, "", "open",
            ])

        fdr_junctions[fdr_id] = trunk_nodes

    # --- Tie switches between geographically adjacent feeders ---
    print("  adding tie switches...")
    fdr_list = [(f[0], f[1], float(f[6]), float(f[7]), f[3], f[10]) for f in feeders]
    tie_num = 0
    for i in range(len(fdr_list)):
        for j in range(i + 1, len(fdr_list)):
            fdr_a, sub_a, tail_a_lat, tail_a_lon, v_a, cond_a = fdr_list[i]
            fdr_b, sub_b, tail_b_lat, tail_b_lon, v_b, cond_b = fdr_list[j]
            # Only tie feeders at the same voltage
            if v_a != v_b:
                continue
            # Check if feeder tails are within ~1.5 miles
            dist = math.sqrt(
                ((tail_a_lat - tail_b_lat) / MILE_LAT) ** 2
                + ((tail_a_lon - tail_b_lon) / MILE_LON) ** 2
            )
            if dist > 1.5:
                continue
            # Create a tie switch
            tie_num += 1
            tie_lat = round((tail_a_lat + tail_b_lat) / 2, 6)
            tie_lon = round((tail_a_lon + tail_b_lon) / 2, 6)
            tie_id = f"TIE-{tie_num:04d}"
            add_node([
                tie_id, "tie_switch", sub_a, fdr_a,
                tie_lat, tie_lon, v_a, "tie_switch",
                "", "", "ABC", "", "open",
            ])
            # Edge from feeder A tail to tie switch
            tie_len = round(dist / 2, 3)
            cond = cond_a
            r, x, amps = conductor_specs.get(cond, (0.25, 0.43, 400))
            edge_num += 1
            edges.append([
                f"EDGE-{edge_num:06d}", f"{fdr_a}-TAIL", tie_id,
                fdr_a, sub_a, "tie", cond, "ABC",
                max(tie_len, 0.01), round(max(tie_len, 0.01) * 5280, 1),
                round(r, 4), round(x, 4), round((r + x) * 0.5, 4),
                amps, v_a, 3, 1, "", "open",
            ])
            # Edge from tie switch to feeder B tail
            edge_num += 1
            edges.append([
                f"EDGE-{edge_num:06d}", tie_id, f"{fdr_b}-TAIL",
                fdr_b, sub_b, "tie", cond, "ABC",
                max(tie_len, 0.01), round(max(tie_len, 0.01) * 5280, 1),
                round(r, 4), round(x, 4), round((r + x) * 0.5, 4),
                amps, v_b, 3, 1, "", "open",
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
    print("Sisyphean Power & Light — Demo Data Generator")
    print("(Fictional utility — all data is synthetic)")
    print("=" * 60)
    print()
    substations = generate_substations()
    feeders = generate_feeders(substations)
    transformers = generate_transformers(feeders)
    customers = generate_customers(transformers, feeders)
    generate_load_profiles(feeders)
    generate_customer_interval_data(customers)
    generate_solar_installations(customers)
    generate_solar_profiles()
    generate_ev_chargers(customers)
    generate_ev_profiles()
    weather_rows = generate_weather_data()
    generate_growth_scenarios()
    generate_outage_history(feeders, weather_rows)
    generate_network_nodes_and_edges(substations, feeders, transformers)
    print()
    print("All demo datasets generated successfully.")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
