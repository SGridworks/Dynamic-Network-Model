#!/usr/bin/env python3
"""
Generate synthetic demo datasets for the Dynamic Network Model.

SYNTHETIC DATA NOTICE
    Sisyphean Power & Light (SP&L) is an entirely fictional utility.
    All data produced by this script is computationally generated.
    No real customer, infrastructure, or operational data is included.

Creates realistic utility distribution system data modeled after SP&L,
a fictional mid-size electric utility serving ~175,000+ customers across
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
import gzip
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

def write_csv(filename, headers, rows, compress=False):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    if compress:
        gz_path = path + ".gz"
        with open(path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            f_out.writelines(f_in)
        print(f"  wrote {len(rows):>10,} rows -> {filename} + .gz")
    else:
        print(f"  wrote {len(rows):>10,} rows -> {filename}")


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
    # --- Phase 2: Distribution-level BTM expansion (8 new substations) ---
    ("Estrella Ranch",     -4.5, -6, "Southern Ave", "51st Ave"),
    ("Midtown Gateway",     0.0,  2, "Van Buren St", "16th St"),
    ("Buckeye Logistics",  -1.0, -7, "Buckeye Rd", "59th Ave"),
    ("Scottsdale Corridor", 8.5,  6, "Glendale Ave", "48th St"),
    ("Laveen Crossing",    -6.0, -5, "Baseline Rd", "43rd Ave"),
    ("Arcadia Heights",     5.5,  6, "Camelback Rd", "48th St"),
    ("Maryvale Junction",   3.0, -6, "Thomas Rd", "51st Ave"),
    ("Desert Ridge",       11.5,  3, "Cactus Rd", "24th St"),
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
    # Maximum ratio of total contracted demand to transformer kVA.
    # A ratio of 1.5 means total contracted demand can be up to 150% of
    # the transformer's rated kVA — realistic given that customers don't
    # all peak simultaneously (typical diversity factor ~0.4-0.6).
    MAX_DEMAND_KVA_RATIO = 1.5
    # Build direction lookup by feeder
    fdr_dir = {f[0]: f[8] for f in feeders}
    rows = []
    cust_num = 0
    for xfmr in transformers:
        xfmr_id = xfmr[0]
        fdr_id = xfmr[1]
        sub_id = xfmr[2]
        xfmr_lat, xfmr_lon = float(xfmr[3]), float(xfmr[4])
        xfmr_kva = float(xfmr[5])
        direction = fdr_dir.get(fdr_id, "N")
        n_cust = random.randint(1, 12)
        # Capacity budget: total contracted demand capped at ratio * kVA
        demand_budget_kw = xfmr_kva * MAX_DEMAND_KVA_RATIO
        total_demand = 0.0
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
            # Cap demand so aggregate stays within transformer budget
            remaining = demand_budget_kw - total_demand
            if remaining <= 0:
                # Assign minimum demand
                demand = round(random.uniform(1, 3), 1)
            elif demand > remaining:
                demand = round(min(demand, remaining), 1)
            total_demand += demand
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
    print("Generating load profiles (15-min intervals, 5 years)...")
    headers = [
        "feeder_id", "substation_id", "timestamp",
        "load_mw", "load_mvar", "voltage_pu", "power_factor",
    ]
    # One representative week per season for each year 2020–2024
    # with ~1.5% year-over-year load growth (compounding from 2020 base)
    LOAD_GROWTH_RATE = 0.015  # 1.5% per year
    BASE_YEAR = 2020
    rows = []
    for fdr in feeders:
        fdr_id = fdr[0]
        sub_id = fdr[1]
        peak_mw = float(fdr[12])
        for year in range(2020, 2025):
            growth_factor = (1 + LOAD_GROWTH_RATE) ** (year - BASE_YEAR)
            seasons = {
                "winter": (datetime(year, 1, 15), 0.70),
                "spring": (datetime(year, 4, 15), 0.60),
                "summer": (datetime(year, 7, 15), 1.00),
                "fall":   (datetime(year, 10, 15), 0.65),
            }
            for _, (start_dt, season_mult) in seasons.items():
                # 168 hours * 4 = 672 intervals per week
                for interval in range(168 * 4):
                    ts = start_dt + timedelta(minutes=15 * interval)
                    hour_frac = ts.hour + ts.minute / 60.0
                    dow = ts.weekday()
                    d = _diurnal(hour_frac, dow)
                    load_mw = round(
                        peak_mw * season_mult * d * growth_factor
                        * random.uniform(0.93, 1.07), 3,
                    )
                    pf = round(random.uniform(0.88, 0.98), 3)
                    load_mvar = round(load_mw * math.tan(math.acos(pf)), 3)
                    voltage_pu = round(random.uniform(0.95, 1.05), 4)
                    rows.append([
                        fdr_id, sub_id, ts.strftime("%Y-%m-%d %H:%M"),
                        load_mw, load_mvar, voltage_pu, pf,
                    ])
    write_csv("load_profiles.csv", headers, rows, compress=True)
    return rows


# ---------------------------------------------------------------------------
# 6. Customer interval data (15-min AMI metering, sample of customers)
# ---------------------------------------------------------------------------

def generate_customer_interval_data(customers):
    """Generate 15-min AMI interval data for a sample of ~500 customers
    covering one representative week per season for each year 2020–2024
    (4 seasons × 5 years = 20 weeks per customer).
    """
    print("Generating customer interval data (15-min AMI, 5 years)...")
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

    # Seasonal multipliers for demand patterns
    season_demand_mult = {
        "winter": 0.75, "spring": 0.65, "summer": 1.00, "fall": 0.70,
    }
    # HVAC cycling intensity by season
    season_hvac_mult = {
        "winter": 0.08, "spring": 0.03, "summer": 0.15, "fall": 0.05,
    }
    LOAD_GROWTH_RATE = 0.015  # 1.5% per year, matching load profiles

    rows = []
    for cust in sample:
        cust_id = cust[0]
        xfmr_id = cust[1]
        fdr_id = cust[2]
        sub_id = cust[3]
        ctype = cust[4]
        contracted_kw = float(cust[6])
        for year in range(2020, 2025):
            growth_factor = (1 + LOAD_GROWTH_RATE) ** (year - 2020)
            seasons = {
                "winter": datetime(year, 1, 15),
                "spring": datetime(year, 4, 15),
                "summer": datetime(year, 7, 15),
                "fall":   datetime(year, 10, 15),
            }
            for season_name, start_dt in seasons.items():
                s_mult = season_demand_mult[season_name]
                hvac_mult = season_hvac_mult[season_name]
                for interval in range(7 * 96):  # 7 days x 96 intervals
                    ts = start_dt + timedelta(minutes=15 * interval)
                    hour_frac = ts.hour + ts.minute / 60.0
                    dow = ts.weekday()
                    if ctype == "residential":
                        if 0 <= hour_frac < 6:
                            base = 0.25
                        elif 6 <= hour_frac < 9:
                            base = 0.35 + 0.15 * ((hour_frac - 6) / 3)
                        elif 9 <= hour_frac < 15:
                            base = 0.30
                        elif 15 <= hour_frac < 21:
                            base = 0.50 + 0.40 * math.sin(math.pi * (hour_frac - 15) / 6)
                        else:
                            base = 0.40 - 0.10 * ((hour_frac - 21) / 3)
                        hvac = hvac_mult * abs(math.sin(math.pi * interval / 3))
                        noise = random.uniform(-0.10, 0.10)
                        demand = contracted_kw * s_mult * growth_factor * max(0.05, base + hvac + noise)
                    elif ctype == "commercial":
                        if 7 <= hour_frac < 20 and dow < 5:
                            base = 0.55 + 0.30 * math.sin(math.pi * (hour_frac - 7) / 13)
                        elif 8 <= hour_frac < 17 and dow >= 5:
                            base = 0.30
                        else:
                            base = 0.15
                        noise = random.uniform(-0.08, 0.08)
                        demand = contracted_kw * s_mult * growth_factor * max(0.05, base + noise)
                    elif ctype == "industrial":
                        shift_hour = hour_frac % 8
                        base = 0.70 + 0.10 * math.sin(math.pi * shift_hour / 8)
                        if 5.5 < shift_hour < 6.5:
                            base -= 0.15
                        noise = random.uniform(-0.05, 0.05)
                        demand = contracted_kw * s_mult * growth_factor * max(0.10, base + noise)
                    else:
                        if 7 <= hour_frac < 18 and dow < 5:
                            base = 0.60
                        else:
                            base = 0.20
                        noise = random.uniform(-0.08, 0.08)
                        demand = contracted_kw * s_mult * growth_factor * max(0.05, base + noise)

                    demand = round(demand, 2)
                    energy = round(demand * 0.25, 3)
                    voltage = round(random.uniform(228, 244), 1) if ctype != "industrial" else round(random.uniform(470, 490), 1)
                    pf = round(random.uniform(0.85, 0.99), 3)
                    rows.append([
                        cust_id, xfmr_id, fdr_id, sub_id, ctype,
                        ts.strftime("%Y-%m-%d %H:%M"),
                        demand, energy, voltage, pf,
                    ])
    write_csv("customer_interval_data.csv", headers, rows, compress=True)
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
    print("Generating weather data (5 years)...")
    headers = [
        "timestamp", "temperature_f", "humidity_pct", "wind_speed_mph",
        "ghi_w_per_m2", "cloud_cover_pct", "is_heatwave", "is_storm",
    ]
    rows = []
    base_temps = {
        1: 55, 2: 58, 3: 65, 4: 75, 5: 85, 6: 100,
        7: 105, 8: 103, 9: 97, 10: 82, 11: 66, 12: 55,
    }
    # Slight per-year offsets for realism (climate trend + natural variation)
    year_temp_offsets = {2020: -1.0, 2021: 0.0, 2022: 0.5, 2023: 0.8, 2024: 1.2}
    year_storm_mult = {2020: 0.9, 2021: 1.0, 2022: 1.0, 2023: 1.1, 2024: 1.15}

    for year in range(2020, 2025):
        start = datetime(year, 1, 1)
        days_in_year = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
        temp_offset = year_temp_offsets[year]
        storm_mult = year_storm_mult[year]
        for day_offset in range(days_in_year):
            dt = start + timedelta(days=day_offset)
            month = dt.month
            base_t = base_temps[month] + temp_offset
            is_heatwave = 0
            is_storm = 0
            # Heatwave events: multi-day stretches in summer
            if month in (6, 7, 8) and day_offset % 30 < 5 and random.random() < 0.6:
                is_heatwave = 1
                base_t += random.uniform(5, 15)
            # Storm events: monsoon season (Jul-Sep) and winter storms
            if month in (7, 8, 9) and random.random() < 0.12 * storm_mult:
                is_storm = 1
            elif month in (12, 1, 2) and random.random() < 0.06 * storm_mult:
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
# 11b. Battery installations — co-located with their customer
# ---------------------------------------------------------------------------

def generate_battery_installations(customers):
    print("Generating battery installations...")
    headers = [
        "battery_id", "customer_id", "transformer_id", "feeder_id",
        "substation_id", "latitude", "longitude",
        "capacity_kwh", "power_kw", "chemistry",
        "install_date", "manufacturer", "status",
    ]
    chemistries = ["lithium-ion", "LFP", "NMC"]
    manufacturers = ["Tesla", "Enphase", "SolarEdge", "BYD", "Generac", "SunPower"]
    rows = []
    batt_num = 0
    batt_custs = [c for c in customers if c[11] == 1]
    for cust in batt_custs:
        batt_num += 1
        cust_id, xfmr_id, fdr_id, sub_id = cust[0], cust[1], cust[2], cust[3]
        lat, lon = float(cust[7]), float(cust[8])
        ctype = cust[4]
        if ctype == "residential":
            capacity_kwh = round(random.choice([10, 13.5, 16, 20]) * random.uniform(0.9, 1.1), 1)
            power_kw = round(capacity_kwh * random.uniform(0.3, 0.5), 1)
        elif ctype == "commercial":
            capacity_kwh = round(random.uniform(50, 500), 1)
            power_kw = round(capacity_kwh * random.uniform(0.25, 0.5), 1)
        else:
            capacity_kwh = round(random.uniform(10, 100), 1)
            power_kw = round(capacity_kwh * random.uniform(0.3, 0.5), 1)
        chemistry = random.choice(chemistries)
        year = random.randint(2020, 2024)
        month = random.randint(1, 12)
        mfr = random.choice(manufacturers)
        status = "active" if random.random() > 0.02 else "inactive"
        rows.append([
            f"BATT-{batt_num:06d}", cust_id, xfmr_id, fdr_id, sub_id,
            lat, lon, capacity_kwh, power_kw, chemistry,
            f"{year}-{month:02d}-01", mfr, status,
        ])
    write_csv("battery_installations.csv", headers, rows)
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
        "community_solar_capacity_mw", "ev_depot_count",
        "microgrid_count", "chp_capacity_mw",
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
        "SCN-001": dict(ev_r=2.5, sol_r=1.8, bat_r=0.8, lg=1.0, lg_r=0.15, pg=1.2, pg_r=0.2, ee_r=0.1, el=2, el_r=0.5, cs=15, cs_r=5, dep=3, dep_r=1, mg=10, mg_r=0, chp=8, chp_r=2),
        "SCN-002": dict(ev_r=5.0, sol_r=2.0, bat_r=1.2, lg=1.5, lg_r=0.3, pg=2.0, pg_r=0.4, ee_r=0.1, el=3, el_r=0.8, cs=20, cs_r=8, dep=5, dep_r=3, mg=10, mg_r=1, chp=8, chp_r=1),
        "SCN-003": dict(ev_r=2.0, sol_r=4.5, bat_r=2.5, lg=0.5, lg_r=0.05, pg=0.8, pg_r=0.1, ee_r=0.2, el=2, el_r=0.3, cs=30, cs_r=15, dep=3, dep_r=1, mg=12, mg_r=1, chp=10, chp_r=3),
        "SCN-004": dict(ev_r=2.5, sol_r=2.0, bat_r=1.0, lg=2.0, lg_r=0.4, pg=3.0, pg_r=0.6, ee_r=0.1, el=2, el_r=0.4, cs=15, cs_r=5, dep=3, dep_r=1, mg=10, mg_r=0, chp=8, chp_r=2),
        "SCN-005": dict(ev_r=4.0, sol_r=3.0, bat_r=2.0, lg=2.5, lg_r=0.5, pg=3.0, pg_r=0.55, ee_r=0.15, el=5, el_r=2.0, cs=25, cs_r=12, dep=8, dep_r=4, mg=15, mg_r=2, chp=12, chp_r=4),
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
                round(p["cs"] + yr * p["cs_r"], 1),
                p["dep"] + yr * p["dep_r"],
                p["mg"] + yr * p["mg_r"],
                round(p["chp"] + yr * p["chp_r"], 1),
                desc,
            ])
    write_csv("growth_scenarios.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 13. Outage history — clustered during storms and heat events
# ---------------------------------------------------------------------------

def generate_outage_history(feeders, weather_rows):
    print("Generating outage history (5 years)...")
    headers = [
        "outage_id", "feeder_id", "substation_id",
        "start_time", "end_time", "duration_hours",
        "cause", "customers_affected", "equipment_involved",
        "weather_related",
    ]
    # Build day-level weather index keyed by (year, day_of_year)
    day_wx = {}  # (year, doy) -> {heatwave, storm, max_temp}
    for wr in weather_rows:
        ts = datetime.strptime(wr[0], "%Y-%m-%d %H:%M")
        key = (ts.year, ts.timetuple().tm_yday - 1)  # 0-based day of year
        temp = float(wr[1])
        hw = int(wr[6])
        st = int(wr[7])
        if key not in day_wx:
            day_wx[key] = {"heatwave": hw, "storm": st, "max_temp": temp}
        else:
            day_wx[key]["max_temp"] = max(day_wx[key]["max_temp"], temp)
            day_wx[key]["heatwave"] = max(day_wx[key]["heatwave"], hw)
            day_wx[key]["storm"] = max(day_wx[key]["storm"], st)

    heat_causes = ["equipment failure", "overload", "underground cable fault"]
    storm_causes = ["tree contact", "lightning", "storm damage", "animal contact"]
    normal_causes = ["equipment failure", "animal contact", "vehicle accident",
                     "dig-in", "underground cable fault", "scheduled maintenance"]

    rows = []
    outage_num = 0
    # Slight increase in outage frequency over time (aging infrastructure)
    year_outage_mult = {2020: 0.85, 2021: 0.90, 2022: 0.95, 2023: 1.05, 2024: 1.10}

    for year in range(2020, 2025):
        days_in_year = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
        start_date = datetime(year, 1, 1)
        mult = year_outage_mult[year]

        # Classify days for this year
        heat_days = [d for d in range(days_in_year)
                     if (year, d) in day_wx and
                     (day_wx[(year, d)]["heatwave"] or day_wx[(year, d)]["max_temp"] > 110)]
        storm_days = [d for d in range(days_in_year)
                      if (year, d) in day_wx and day_wx[(year, d)]["storm"]]
        normal_days = [d for d in range(days_in_year)
                       if d not in heat_days and d not in storm_days]

        for fdr in feeders:
            fdr_id = fdr[0]
            sub_id = fdr[1]
            n_cust = fdr[13]
            base_outages = random.randint(4, 11)
            n_outages = max(3, round(base_outages * mult))
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
                    pool = list(range(days_in_year))
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
                tie_id, "tie_switch", sub_a, "",
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
# 15. Community solar — ground-mount shared facilities at feeder level
# ---------------------------------------------------------------------------

def generate_community_solar(feeders):
    print("Generating community solar facilities...")
    headers = [
        "community_solar_id", "feeder_id", "substation_id",
        "latitude", "longitude",
        "nameplate_dc_mw", "nameplate_ac_mw", "dc_ac_ratio",
        "annual_degradation_rate",
        "tilt_degrees", "azimuth_degrees",
        "subscriber_count", "subscription_type",
        "interconnection_date", "interconnection_level", "status",
    ]
    subscription_types = ["fixed_bill", "percentage_of_output", "capacity_block"]
    rows = []
    cs_num = 0
    for fdr in feeders:
        if random.random() < 0.35:
            cs_num += 1
            fdr_id = fdr[0]
            sub_id = fdr[1]
            head_lat, head_lon = float(fdr[4]), float(fdr[5])
            tail_lat, tail_lon = float(fdr[6]), float(fdr[7])
            frac = random.uniform(0.5, 0.9)
            lat, lon = point_along_route(head_lat, head_lon, tail_lat, tail_lon, frac)
            dc_mw = round(random.uniform(1.0, 5.0), 2)
            dc_ac = round(random.uniform(1.2, 1.4), 2)
            ac_mw = round(dc_mw / dc_ac, 2)
            degradation = round(random.uniform(0.004, 0.006), 4)
            tilt = round(random.uniform(20, 30), 1)
            azimuth = round(random.uniform(170, 200), 1)
            subscribers = random.randint(50, 500)
            sub_type = random.choice(subscription_types)
            year = random.randint(2019, 2024)
            month = random.randint(1, 12)
            level = random.choice(["Level 2", "Level 3"])
            status = random.choice(["active", "active", "active", "under_construction"])
            rows.append([
                f"CS-{cs_num:04d}", fdr_id, sub_id, lat, lon,
                dc_mw, ac_mw, dc_ac, degradation,
                tilt, azimuth, subscribers, sub_type,
                f"{year}-{month:02d}-01", level, status,
            ])
    write_csv("community_solar.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 16. EV charging depots — fleet-level DCFC facilities
# ---------------------------------------------------------------------------

def generate_ev_charging_depots(feeders, transformers):
    print("Generating EV charging depots...")
    headers = [
        "depot_id", "feeder_id", "substation_id", "transformer_id",
        "latitude", "longitude",
        "operator_name", "fleet_type",
        "num_chargers", "charger_power_kw", "total_capacity_mw",
        "transformer_kva", "transformer_dedicated",
        "peak_demand_mw", "operating_hours",
        "install_date", "status",
    ]
    operators = [
        "Valley Metro", "Amazon DSP", "UPS", "FedEx", "USPS",
        "First Student", "Republic Services", "Frito-Lay", "Sysco",
    ]
    fleet_types = ["transit_bus", "delivery_van", "school_bus", "freight"]
    industrial_subs = {"SUB-018"}
    rows = []
    depot_num = 0
    for fdr in feeders:
        sub_id = fdr[1]
        prob = 0.40 if sub_id in industrial_subs else 0.12
        if random.random() < prob:
            depot_num += 1
            fdr_id = fdr[0]
            fdr_xfmrs = [x for x in transformers if x[1] == fdr_id]
            if not fdr_xfmrs:
                continue
            xfmr = random.choice(fdr_xfmrs)
            lat, lon = float(xfmr[3]), float(xfmr[4])
            operator = random.choice(operators)
            fleet = random.choice(fleet_types)
            n_chargers = random.randint(10, 50)
            charger_kw = random.choice([150, 180, 350])
            total_mw = round(n_chargers * charger_kw / 1000, 2)
            xfmr_kva = random.choice([500, 750, 1000, 1500, 2000])
            dedicated = random.choice([True, True, False])
            peak_mw = round(total_mw * random.uniform(0.5, 0.8), 2)
            hours = random.choice(["06:00-22:00", "00:00-24:00", "05:00-23:00", "04:00-20:00"])
            year = random.randint(2021, 2024)
            month = random.randint(1, 12)
            status = "active" if random.random() > 0.1 else "planned"
            rows.append([
                f"DEPOT-{depot_num:04d}", fdr_id, sub_id, xfmr[0],
                lat, lon, operator, fleet,
                n_chargers, charger_kw, total_mw,
                xfmr_kva, dedicated,
                peak_mw, hours,
                f"{year}-{month:02d}-01", status,
            ])
    write_csv("ev_charging_depots.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 17. Microgrids — coordinated DER aggregates that can island
# ---------------------------------------------------------------------------

def generate_microgrids(feeders):
    print("Generating microgrids...")
    headers = [
        "microgrid_id", "feeder_id", "substation_id",
        "latitude", "longitude",
        "facility_type", "facility_name",
        "solar_capacity_mw", "battery_power_mw", "battery_energy_mwh",
        "chp_capacity_mw", "total_generation_mw",
        "peak_load_mw", "critical_load_mw",
        "can_island", "island_duration_hours",
        "interconnection_date", "status",
    ]
    facility_configs = [
        ("hospital_campus", "Banner Medical Center", 1.5, 1.0, 4.0, 2.0),
        ("hospital_campus", "HonorHealth Campus", 1.2, 0.8, 3.2, 1.5),
        ("university", "ASU Polytechnic Campus", 3.0, 2.0, 8.0, 1.0),
        ("university", "GCU North Campus", 2.0, 1.5, 6.0, 0.5),
        ("military", "Luke AFB Annex", 4.0, 3.0, 12.0, 2.5),
        ("commercial_campus", "PayPal Campus", 2.5, 2.0, 8.0, 0.0),
        ("commercial_campus", "State Farm Regional", 1.8, 1.2, 4.8, 0.0),
        ("water_treatment", "91st Ave WWTP", 2.0, 1.5, 6.0, 3.0),
        ("water_treatment", "Cave Creek WRP", 0.8, 0.5, 2.0, 1.0),
        ("commercial_campus", "Chandler Tech Park", 2.2, 1.8, 7.2, 0.0),
    ]
    rows = []
    available_feeders = list(feeders)
    random.shuffle(available_feeders)
    for i, (ftype, fname, solar_mw, batt_mw, batt_mwh, chp_mw) in enumerate(facility_configs):
        if i >= len(available_feeders):
            break
        fdr = available_feeders[i]
        fdr_id = fdr[0]
        sub_id = fdr[1]
        head_lat, head_lon = float(fdr[4]), float(fdr[5])
        tail_lat, tail_lon = float(fdr[6]), float(fdr[7])
        lat, lon = point_along_route(
            head_lat, head_lon, tail_lat, tail_lon, random.uniform(0.3, 0.7),
        )
        total_gen = round(solar_mw + chp_mw, 2)
        peak_load = round(total_gen * random.uniform(1.2, 2.0), 2)
        critical = round(peak_load * random.uniform(0.3, 0.6), 2)
        can_island = True
        if critical > 0:
            island_hrs = round(batt_mwh / critical, 1)
        else:
            island_hrs = round(batt_mwh / max(batt_mw, 0.1), 1)
        year = random.randint(2020, 2024)
        month = random.randint(1, 12)
        status = "active" if random.random() > 0.15 else "commissioning"
        rows.append([
            f"MG-{i+1:04d}", fdr_id, sub_id, lat, lon,
            ftype, fname,
            solar_mw, batt_mw, batt_mwh, chp_mw, total_gen,
            peak_load, critical, can_island, island_hrs,
            f"{year}-{month:02d}-01", status,
        ])
    write_csv("microgrids.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 18. Small CHP — reciprocating engines at commercial/institutional sites
# ---------------------------------------------------------------------------

def generate_small_chp(customers):
    print("Generating small CHP installations...")
    headers = [
        "chp_id", "customer_id", "transformer_id", "feeder_id", "substation_id",
        "latitude", "longitude",
        "facility_type", "nameplate_mw",
        "heat_rate_btu_per_kwh", "forced_outage_rate", "planned_outage_rate",
        "min_stable_level_fraction", "startup_time_minutes",
        "gas_pressure_psig_required", "ramp_rate_mw_per_min",
        "thermal_output_mmbtu_hr", "thermal_efficiency",
        "install_date", "status",
    ]
    facility_types = [
        "hospital", "university", "food_processing", "hotel",
        "data_center_small", "laundry", "brewery",
    ]
    eligible = [c for c in customers if c[4] in ("commercial", "industrial")]
    random.shuffle(eligible)
    n_chp = random.randint(15, 25)
    rows = []
    for i in range(min(n_chp, len(eligible))):
        cust = eligible[i]
        cust_id, xfmr_id, fdr_id, sub_id = cust[0], cust[1], cust[2], cust[3]
        lat, lon = float(cust[7]), float(cust[8])
        ftype = random.choice(facility_types)
        nameplate = round(random.uniform(0.5, 5.0), 2)
        heat_rate = random.randint(8500, 10500)
        for_rate = round(random.uniform(0.02, 0.06), 3)
        plan_rate = round(random.uniform(0.03, 0.05), 3)
        min_stable = round(random.uniform(0.25, 0.40), 2)
        startup = round(random.uniform(5, 30), 1)
        gas_psi = random.choice([2, 5, 15, 30, 60])
        ramp = round(nameplate * random.uniform(0.05, 0.15), 3)
        thermal = round(nameplate * random.uniform(3.0, 5.0), 2)
        thermal_eff = round(random.uniform(0.40, 0.55), 3)
        year = random.randint(2018, 2024)
        month = random.randint(1, 12)
        status = "active" if random.random() > 0.05 else "maintenance"
        rows.append([
            f"CHP-{i+1:04d}", cust_id, xfmr_id, fdr_id, sub_id,
            lat, lon, ftype, nameplate,
            heat_rate, for_rate, plan_rate,
            min_stable, startup, gas_psi, ramp,
            thermal, thermal_eff,
            f"{year}-{month:02d}-01", status,
        ])
    write_csv("small_chp.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 19. Commercial BESS — customer-sited or utility-sited battery storage
# ---------------------------------------------------------------------------

def generate_commercial_bess(customers):
    print("Generating commercial BESS installations...")
    headers = [
        "bess_id", "customer_id", "transformer_id", "feeder_id", "substation_id",
        "latitude", "longitude",
        "power_mw", "energy_mwh", "chemistry",
        "charge_efficiency", "discharge_efficiency",
        "min_soc_fraction", "max_soc_fraction",
        "augment_threshold", "capex_per_kwh",
        "application_type", "manufacturer",
        "install_date", "status",
    ]
    chemistries = ["LFP", "NMC"]
    applications = ["demand_charge_mgmt", "peak_shaving", "backup", "solar_shifting"]
    manufacturers = ["Tesla", "BYD", "Fluence", "Powin", "EnerSys", "Samsung SDI"]
    eligible = [c for c in customers if c[4] in ("commercial", "industrial")]
    random.shuffle(eligible)
    n_bess = random.randint(30, 50)
    rows = []
    for i in range(min(n_bess, len(eligible))):
        cust = eligible[i]
        cust_id, xfmr_id, fdr_id, sub_id = cust[0], cust[1], cust[2], cust[3]
        lat, lon = float(cust[7]), float(cust[8])
        power_mw = round(random.uniform(0.25, 2.0), 3)
        duration = random.choice([2, 4])
        energy_mwh = round(power_mw * duration, 3)
        chem = random.choice(chemistries)
        charge_eff = round(random.uniform(0.90, 0.95), 3)
        discharge_eff = round(random.uniform(0.90, 0.95), 3)
        min_soc = 0.10
        max_soc = 0.90
        augment = 0.80
        capex = int(round(random.uniform(200, 350), 0))
        app = random.choice(applications)
        mfr = random.choice(manufacturers)
        year = random.randint(2021, 2024)
        month = random.randint(1, 12)
        status = "active" if random.random() > 0.05 else "commissioning"
        rows.append([
            f"CBESS-{i+1:04d}", cust_id, xfmr_id, fdr_id, sub_id,
            lat, lon, power_mw, energy_mwh, chem,
            charge_eff, discharge_eff, min_soc, max_soc,
            augment, capex, app, mfr,
            f"{year}-{month:02d}-01", status,
        ])
    write_csv("commercial_bess.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 20. Interconnection queue — distribution-level applications
# ---------------------------------------------------------------------------

def generate_interconnection_queue(feeders):
    print("Generating interconnection queue...")
    headers = [
        "application_id", "feeder_id", "substation_id",
        "applicant_name", "project_type",
        "requested_capacity_kw", "technology_type",
        "study_level", "study_status",
        "application_date", "study_completion_date",
        "estimated_cost", "system_upgrades_required",
        "ieee_1547_category", "status",
    ]
    project_types = [
        ("commercial_rooftop_solar", 0.35),
        ("community_solar", 0.15),
        ("ev_charging_facility", 0.15),
        ("residential_solar_storage", 0.15),
        ("small_chp", 0.10),
        ("microgrid", 0.05),
        ("commercial_bess", 0.05),
    ]
    tech_map = {
        "commercial_rooftop_solar": "solar_pv",
        "community_solar": "solar_pv",
        "ev_charging_facility": "load_only",
        "residential_solar_storage": "solar_plus_storage",
        "small_chp": "natural_gas_recip",
        "microgrid": "mixed_der",
        "commercial_bess": "battery_storage",
    }
    applicant_prefixes = [
        "SunPower", "NextEra", "Clearway", "Primergy", "AES",
        "Tesla", "ChargePoint", "Bloom", "Phoenix Solar Co",
        "Desert Energy", "Valley Clean", "Cactus Power",
        "Mesquite Energy", "Sun Valley", "Pioneer Solar",
    ]
    study_statuses = ["complete", "in_progress", "not_started", "waived"]
    app_statuses = ["approved", "in_review", "withdrawn", "pending", "active"]
    upgrades = [
        "none", "transformer_upgrade", "reconductoring",
        "voltage_regulator", "protection_relay_update", "new_service_transformer",
    ]
    rows = []
    n_apps = random.randint(80, 120)
    for i in range(n_apps):
        fdr = random.choice(feeders)
        fdr_id = fdr[0]
        sub_id = fdr[1]
        r_val = random.random()
        cum = 0
        ptype = "commercial_rooftop_solar"
        for pt, w in project_types:
            cum += w
            if r_val <= cum:
                ptype = pt
                break
        tech = tech_map[ptype]
        applicant = f"{random.choice(applicant_prefixes)} {random.choice(['LLC', 'Inc', 'Corp', 'LP'])}"
        if ptype == "commercial_rooftop_solar":
            cap_kw = round(random.uniform(50, 500), 0)
        elif ptype == "community_solar":
            cap_kw = round(random.uniform(1000, 5000), 0)
        elif ptype == "ev_charging_facility":
            cap_kw = round(random.uniform(500, 5000), 0)
        elif ptype == "residential_solar_storage":
            cap_kw = round(random.uniform(5, 25), 0)
        elif ptype == "small_chp":
            cap_kw = round(random.uniform(500, 5000), 0)
        elif ptype == "microgrid":
            cap_kw = round(random.uniform(2000, 10000), 0)
        else:
            cap_kw = round(random.uniform(250, 2000), 0)
        if cap_kw < 25:
            study_level = "Level 1 - Fast Track"
            study_days = 15
            ieee_cat = "Category I"
        elif cap_kw <= 5000:
            study_level = "Level 2 - Supplemental"
            study_days = 40
            ieee_cat = "Category II"
        else:
            study_level = "Level 3 - Detailed Study"
            study_days = random.randint(60, 120)
            ieee_cat = "Category III"
        year = random.randint(2022, 2024)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        app_date = datetime(year, month, day)
        comp_date = app_date + timedelta(days=study_days + random.randint(-5, 30))
        cost = round(random.uniform(5000, 500000), 0) if cap_kw > 100 else round(random.uniform(500, 5000), 0)
        upgrade = random.choice(upgrades)
        study_st = random.choice(study_statuses)
        app_st = random.choice(app_statuses)
        rows.append([
            f"IQ-{i+1:05d}", fdr_id, sub_id,
            applicant, ptype,
            int(cap_kw), tech,
            study_level, study_st,
            app_date.strftime("%Y-%m-%d"),
            comp_date.strftime("%Y-%m-%d"),
            int(cost), upgrade, ieee_cat, app_st,
        ])
    write_csv("interconnection_queue.csv", headers, rows)
    return rows


# ---------------------------------------------------------------------------
# 21. Hosting capacity — pre-computed per distribution transformer
# ---------------------------------------------------------------------------

def generate_hosting_capacity(transformers, solar_installations, batteries,
                              commercial_bess):
    print("Generating hosting capacity by transformer...")
    headers = [
        "transformer_id", "feeder_id",
        "rated_kva", "existing_der_kw", "allocated_load_kw",
        "thermal_hosting_capacity_kw", "voltage_hosting_capacity_kw",
        "limiting_factor", "hosting_capacity_kw",
    ]
    # Aggregate existing DER by transformer
    der_by_xfmr = {}
    for s in solar_installations:
        xid = s[2]  # transformer_id
        der_by_xfmr[xid] = der_by_xfmr.get(xid, 0) + float(s[7])  # capacity_kw
    for b in batteries:
        xid = b[2]  # transformer_id
        der_by_xfmr[xid] = der_by_xfmr.get(xid, 0) + float(b[8])  # power_kw
    for cb in commercial_bess:
        xid = cb[2]  # transformer_id
        der_by_xfmr[xid] = der_by_xfmr.get(xid, 0) + float(cb[7]) * 1000  # MW->kW
    rows = []
    for xfmr in transformers:
        xid = xfmr[0]
        fdr_id = xfmr[1]
        kva = float(xfmr[5])
        existing_der_kw = round(der_by_xfmr.get(xid, 0), 1)
        allocated_load_kw = round(kva * random.uniform(0.3, 0.8), 1)
        thermal_hc = round(
            max(0, kva * 0.85 - existing_der_kw * 0.5 - allocated_load_kw * 0.3)
            * random.uniform(0.8, 1.2), 1,
        )
        voltage_hc = round(
            max(0, kva * random.uniform(0.4, 0.7) - existing_der_kw * 0.8)
            * random.uniform(0.7, 1.1), 1,
        )
        hc = min(thermal_hc, voltage_hc)
        limiting = "voltage" if voltage_hc <= thermal_hc else "thermal"
        rows.append([
            xid, fdr_id, kva, existing_der_kw, allocated_load_kw,
            thermal_hc, voltage_hc, limiting, round(hc, 1),
        ])
    write_csv("hosting_capacity_by_transformer.csv", headers, rows)
    return rows


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

    # Fix: recompute feeders.num_customers from actual customer counts
    print("Recomputing feeder customer counts...")
    cust_per_fdr = {}
    for c in customers:
        cust_per_fdr[c[2]] = cust_per_fdr.get(c[2], 0) + 1
    for fdr in feeders:
        fdr[13] = cust_per_fdr.get(fdr[0], 0)
    # Rewrite feeders.csv with corrected counts
    fdr_headers = [
        "feeder_id", "substation_id", "name", "voltage_kv",
        "latitude_head", "longitude_head",
        "latitude_tail", "longitude_tail",
        "direction", "length_miles", "conductor_type",
        "rated_capacity_mw", "peak_load_mw", "num_customers", "status",
    ]
    write_csv("feeders.csv", fdr_headers, feeders)

    generate_load_profiles(feeders)
    generate_customer_interval_data(customers)
    solar_installations = generate_solar_installations(customers)
    generate_solar_profiles()
    generate_ev_chargers(customers)
    generate_ev_profiles()
    weather_rows = generate_weather_data()
    generate_growth_scenarios()
    generate_outage_history(feeders, weather_rows)
    generate_network_nodes_and_edges(substations, feeders, transformers)
    batteries = generate_battery_installations(customers)

    # Distribution-level DER datasets
    generate_community_solar(feeders)
    generate_ev_charging_depots(feeders, transformers)
    generate_microgrids(feeders)
    generate_small_chp(customers)
    commercial_bess = generate_commercial_bess(customers)
    generate_interconnection_queue(feeders)
    generate_hosting_capacity(transformers, solar_installations, batteries,
                              commercial_bess)
    print()
    print("All demo datasets generated successfully.")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
