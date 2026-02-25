#!/usr/bin/env python3
"""
Generate synthetic Boiler Feed Pump train data for SP&L Unit 1 (300MW 2x1 CCGT).

SYNTHETIC DATA NOTICE
    Sisyphean Power & Light (SP&L) is an entirely fictional utility.
    All data produced by this script is computationally generated.
    No real customer, infrastructure, or operational data is included.

Creates 1 year (2024) of 1-minute time-series data for a motor-driven
HP Boiler Feed Pump train at SP&L's 300MW combined-cycle generating station.

System boundary: BFP suction valves to BFP discharge valves.
    - Deaerator is OUTSIDE (upstream supply boundary)
    - HP Feedwater Heaters are OUTSIDE (downstream discharge boundary)

Equipment inside boundary (per pump, x2 trains A/B):
    - Motor-driven HP BFP (barrel-casing, multistage)
    - Drive motor (6.6 kV, direct-coupled)
    - Lube oil system (main + aux + emergency pumps)
    - Mechanical seals (tandem, API Plan 23)
    - Suction/discharge/recirc valves
    - Suction strainer

Tie-in to SP&L distribution dataset:
    Unit 1 MW output is derived from SP&L system demand using the same
    diurnal/seasonal patterns as the existing load_profiles data.
    Timestamps align with the existing weather and load time-series.

Output files (in sisyphean-power-and-light/generation/):
    timeseries/bfp_train_1min.parquet    - 1-minute averages
    timeseries/bfp_train_15min.parquet   - 15-minute rollup
    timeseries/bfp_train_hourly.parquet  - hourly rollup
    events/alarm_log.csv                 - DCS alarm history
    events/trip_log.csv                  - Equipment trips
    events/operator_actions.csv          - Manual interventions
    reference/pump_curves.csv            - OEM head-flow-efficiency
    reference/heat_balance.csv           - Unit load vs FW parameters
    reference/design_parameters.json     - Nameplate data, setpoints
    equipment_registry.csv               - Asset metadata
    tag_dictionary.csv                   - Full tag list

Usage:
    python generate_bfp_data.py

Requires: pandas, pyarrow (pip install pandas pyarrow)
"""

import csv
import json
import math
import os
import random
from datetime import datetime, timedelta

import pandas as pd

random.seed(42)

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(REPO_ROOT, "sisyphean-power-and-light", "generation")

# ===========================================================================
# PLANT DESIGN PARAMETERS
# ===========================================================================
# 2x1 CCGT: 2x GE 7F-class gas turbines + 1 steam turbine
# Triple-pressure HRSG with reheat

PLANT = {
    "name": "SP&L Generating Station 1",
    "unit_id": "U1",
    "type": "2x1 CCGT",
    "rated_mw": 300.0,
    "min_load_mw": 100.0,
    "gt_count": 2,
    "gt_rated_mw": 105.0,
    "st_rated_mw": 100.0,
    "hp_drum_pressure_barg": 130.0,
    "hp_steam_temp_c": 565.0,
    "da_pressure_barg": 7.0,
    "da_temperature_c": 165.0,
}

# Motor-driven HP BFP specs (2x100%, A=duty, B=standby)
BFP = {
    "count": 2,
    "type": "barrel-casing multistage",
    "stages": 8,
    "oem": "KSB",
    "model": "CHTD 8/6",
    "rated_speed_rpm": 2985,
    "rated_flow_tph": 300.0,
    "bep_flow_tph": 260.0,
    "min_cont_flow_tph": 75.0,
    "rated_suction_barg": 7.0,
    "rated_discharge_barg": 160.0,
    "rated_dp_bar": 153.0,
    "bep_efficiency": 0.80,
    "shutoff_dp_bar": 180.0,
    # Motor
    "motor_rated_kw": 1800,
    "motor_voltage_kv": 6.6,
    "motor_rated_a": 190.0,
    "motor_pf": 0.88,
    "motor_efficiency": 0.97,
    # Bearing limits (degC)
    "journal_normal": (60.0, 70.0),
    "journal_alarm": 85.0,
    "journal_trip": 95.0,
    "thrust_normal": (65.0, 75.0),
    "thrust_alarm": 95.0,
    "thrust_trip": 105.0,
    "motor_brg_normal": (55.0, 68.0),
    "motor_brg_alarm": 90.0,
    "motor_brg_trip": 100.0,
    # Vibration limits (um pk-pk shaft, mm/s housing)
    "shaft_vib_normal": (20.0, 40.0),
    "shaft_vib_alarm": 80.0,
    "shaft_vib_trip": 110.0,
    # Lube oil
    "lo_press_normal": (1.4, 1.8),
    "lo_press_alarm": 0.9,
    "lo_press_trip": 0.6,
    "lo_supply_temp": (42.0, 48.0),
    "lo_return_temp": (55.0, 62.0),
    "lo_temp_alarm": 68.0,
    # Seals (mechanical, API Plan 23)
    "seal_temp_normal": (40.0, 55.0),
    "seal_temp_alarm": 70.0,
    "seal_leak_normal": (0.5, 3.0),
    "seal_leak_alarm": 15.0,
    "seal_cw_flow_normal": (2.5, 4.5),
    # Axial displacement (mm)
    "axial_normal": (-0.15, 0.15),
    "axial_alarm": 0.30,
    "axial_trip": 0.50,
    # Recirc
    "recirc_setpoint_tph": 75.0,
}

# ===========================================================================
# TEMPORAL CONSTANTS
# ===========================================================================

START_DT = datetime(2024, 1, 1, 0, 0)
END_DT = datetime(2025, 1, 1, 0, 0)
TOTAL_MINUTES = int((END_DT - START_DT).total_seconds() / 60)  # 527040 (leap year)

# ===========================================================================
# PUMP SCHEDULE (which pump runs when)
# ===========================================================================
# Months 1-5:  BFP-A running, B standby
# June 1:      Planned swap to BFP-B (A offline for seal work)
# June-Aug:    BFP-B running, A standby
# Aug 20:      BFP-B trips (high bearing temp), auto-transfer to A
# Aug 20-31:   BFP-A running (emergency)
# Sep 1-14:    Planned outage (unit offline, both pumps stopped)
# Sep 15-Dec:  BFP-A running (repaired), B standby

SCHEDULE = [
    # (start_date, end_date, running_pump, mode)
    (datetime(2024, 1, 1), datetime(2024, 6, 1), "A", "normal"),
    (datetime(2024, 6, 1), datetime(2024, 8, 20), "B", "normal"),
    (datetime(2024, 8, 20), datetime(2024, 9, 1), "A", "emergency"),
    (datetime(2024, 9, 1), datetime(2024, 9, 15), None, "outage"),
    (datetime(2024, 9, 15), datetime(2025, 1, 1), "A", "normal"),
]


def get_schedule(ts):
    """Return (running_pump, mode) for a given timestamp."""
    for start, end, pump, mode in SCHEDULE:
        if start <= ts < end:
            return pump, mode
    return "A", "normal"


# ===========================================================================
# FAULT DEFINITIONS
# ===========================================================================
# Each fault has a start/end date, affected pump, affected tags, and a
# progression function that returns a multiplier/offset based on how far
# into the fault we are (0.0 = onset, 1.0 = fully developed).

FAULTS = [
    {
        "id": "SEAL-001",
        "name": "BFP-A DE seal degradation",
        "pump": "A",
        "start": datetime(2024, 4, 1),
        "end": datetime(2024, 6, 1),
        "description": "Gradual DE mechanical seal face wear",
    },
    {
        "id": "BRG-001",
        "name": "BFP-B NDE bearing wear",
        "pump": "B",
        "start": datetime(2024, 7, 15),
        "end": datetime(2024, 8, 20),
        "description": "Progressive NDE journal bearing babbitt wear",
    },
    {
        "id": "ALIGN-001",
        "name": "BFP-A coupling misalignment",
        "pump": "A",
        "start": datetime(2024, 10, 15),
        "end": datetime(2024, 12, 31),
        "description": "Post-outage thermal growth misalignment",
    },
]

# Transient events (specific timestamps)
TRANSIENT_EVENTS = [
    {"ts": datetime(2024, 3, 15, 14, 30), "type": "cavitation",
     "pump": "A", "duration_min": 8, "desc": "DA level dip during GT load swing"},
    {"ts": datetime(2024, 5, 22, 9, 15), "type": "cavitation",
     "pump": "A", "duration_min": 12, "desc": "Rapid GT ramp from 60% to 95%"},
    {"ts": datetime(2024, 7, 28, 16, 0), "type": "lo_cooler",
     "pump": "B", "duration_min": 45, "desc": "LO cooler CW supply temp spike"},
    {"ts": datetime(2024, 8, 5, 11, 30), "type": "recirc_hunting",
     "pump": "B", "duration_min": 90, "desc": "ARC valve positioner fault"},
    {"ts": datetime(2024, 8, 10, 15, 0), "type": "cavitation",
     "pump": "B", "duration_min": 6, "desc": "DA level transient"},
    {"ts": datetime(2024, 8, 15, 13, 45), "type": "lo_cooler",
     "pump": "B", "duration_min": 30, "desc": "High ambient CW temp"},
    {"ts": datetime(2024, 11, 3, 7, 0), "type": "cavitation",
     "pump": "A", "duration_min": 5, "desc": "Morning GT fast start"},
]


def fault_progression(fault, ts):
    """Return 0.0-1.0 progression through a fault window."""
    if ts < fault["start"] or ts >= fault["end"]:
        return 0.0
    elapsed = (ts - fault["start"]).total_seconds()
    total = (fault["end"] - fault["start"]).total_seconds()
    return min(1.0, elapsed / total)


def is_transient_active(event, ts):
    """Check if a transient event is active at timestamp ts."""
    event_end = event["ts"] + timedelta(minutes=event["duration_min"])
    return event["ts"] <= ts < event_end


def transient_intensity(event, ts):
    """Return 0.0-1.0 intensity of a transient event (ramps up then down)."""
    if not is_transient_active(event, ts):
        return 0.0
    elapsed = (ts - event["ts"]).total_seconds()
    duration = event["duration_min"] * 60
    frac = elapsed / duration
    # Bell curve: peak at 30% through event
    return math.exp(-((frac - 0.3) ** 2) / 0.08)


# ===========================================================================
# PHYSICS MODELS
# ===========================================================================

def diurnal_load_factor(hour_frac, dow):
    """
    Diurnal load shape matching the existing SP&L load_profiles pattern.
    Returns 0-1 multiplier on peak load.
    Identical logic to demo_data/generate_demo_data.py::_diurnal().
    """
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


def seasonal_factor(month):
    """Phoenix seasonal demand multiplier (summer peak)."""
    factors = {
        1: 0.70, 2: 0.65, 3: 0.60, 4: 0.62, 5: 0.75, 6: 0.92,
        7: 1.00, 8: 0.98, 9: 0.85, 10: 0.68, 11: 0.62, 12: 0.70,
    }
    return factors[month]


def ambient_temp_c(ts):
    """
    Ambient temperature model for Phoenix (degC).
    Matches existing weather_data generation pattern.
    """
    month = ts.month
    base_temps_f = {
        1: 55, 2: 58, 3: 65, 4: 75, 5: 85, 6: 100,
        7: 105, 8: 103, 9: 97, 10: 82, 11: 66, 12: 55,
    }
    base_f = base_temps_f[month] + 1.2  # 2024 offset (matches existing)
    hour = ts.hour + ts.minute / 60.0
    diurnal_f = 15 * math.sin(math.pi * (hour - 5) / 14) if 5 <= hour <= 19 else -8
    temp_f = base_f + diurnal_f + random.uniform(-3, 3)
    return round((temp_f - 32) * 5 / 9, 1)


def system_demand_mw(ts):
    """
    SP&L system demand in MW, correlated with existing load_profiles.
    System peak ~588 MW, uses same diurnal and seasonal patterns.
    """
    hour_frac = ts.hour + ts.minute / 60.0
    dow = ts.weekday()
    d = diurnal_load_factor(hour_frac, dow)
    s = seasonal_factor(ts.month)
    system_peak = 588.0
    noise = random.uniform(0.93, 1.07)
    return round(system_peak * d * s * noise, 1)


def unit_mw(system_mw, ambient_c):
    """
    Unit 1 MW output dispatched from system demand.
    Serves ~65% of SP&L load, capped at rated capacity.
    GT output derates in high ambient.
    """
    dispatch_frac = 0.65
    # GT ambient derate: ~0.5% per degC above 30C
    gt_derate = 1.0
    if ambient_c > 30:
        gt_derate = max(0.85, 1.0 - 0.005 * (ambient_c - 30))
    target = system_mw * dispatch_frac
    max_mw = PLANT["rated_mw"] * gt_derate
    return round(max(PLANT["min_load_mw"], min(target, max_mw)), 1)


def fw_flow_from_mw(mw):
    """
    Feedwater flow (t/hr) from unit MW.
    Approximately linear: 100 MW -> 90 t/hr, 300 MW -> 250 t/hr.
    """
    if mw <= 0:
        return 0.0
    mw_frac = (mw - PLANT["min_load_mw"]) / (PLANT["rated_mw"] - PLANT["min_load_mw"])
    mw_frac = max(0.0, min(1.0, mw_frac))
    flow_frac = 0.95 * mw_frac + 0.05 * mw_frac ** 1.3
    flow = 90.0 + flow_frac * (250.0 - 90.0)
    return round(flow, 1)


def pump_dp(flow_tph):
    """
    Pump differential pressure from H-Q curve.
    Shutoff: 180 bar, at BEP (260 t/hr): 153 bar, at rated (300): 145 bar.
    """
    if flow_tph <= 0:
        return BFP["shutoff_dp_bar"]
    b = (BFP["shutoff_dp_bar"] - 145.0) / (BFP["rated_flow_tph"] ** 2)
    dp = BFP["shutoff_dp_bar"] - b * flow_tph ** 2
    return round(max(130.0, dp), 1)


def pump_efficiency(flow_tph):
    """Pump efficiency (bell curve around BEP)."""
    if flow_tph <= 0:
        return 0.0
    bep = BFP["bep_flow_tph"]
    max_eff = BFP["bep_efficiency"]
    dev = (flow_tph - bep) / bep
    eff = max_eff * (1.0 - 1.2 * dev ** 2)
    return max(0.50, min(max_eff, eff))


def pump_power_kw(flow_tph, dp_bar):
    """Hydraulic power: P = Q * dP / (36 * eta), Q in t/hr, dP in bar."""
    if flow_tph <= 0 or dp_bar <= 0:
        return 0.0
    eff = pump_efficiency(flow_tph)
    return round(flow_tph * dp_bar / (36.0 * eff), 0)


def motor_current_a(power_kw):
    """Motor current from shaft power."""
    if power_kw <= 0:
        return 0.0
    elec_kw = power_kw / BFP["motor_efficiency"]
    current = elec_kw / (math.sqrt(3) * BFP["motor_voltage_kv"] * BFP["motor_pf"])
    return round(current, 1)


# ===========================================================================
# SENSOR MODELS (per-tag generation with noise)
# ===========================================================================

def _randn(mean, std):
    """Gaussian noise, rounded to 1 decimal."""
    return round(random.gauss(mean, std), 1)


def _randu(lo, hi):
    """Uniform noise, rounded to 1 decimal."""
    return round(random.uniform(lo, hi), 1)


def generate_pump_tags(pump_id, is_running, flow_tph, dp_bar, power_kw,
                       current_a, ambient_c, load_frac, faults_active,
                       transients_active):
    """
    Generate all analog tag values for one pump at one timestamp.
    Returns dict of tag_name -> value.
    """
    pfx = f"U1_BFP{pump_id}_"
    tags = {}

    if not is_running:
        # Standby state: everything at zero/ambient
        tags[pfx + "SUCT_PRESS"] = round(BFP["rated_suction_barg"] + _randn(0, 0.05), 2)
        tags[pfx + "DISCH_PRESS"] = round(BFP["rated_suction_barg"] + _randn(0, 0.05), 2)
        tags[pfx + "DIFF_PRESS"] = 0.0
        tags[pfx + "FW_FLOW"] = 0.0
        tags[pfx + "RECIRC_FLOW"] = 0.0
        tags[pfx + "SPEED"] = 0
        tags[pfx + "MTR_CURRENT"] = 0.0
        tags[pfx + "MTR_POWER"] = 0.0
        tags[pfx + "MTR_WINDING_TEMP"] = round(ambient_c + _randn(5, 1), 1)
        # Bearings at slightly above ambient (lube oil circulation)
        brg_base = ambient_c + 8.0
        tags[pfx + "BRG_DE_TEMP"] = round(brg_base + _randn(0, 0.5), 1)
        tags[pfx + "BRG_NDE_TEMP"] = round(brg_base + _randn(0, 0.5), 1)
        tags[pfx + "THR_ACT_TEMP"] = round(brg_base + _randn(0, 0.5), 1)
        tags[pfx + "THR_INACT_TEMP"] = round(brg_base + _randn(0, 0.5), 1)
        tags[pfx + "MTR_DE_BRG_TEMP"] = round(brg_base - 2 + _randn(0, 0.5), 1)
        tags[pfx + "MTR_NDE_BRG_TEMP"] = round(brg_base - 2 + _randn(0, 0.5), 1)
        # Vibration = 0
        for v in ["VIB_DE_X", "VIB_DE_Y", "VIB_NDE_X", "VIB_NDE_Y"]:
            tags[pfx + v] = 0.0
        tags[pfx + "AXIAL_DISP"] = 0.0
        # Lube oil (aux pump running)
        tags[pfx + "LO_HDR_PRESS"] = _randu(1.2, 1.4)
        tags[pfx + "LO_SUPPLY_TEMP"] = round(ambient_c + _randn(12, 1), 1)
        tags[pfx + "LO_RETURN_TEMP"] = round(ambient_c + _randn(15, 1), 1)
        tags[pfx + "LO_TANK_LVL"] = _randu(85, 92)
        tags[pfx + "LO_FILTER_DP"] = _randu(0.1, 0.2)
        # Seals (no flow, ambient)
        tags[pfx + "SEAL_DE_TEMP"] = round(ambient_c + _randn(3, 0.5), 1)
        tags[pfx + "SEAL_NDE_TEMP"] = round(ambient_c + _randn(3, 0.5), 1)
        tags[pfx + "SEAL_DE_LEAK"] = 0.0
        tags[pfx + "SEAL_NDE_LEAK"] = 0.0
        tags[pfx + "SEAL_CW_FLOW"] = _randu(1.0, 1.5)
        # Valves: suction open, discharge closed, recirc closed
        tags[pfx + "SUCT_VLV_POS"] = 100.0
        tags[pfx + "DISCH_VLV_POS"] = 0.0
        tags[pfx + "RECIRC_VLV_POS"] = 0.0
        tags[pfx + "STRAINER_DP"] = _randu(0.01, 0.03)
        # Status
        tags[pfx + "RUN_STATUS"] = 0
        tags[pfx + "TRIP"] = 0
        tags[pfx + "AUTO_MODE"] = 1
        return tags

    # ---- RUNNING STATE ----
    amb_offset = max(0, (ambient_c - 25) * 0.15)

    # Process
    suct_p = BFP["rated_suction_barg"] + _randn(0, 0.1)
    disch_p = suct_p + dp_bar + _randn(0, 0.3)
    tags[pfx + "SUCT_PRESS"] = round(suct_p, 2)
    tags[pfx + "DISCH_PRESS"] = round(disch_p, 2)
    tags[pfx + "DIFF_PRESS"] = round(disch_p - suct_p, 1)

    # Flow and recirc
    recirc_flow = 0.0
    if flow_tph < BFP["min_cont_flow_tph"]:
        recirc_flow = BFP["recirc_setpoint_tph"] - flow_tph
        total_pump_flow = BFP["recirc_setpoint_tph"]
    else:
        total_pump_flow = flow_tph
    tags[pfx + "FW_FLOW"] = round(flow_tph + _randn(0, 0.5), 1)
    tags[pfx + "RECIRC_FLOW"] = round(max(0, recirc_flow + _randn(0, 0.3)), 1)
    tags[pfx + "SPEED"] = BFP["rated_speed_rpm"]
    tags[pfx + "MTR_CURRENT"] = round(current_a + _randn(0, 1.0), 1)
    tags[pfx + "MTR_POWER"] = round(power_kw + _randn(0, 5), 0)
    tags[pfx + "MTR_WINDING_TEMP"] = round(80 + 30 * load_frac + amb_offset + _randn(0, 1), 1)

    # Bearings (base temp + load-dependent + ambient offset)
    de_base = 60 + 10 * load_frac
    nde_base = 58 + 10 * load_frac
    thr_act_base = 65 + 12 * load_frac
    thr_inact_base = 60 + 8 * load_frac
    mtr_de_base = 55 + 10 * load_frac
    mtr_nde_base = 53 + 10 * load_frac

    tags[pfx + "BRG_DE_TEMP"] = round(de_base + amb_offset + _randn(0, 0.4), 1)
    tags[pfx + "BRG_NDE_TEMP"] = round(nde_base + amb_offset + _randn(0, 0.4), 1)
    tags[pfx + "THR_ACT_TEMP"] = round(thr_act_base + amb_offset + _randn(0, 0.5), 1)
    tags[pfx + "THR_INACT_TEMP"] = round(thr_inact_base + amb_offset + _randn(0, 0.4), 1)
    tags[pfx + "MTR_DE_BRG_TEMP"] = round(mtr_de_base + amb_offset + _randn(0, 0.4), 1)
    tags[pfx + "MTR_NDE_BRG_TEMP"] = round(mtr_nde_base + amb_offset + _randn(0, 0.4), 1)

    # Vibration (1x unbalance + load dependence)
    vib_base = 25 + 10 * load_frac
    tags[pfx + "VIB_DE_X"] = round(max(5, vib_base + _randn(0, 1.5)), 1)
    tags[pfx + "VIB_DE_Y"] = round(max(5, vib_base + _randn(0, 1.5)), 1)
    tags[pfx + "VIB_NDE_X"] = round(max(5, vib_base - 2 + _randn(0, 1.5)), 1)
    tags[pfx + "VIB_NDE_Y"] = round(max(5, vib_base - 2 + _randn(0, 1.5)), 1)
    tags[pfx + "AXIAL_DISP"] = round(_randn(0.0, 0.03), 3)

    # Lube oil
    tags[pfx + "LO_HDR_PRESS"] = _randu(1.5, 1.7)
    lo_supply = 44 + amb_offset * 0.5
    tags[pfx + "LO_SUPPLY_TEMP"] = round(lo_supply + _randn(0, 0.5), 1)
    tags[pfx + "LO_RETURN_TEMP"] = round(lo_supply + 12 + 4 * load_frac + _randn(0, 0.5), 1)
    tags[pfx + "LO_TANK_LVL"] = _randu(82, 90)
    tags[pfx + "LO_FILTER_DP"] = _randu(0.15, 0.30)

    # Seals
    seal_base = 42 + 8 * load_frac + amb_offset * 0.3
    tags[pfx + "SEAL_DE_TEMP"] = round(seal_base + _randn(0, 0.5), 1)
    tags[pfx + "SEAL_NDE_TEMP"] = round(seal_base - 2 + _randn(0, 0.5), 1)
    tags[pfx + "SEAL_DE_LEAK"] = round(max(0.1, _randu(0.8, 2.5)), 1)
    tags[pfx + "SEAL_NDE_LEAK"] = round(max(0.1, _randu(0.6, 2.0)), 1)
    tags[pfx + "SEAL_CW_FLOW"] = _randu(3.0, 4.0)

    # Valves (running: suction open, discharge open, recirc depends on flow)
    tags[pfx + "SUCT_VLV_POS"] = 100.0
    tags[pfx + "DISCH_VLV_POS"] = 100.0
    recirc_pos = min(100, max(0, recirc_flow / BFP["recirc_setpoint_tph"] * 100))
    tags[pfx + "RECIRC_VLV_POS"] = round(recirc_pos, 1)
    tags[pfx + "STRAINER_DP"] = round(0.02 + 0.08 * (flow_tph / BFP["rated_flow_tph"]) + _randn(0, 0.005), 3)

    # Status
    tags[pfx + "RUN_STATUS"] = 1
    tags[pfx + "TRIP"] = 0
    tags[pfx + "AUTO_MODE"] = 1

    # ---- APPLY FAULT OVERLAYS ----
    for fault_id, progression in faults_active.items():
        if progression <= 0:
            continue
        fault = next((f for f in FAULTS if f["id"] == fault_id), None)
        if not fault or fault["pump"] != pump_id:
            continue

        if fault_id == "SEAL-001":
            # DE seal degradation: leak increases, seal temp rises
            leak_increase = progression * 12.0  # up to +12 cc/min
            temp_increase = progression * 8.0   # up to +8 degC
            tags[pfx + "SEAL_DE_LEAK"] += round(leak_increase, 1)
            tags[pfx + "SEAL_DE_TEMP"] += round(temp_increase, 1)

        elif fault_id == "BRG-001":
            # NDE bearing wear: temp rise, vibration 1x increase
            temp_rise = progression * 18.0       # up to +18 degC (toward alarm)
            vib_1x = progression * 35.0          # up to +35 um (toward alarm)
            sub_sync = progression * 8.0         # subsynchronous component
            tags[pfx + "BRG_NDE_TEMP"] += round(temp_rise, 1)
            tags[pfx + "VIB_NDE_X"] += round(vib_1x + _randn(0, sub_sync * 0.3), 1)
            tags[pfx + "VIB_NDE_Y"] += round(vib_1x * 0.8 + _randn(0, sub_sync * 0.3), 1)
            # Slight lube oil temp rise from friction
            tags[pfx + "LO_RETURN_TEMP"] += round(progression * 4.0, 1)

        elif fault_id == "ALIGN-001":
            # Coupling misalignment: 2x vibration component, both bearings affected
            vib_2x = progression * 25.0  # up to +25 um at 2x frequency
            tags[pfx + "VIB_DE_X"] += round(vib_2x + _randn(0, 2), 1)
            tags[pfx + "VIB_DE_Y"] += round(vib_2x * 0.9 + _randn(0, 2), 1)
            tags[pfx + "VIB_NDE_X"] += round(vib_2x * 0.7 + _randn(0, 2), 1)
            tags[pfx + "VIB_NDE_Y"] += round(vib_2x * 0.6 + _randn(0, 2), 1)
            # Coupling heating affects both motor NDE and pump DE
            tags[pfx + "MTR_NDE_BRG_TEMP"] += round(progression * 6.0, 1)
            tags[pfx + "BRG_DE_TEMP"] += round(progression * 4.0, 1)
            # Slight axial displacement shift
            tags[pfx + "AXIAL_DISP"] += round(progression * 0.12, 3)

    # ---- APPLY TRANSIENT OVERLAYS ----
    for event, intensity in transients_active:
        if intensity <= 0 or event["pump"] != pump_id:
            continue

        if event["type"] == "cavitation":
            # Suction pressure drops, vibration broadband spike, flow unstable
            tags[pfx + "SUCT_PRESS"] -= round(intensity * 2.5, 2)
            tags[pfx + "DIFF_PRESS"] -= round(intensity * 3.0, 1)
            for v in ["VIB_DE_X", "VIB_DE_Y", "VIB_NDE_X", "VIB_NDE_Y"]:
                tags[pfx + v] += round(intensity * 20 * random.uniform(0.5, 1.5), 1)
            tags[pfx + "FW_FLOW"] += round(intensity * _randn(0, 5), 1)

        elif event["type"] == "lo_cooler":
            # LO supply temp rises, bearing temps follow
            lo_rise = intensity * 12.0
            tags[pfx + "LO_SUPPLY_TEMP"] += round(lo_rise, 1)
            tags[pfx + "LO_RETURN_TEMP"] += round(lo_rise * 1.3, 1)
            tags[pfx + "BRG_DE_TEMP"] += round(lo_rise * 0.6, 1)
            tags[pfx + "BRG_NDE_TEMP"] += round(lo_rise * 0.6, 1)
            tags[pfx + "THR_ACT_TEMP"] += round(lo_rise * 0.5, 1)

        elif event["type"] == "recirc_hunting":
            # Recirc valve oscillates, flow unstable
            osc = intensity * 30 * math.sin(random.uniform(0, 2 * math.pi))
            tags[pfx + "RECIRC_VLV_POS"] = round(max(0, min(100,
                tags[pfx + "RECIRC_VLV_POS"] + osc)), 1)
            tags[pfx + "RECIRC_FLOW"] += round(intensity * _randn(0, 10), 1)
            tags[pfx + "FW_FLOW"] += round(intensity * _randn(0, 3), 1)

    return tags


def generate_stopped_tags(pump_id, ambient_c):
    """Generate tags for a pump during planned outage (completely stopped)."""
    pfx = f"U1_BFP{pump_id}_"
    tags = {}
    tags[pfx + "SUCT_PRESS"] = 0.0
    tags[pfx + "DISCH_PRESS"] = 0.0
    tags[pfx + "DIFF_PRESS"] = 0.0
    tags[pfx + "FW_FLOW"] = 0.0
    tags[pfx + "RECIRC_FLOW"] = 0.0
    tags[pfx + "SPEED"] = 0
    tags[pfx + "MTR_CURRENT"] = 0.0
    tags[pfx + "MTR_POWER"] = 0.0
    tags[pfx + "MTR_WINDING_TEMP"] = round(ambient_c + _randn(2, 0.5), 1)
    for brg in ["BRG_DE_TEMP", "BRG_NDE_TEMP", "THR_ACT_TEMP", "THR_INACT_TEMP",
                 "MTR_DE_BRG_TEMP", "MTR_NDE_BRG_TEMP"]:
        tags[pfx + brg] = round(ambient_c + _randn(2, 0.5), 1)
    for v in ["VIB_DE_X", "VIB_DE_Y", "VIB_NDE_X", "VIB_NDE_Y"]:
        tags[pfx + v] = 0.0
    tags[pfx + "AXIAL_DISP"] = 0.0
    tags[pfx + "LO_HDR_PRESS"] = 0.0
    tags[pfx + "LO_SUPPLY_TEMP"] = round(ambient_c + _randn(1, 0.3), 1)
    tags[pfx + "LO_RETURN_TEMP"] = round(ambient_c + _randn(1, 0.3), 1)
    tags[pfx + "LO_TANK_LVL"] = _randu(88, 93)
    tags[pfx + "LO_FILTER_DP"] = 0.0
    tags[pfx + "SEAL_DE_TEMP"] = round(ambient_c + _randn(1, 0.3), 1)
    tags[pfx + "SEAL_NDE_TEMP"] = round(ambient_c + _randn(1, 0.3), 1)
    tags[pfx + "SEAL_DE_LEAK"] = 0.0
    tags[pfx + "SEAL_NDE_LEAK"] = 0.0
    tags[pfx + "SEAL_CW_FLOW"] = 0.0
    tags[pfx + "SUCT_VLV_POS"] = 0.0
    tags[pfx + "DISCH_VLV_POS"] = 0.0
    tags[pfx + "RECIRC_VLV_POS"] = 0.0
    tags[pfx + "STRAINER_DP"] = 0.0
    tags[pfx + "RUN_STATUS"] = 0
    tags[pfx + "TRIP"] = 0
    tags[pfx + "AUTO_MODE"] = 0
    return tags


# ===========================================================================
# SYSTEM TAG GENERATION
# ===========================================================================

def generate_system_tags(ts, unit_mw_val, fw_flow_val, dp_val, ambient_c):
    """Generate shared/system-level tags."""
    tags = {}
    if unit_mw_val <= 0:
        # Unit offline
        tags["U1_FW_HDR_PRESS"] = 0.0
        tags["U1_FW_HDR_TEMP"] = round(ambient_c + _randn(5, 1), 1)
        tags["U1_FW_HDR_FLOW"] = 0.0
        tags["U1_UNIT_MW_GROSS"] = 0.0
        tags["U1_UNIT_MW_NET"] = 0.0
        tags["U1_GT_A_LOAD"] = 0.0
        tags["U1_GT_B_LOAD"] = 0.0
        tags["U1_ST_LOAD"] = 0.0
    else:
        disch_p = BFP["rated_suction_barg"] + dp_val
        tags["U1_FW_HDR_PRESS"] = round(disch_p - _randu(1, 3), 1)
        # FW temp rises with load (more extraction heating)
        fw_temp = 160 + 30 * (unit_mw_val / PLANT["rated_mw"])
        tags["U1_FW_HDR_TEMP"] = round(fw_temp + _randn(0, 1), 1)
        tags["U1_FW_HDR_FLOW"] = round(fw_flow_val + _randn(0, 0.5), 1)
        tags["U1_UNIT_MW_GROSS"] = round(unit_mw_val + _randn(0, 0.5), 1)
        parasitic = 8 + 4 * (unit_mw_val / PLANT["rated_mw"])
        tags["U1_UNIT_MW_NET"] = round(unit_mw_val - parasitic + _randn(0, 0.3), 1)
        # Split GT/ST load (GTs share equally, ST gets remainder)
        gt_total = unit_mw_val * 0.67
        gt_each = gt_total / 2
        st_load = unit_mw_val - gt_total
        tags["U1_GT_A_LOAD"] = round(gt_each + _randn(0, 0.3), 1)
        tags["U1_GT_B_LOAD"] = round(gt_each + _randn(0, 0.3), 1)
        tags["U1_ST_LOAD"] = round(st_load + _randn(0, 0.3), 1)

    # Boundary values (always present)
    da_p = PLANT["da_pressure_barg"]
    tags["U1_DA_PRESS"] = round(da_p + _randn(0, 0.1), 2)
    tags["U1_DA_TEMP"] = round(PLANT["da_temperature_c"] + _randn(0, 0.3), 1)
    tags["U1_DA_LEVEL"] = _randu(48, 55) if unit_mw_val > 0 else _randu(30, 35)
    tags["U1_AMBIENT_TEMP"] = round(ambient_c, 1)
    # Cooling water tracks ambient with ~5C approach
    tags["U1_CW_SUPPLY_TEMP"] = round(ambient_c - 5 + _randn(0, 1), 1)

    return tags


# ===========================================================================
# EVENT LOG GENERATION
# ===========================================================================

def generate_event_logs(all_rows):
    """
    Scan generated data for alarm/trip conditions and create event logs.
    Also generates operator action log from schedule changes.
    """
    alarms = []
    trips = []
    operators = []

    # Operator actions from schedule
    operators.append(["2024-01-01 00:00", "U1-BFPA", "START", "Unit startup, BFP-A to duty"])
    operators.append(["2024-06-01 06:00", "U1-BFPB", "START", "Planned swap: start BFP-B"])
    operators.append(["2024-06-01 06:05", "U1-BFPA", "STOP", "Planned swap: stop BFP-A for seal work"])
    operators.append(["2024-08-20 13:45", "U1-BFPA", "START", "Emergency start BFP-A (B trip)"])
    operators.append(["2024-09-01 00:00", "U1", "UNIT_SHUTDOWN", "Planned outage begins"])
    operators.append(["2024-09-15 06:00", "U1-BFPA", "START", "Post-outage startup, BFP-A to duty"])
    operators.append(["2024-09-15 06:00", "U1", "UNIT_START", "Post-outage unit restart"])

    # BFP-B trip event
    trips.append([
        "2024-08-20 13:45", "U1-BFPB", "HIGH_BRG_TEMP",
        "NDE journal bearing temperature exceeded trip setpoint (95 degC)",
        "BRG_NDE_TEMP", "96.2",
    ])

    # Scan data for alarm conditions (sample every 15 min to keep log manageable)
    alarm_checks = {
        "BRG_DE_TEMP": ("HIGH_BRG_TEMP", BFP["journal_alarm"]),
        "BRG_NDE_TEMP": ("HIGH_BRG_TEMP", BFP["journal_alarm"]),
        "THR_ACT_TEMP": ("HIGH_THR_BRG_TEMP", BFP["thrust_alarm"]),
        "SEAL_DE_LEAK": ("HIGH_SEAL_LEAK", BFP["seal_leak_alarm"]),
        "SEAL_NDE_LEAK": ("HIGH_SEAL_LEAK", BFP["seal_leak_alarm"]),
        "VIB_DE_X": ("HIGH_VIBRATION", BFP["shaft_vib_alarm"]),
        "VIB_NDE_X": ("HIGH_VIBRATION", BFP["shaft_vib_alarm"]),
        "LO_SUPPLY_TEMP": ("HIGH_LO_TEMP", BFP["lo_temp_alarm"]),
        "SEAL_DE_TEMP": ("HIGH_SEAL_TEMP", BFP["seal_temp_alarm"]),
    }

    prev_alarm_state = {}
    for i, row in enumerate(all_rows):
        if i % 15 != 0:
            continue
        ts_str = row["timestamp"]
        for pump_id in ["A", "B"]:
            pfx = f"U1_BFP{pump_id}_"
            for tag_suffix, (alarm_code, threshold) in alarm_checks.items():
                tag = pfx + tag_suffix
                val = row.get(tag, 0)
                key = (pump_id, tag_suffix)
                was_alarming = prev_alarm_state.get(key, False)
                is_alarming = val > threshold
                if is_alarming and not was_alarming:
                    alarms.append([ts_str, f"U1-BFP{pump_id}", alarm_code,
                                   f"{tag_suffix} = {val} > {threshold}", "ACTIVE"])
                elif not is_alarming and was_alarming:
                    alarms.append([ts_str, f"U1-BFP{pump_id}", alarm_code,
                                   f"{tag_suffix} = {val} returned below {threshold}", "CLEARED"])
                prev_alarm_state[key] = is_alarming

    return alarms, trips, operators


# ===========================================================================
# REFERENCE DATA GENERATION
# ===========================================================================

def write_tag_dictionary():
    """Write the complete tag dictionary CSV."""
    print("  Writing tag_dictionary.csv...")
    headers = ["tag_id", "description", "units", "range_min", "range_max",
               "scan_rate_sec", "pump"]
    rows = []
    per_pump_tags = [
        ("SUCT_PRESS", "Suction pressure", "bar(g)", 0, 15, 1),
        ("DISCH_PRESS", "Discharge pressure", "bar(g)", 0, 200, 1),
        ("DIFF_PRESS", "Differential pressure", "bar", 0, 185, 1),
        ("FW_FLOW", "Feedwater flow", "t/hr", 0, 350, 1),
        ("RECIRC_FLOW", "Recirculation flow", "t/hr", 0, 100, 1),
        ("SPEED", "Pump speed", "RPM", 0, 3600, 1),
        ("MTR_CURRENT", "Motor current", "A", 0, 250, 1),
        ("MTR_POWER", "Motor power", "kW", 0, 2000, 1),
        ("MTR_WINDING_TEMP", "Motor winding temperature", "degC", 0, 180, 5),
        ("BRG_DE_TEMP", "Pump DE journal bearing temp", "degC", 0, 120, 5),
        ("BRG_NDE_TEMP", "Pump NDE journal bearing temp", "degC", 0, 120, 5),
        ("THR_ACT_TEMP", "Thrust bearing active side temp", "degC", 0, 120, 5),
        ("THR_INACT_TEMP", "Thrust bearing inactive side temp", "degC", 0, 120, 5),
        ("MTR_DE_BRG_TEMP", "Motor DE bearing temp", "degC", 0, 120, 5),
        ("MTR_NDE_BRG_TEMP", "Motor NDE bearing temp", "degC", 0, 120, 5),
        ("VIB_DE_X", "Shaft vibration DE X-probe", "um_pk-pk", 0, 150, 1),
        ("VIB_DE_Y", "Shaft vibration DE Y-probe", "um_pk-pk", 0, 150, 1),
        ("VIB_NDE_X", "Shaft vibration NDE X-probe", "um_pk-pk", 0, 150, 1),
        ("VIB_NDE_Y", "Shaft vibration NDE Y-probe", "um_pk-pk", 0, 150, 1),
        ("AXIAL_DISP", "Axial displacement", "mm", -1.0, 1.0, 1),
        ("LO_HDR_PRESS", "Lube oil header pressure", "bar(g)", 0, 3.0, 5),
        ("LO_SUPPLY_TEMP", "Lube oil supply temperature", "degC", 0, 100, 5),
        ("LO_RETURN_TEMP", "Lube oil return temperature", "degC", 0, 100, 5),
        ("LO_TANK_LVL", "Lube oil tank level", "%", 0, 100, 5),
        ("LO_FILTER_DP", "Lube oil filter diff pressure", "bar", 0, 2.0, 5),
        ("SEAL_DE_TEMP", "DE seal chamber temperature", "degC", 0, 100, 5),
        ("SEAL_NDE_TEMP", "NDE seal chamber temperature", "degC", 0, 100, 5),
        ("SEAL_DE_LEAK", "DE seal leakage", "cc/min", 0, 50, 5),
        ("SEAL_NDE_LEAK", "NDE seal leakage", "cc/min", 0, 50, 5),
        ("SEAL_CW_FLOW", "Seal cooling water flow", "L/min", 0, 10, 5),
        ("SUCT_VLV_POS", "Suction valve position", "%", 0, 100, 5),
        ("DISCH_VLV_POS", "Discharge valve position", "%", 0, 100, 5),
        ("RECIRC_VLV_POS", "Recirc valve position", "%", 0, 100, 5),
        ("STRAINER_DP", "Suction strainer diff pressure", "bar", 0, 1.0, 5),
        ("RUN_STATUS", "Running status", "bool", 0, 1, 0),
        ("TRIP", "Trip signal", "bool", 0, 1, 0),
        ("AUTO_MODE", "Auto/manual mode", "bool", 0, 1, 0),
    ]
    for pump in ["A", "B"]:
        for tag, desc, units, rmin, rmax, scan in per_pump_tags:
            rows.append([f"U1_BFP{pump}_{tag}", f"BFP-{pump} {desc}",
                         units, rmin, rmax, scan, pump])

    sys_tags = [
        ("U1_FW_HDR_PRESS", "FW header pressure", "bar(g)", 0, 200, 1, "SYS"),
        ("U1_FW_HDR_TEMP", "FW header temperature", "degC", 0, 300, 5, "SYS"),
        ("U1_FW_HDR_FLOW", "FW total flow to HRSG", "t/hr", 0, 350, 1, "SYS"),
        ("U1_UNIT_MW_GROSS", "Unit gross MW output", "MW", 0, 350, 1, "SYS"),
        ("U1_UNIT_MW_NET", "Unit net MW output", "MW", 0, 320, 1, "SYS"),
        ("U1_GT_A_LOAD", "Gas turbine A load", "MW", 0, 120, 1, "SYS"),
        ("U1_GT_B_LOAD", "Gas turbine B load", "MW", 0, 120, 1, "SYS"),
        ("U1_ST_LOAD", "Steam turbine load", "MW", 0, 120, 1, "SYS"),
        ("U1_DA_PRESS", "Deaerator pressure (boundary)", "bar(g)", 0, 15, 5, "SYS"),
        ("U1_DA_TEMP", "Deaerator temperature (boundary)", "degC", 0, 200, 5, "SYS"),
        ("U1_DA_LEVEL", "Deaerator level (boundary)", "%", 0, 100, 5, "SYS"),
        ("U1_AMBIENT_TEMP", "Ambient temperature", "degC", -10, 55, 60, "SYS"),
        ("U1_CW_SUPPLY_TEMP", "Cooling water supply temp", "degC", 0, 45, 60, "SYS"),
    ]
    for tag, desc, units, rmin, rmax, scan, pump in sys_tags:
        rows.append([tag, desc, units, rmin, rmax, scan, pump])

    path = os.path.join(OUTPUT_DIR, "tag_dictionary.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def write_equipment_registry():
    """Write equipment metadata CSV."""
    print("  Writing equipment_registry.csv...")
    headers = ["equipment_id", "name", "type", "oem", "model", "serial",
               "install_year", "rated_power_kw", "rated_speed_rpm",
               "rated_flow_tph", "rated_dp_bar", "parent_system"]
    rows = [
        ["U1-BFPA", "HP BFP Pump A", "barrel-casing multistage pump",
         "KSB", "CHTD 8/6", "KSB-2019-44821", 2019, "", BFP["rated_speed_rpm"],
         BFP["rated_flow_tph"], BFP["rated_dp_bar"], "U1-FW"],
        ["U1-BFPA-MTR", "BFP A Drive Motor", "squirrel-cage induction motor",
         "ABB", "AXR 500MK4", "ABB-2019-77231", 2019, BFP["motor_rated_kw"],
         BFP["rated_speed_rpm"], "", "", "U1-BFPA"],
        ["U1-BFPA-LO", "BFP A Lube Oil System", "forced-feed lube oil skid",
         "Bijur Delimon", "FLM-2200", "BD-2019-1105", 2019, "", "", "", "", "U1-BFPA"],
        ["U1-BFPB", "HP BFP Pump B", "barrel-casing multistage pump",
         "KSB", "CHTD 8/6", "KSB-2019-44822", 2019, "", BFP["rated_speed_rpm"],
         BFP["rated_flow_tph"], BFP["rated_dp_bar"], "U1-FW"],
        ["U1-BFPB-MTR", "BFP B Drive Motor", "squirrel-cage induction motor",
         "ABB", "AXR 500MK4", "ABB-2019-77232", 2019, BFP["motor_rated_kw"],
         BFP["rated_speed_rpm"], "", "", "U1-BFPB"],
        ["U1-BFPB-LO", "BFP B Lube Oil System", "forced-feed lube oil skid",
         "Bijur Delimon", "FLM-2200", "BD-2019-1106", 2019, "", "", "", "", "U1-BFPB"],
    ]
    path = os.path.join(OUTPUT_DIR, "equipment_registry.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def write_pump_curves():
    """Write OEM pump performance curves."""
    print("  Writing pump_curves.csv...")
    headers = ["flow_tph", "flow_pct_bep", "head_bar", "efficiency_pct", "power_kw",
               "npsh_required_m"]
    rows = []
    for flow_pct in range(0, 131, 5):
        flow = BFP["bep_flow_tph"] * flow_pct / 100
        dp = pump_dp(flow)
        eff = pump_efficiency(flow) if flow > 0 else 0
        pwr = pump_power_kw(flow, dp) if flow > 0 else 0
        # NPSH increases with flow squared
        npsh = 8 + 15 * (flow / BFP["rated_flow_tph"]) ** 2
        rows.append([round(flow, 0), flow_pct, round(dp, 1),
                     round(eff * 100, 1), round(pwr, 0), round(npsh, 1)])
    path = os.path.join(OUTPUT_DIR, "reference", "pump_curves.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def write_heat_balance():
    """Write unit load vs FW system parameters."""
    print("  Writing heat_balance.csv...")
    headers = ["unit_mw", "unit_pct", "fw_flow_tph", "fw_temp_c",
               "bfp_dp_bar", "bfp_power_kw", "hp_drum_press_barg"]
    rows = []
    for pct in range(30, 105, 5):
        mw = PLANT["rated_mw"] * pct / 100
        flow = fw_flow_from_mw(mw)
        dp = pump_dp(flow)
        pwr = pump_power_kw(flow, dp)
        fw_temp = 160 + 30 * (mw / PLANT["rated_mw"])
        drum_p = PLANT["hp_drum_pressure_barg"] * (0.85 + 0.15 * pct / 100)
        rows.append([round(mw, 0), pct, round(flow, 1), round(fw_temp, 1),
                     round(dp, 1), round(pwr, 0), round(drum_p, 1)])
    path = os.path.join(OUTPUT_DIR, "reference", "heat_balance.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)


def write_design_parameters():
    """Write design parameters JSON."""
    print("  Writing design_parameters.json...")
    params = {
        "plant": PLANT,
        "bfp": {k: v for k, v in BFP.items()},
        "alarm_setpoints": {
            "journal_bearing_high_alarm_degc": BFP["journal_alarm"],
            "journal_bearing_high_trip_degc": BFP["journal_trip"],
            "thrust_bearing_high_alarm_degc": BFP["thrust_alarm"],
            "thrust_bearing_high_trip_degc": BFP["thrust_trip"],
            "motor_bearing_high_alarm_degc": BFP["motor_brg_alarm"],
            "motor_bearing_high_trip_degc": BFP["motor_brg_trip"],
            "shaft_vibration_high_alarm_um": BFP["shaft_vib_alarm"],
            "shaft_vibration_high_trip_um": BFP["shaft_vib_trip"],
            "lo_pressure_low_alarm_barg": BFP["lo_press_alarm"],
            "lo_pressure_low_trip_barg": BFP["lo_press_trip"],
            "lo_temperature_high_alarm_degc": BFP["lo_temp_alarm"],
            "seal_leakage_high_alarm_ccmin": BFP["seal_leak_alarm"],
            "seal_temperature_high_alarm_degc": BFP["seal_temp_alarm"],
            "axial_displacement_high_alarm_mm": BFP["axial_alarm"],
            "axial_displacement_high_trip_mm": BFP["axial_trip"],
        },
        "fault_scenarios_embedded": [
            {"id": f["id"], "name": f["name"], "pump": f["pump"],
             "start": f["start"].isoformat(), "end": f["end"].isoformat(),
             "description": f["description"]}
            for f in FAULTS
        ],
    }
    path = os.path.join(OUTPUT_DIR, "reference", "design_parameters.json")
    with open(path, "w") as f:
        json.dump(params, f, indent=2, default=str)


# ===========================================================================
# MAIN GENERATION LOOP
# ===========================================================================

def generate_timeseries():
    """Generate 1-minute time-series data for the full year."""
    print("Generating BFP train time-series (1-min, 2024)...")
    print(f"  {TOTAL_MINUTES:,} minutes to generate...")

    all_rows = []
    trip_b_applied = False

    for minute_idx in range(TOTAL_MINUTES):
        ts = START_DT + timedelta(minutes=minute_idx)
        running_pump, mode = get_schedule(ts)
        amb_c = ambient_temp_c(ts)

        # Progress reporting
        if minute_idx % 100000 == 0 and minute_idx > 0:
            print(f"    {minute_idx:,} / {TOTAL_MINUTES:,} minutes...")

        row = {"timestamp": ts.strftime("%Y-%m-%d %H:%M")}

        if mode == "outage":
            # Both pumps stopped, unit offline
            row.update(generate_stopped_tags("A", amb_c))
            row.update(generate_stopped_tags("B", amb_c))
            row.update(generate_system_tags(ts, 0, 0, 0, amb_c))
            all_rows.append(row)
            continue

        # Compute unit dispatch
        sys_demand = system_demand_mw(ts)
        u_mw = unit_mw(sys_demand, amb_c)
        flow = fw_flow_from_mw(u_mw)
        dp = pump_dp(flow)
        pwr = pump_power_kw(flow, dp)
        cur = motor_current_a(pwr)
        load_frac = max(0, min(1, (u_mw - PLANT["min_load_mw"]) /
                                  (PLANT["rated_mw"] - PLANT["min_load_mw"])))

        # Compute fault progressions
        faults_active = {}
        for fault in FAULTS:
            prog = fault_progression(fault, ts)
            if prog > 0:
                faults_active[fault["id"]] = prog

        # Compute transient intensities
        transients_active = []
        for event in TRANSIENT_EVENTS:
            intensity = transient_intensity(event, ts)
            if intensity > 0:
                transients_active.append((event, intensity))

        # Check for BFP-B trip at the specific minute
        if (not trip_b_applied and running_pump == "B" and
                ts >= datetime(2024, 8, 20, 13, 45)):
            # Trip happens this minute: B trips, A starts
            trip_b_applied = True

        # Generate tags for both pumps
        for pump_id in ["A", "B"]:
            is_running = (pump_id == running_pump)
            if is_running:
                row.update(generate_pump_tags(
                    pump_id, True, flow, dp, pwr, cur, amb_c, load_frac,
                    faults_active, transients_active))
            else:
                row.update(generate_pump_tags(
                    pump_id, False, 0, 0, 0, 0, amb_c, 0,
                    {}, []))

        # System tags
        row.update(generate_system_tags(ts, u_mw, flow, dp, amb_c))
        all_rows.append(row)

    print(f"  Generated {len(all_rows):,} rows")
    return all_rows


# ===========================================================================
# OUTPUT
# ===========================================================================

def write_parquet(all_rows):
    """Write 1-min, 15-min, and hourly parquet files."""
    print("Writing parquet files...")
    df = pd.DataFrame(all_rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 1-minute
    path_1m = os.path.join(OUTPUT_DIR, "timeseries", "bfp_train_1min.parquet")
    df.to_parquet(path_1m, index=False, engine="pyarrow")
    print(f"  wrote {len(df):,} rows -> bfp_train_1min.parquet")

    # 15-minute rollup (mean of numeric columns)
    df_15m = df.set_index("timestamp").resample("15min").mean(numeric_only=True).reset_index()
    # Round to reasonable precision
    for col in df_15m.columns:
        if col != "timestamp" and df_15m[col].dtype in ["float64", "float32"]:
            df_15m[col] = df_15m[col].round(2)
    path_15m = os.path.join(OUTPUT_DIR, "timeseries", "bfp_train_15min.parquet")
    df_15m.to_parquet(path_15m, index=False, engine="pyarrow")
    print(f"  wrote {len(df_15m):,} rows -> bfp_train_15min.parquet")

    # Hourly rollup
    df_1h = df.set_index("timestamp").resample("1h").mean(numeric_only=True).reset_index()
    for col in df_1h.columns:
        if col != "timestamp" and df_1h[col].dtype in ["float64", "float32"]:
            df_1h[col] = df_1h[col].round(2)
    path_1h = os.path.join(OUTPUT_DIR, "timeseries", "bfp_train_hourly.parquet")
    df_1h.to_parquet(path_1h, index=False, engine="pyarrow")
    print(f"  wrote {len(df_1h):,} rows -> bfp_train_hourly.parquet")

    return df


def write_event_csvs(alarms, trips, operators):
    """Write event log CSV files."""
    print("Writing event logs...")

    path = os.path.join(OUTPUT_DIR, "events", "alarm_log.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "equipment", "alarm_code", "message", "state"])
        w.writerows(alarms)
    print(f"  wrote {len(alarms):,} rows -> alarm_log.csv")

    path = os.path.join(OUTPUT_DIR, "events", "trip_log.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "equipment", "trip_code", "description",
                     "trigger_tag", "trigger_value"])
        w.writerows(trips)
    print(f"  wrote {len(trips):,} rows -> trip_log.csv")

    path = os.path.join(OUTPUT_DIR, "events", "operator_actions.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "equipment", "action", "description"])
        w.writerows(operators)
    print(f"  wrote {len(operators):,} rows -> operator_actions.csv")


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main():
    print("=" * 70)
    print("SP&L Unit 1 - BFP Train Synthetic Data Generator")
    print("=" * 70)
    print(f"Plant: {PLANT['name']} ({PLANT['type']}, {PLANT['rated_mw']} MW)")
    print(f"Period: {START_DT.date()} to {END_DT.date()}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    # Ensure output directories exist
    for subdir in ["timeseries", "events", "reference"]:
        os.makedirs(os.path.join(OUTPUT_DIR, subdir), exist_ok=True)

    # Generate reference data
    print("Generating reference data...")
    write_tag_dictionary()
    write_equipment_registry()
    write_pump_curves()
    write_heat_balance()
    write_design_parameters()
    print()

    # Generate time-series
    all_rows = generate_timeseries()
    print()

    # Write parquet files
    write_parquet(all_rows)
    print()

    # Generate and write event logs
    alarms, trips, operators = generate_event_logs(all_rows)
    write_event_csvs(alarms, trips, operators)
    print()

    print("=" * 70)
    print("Generation complete!")
    print(f"  Time-series: {len(all_rows):,} rows x {len(all_rows[0]):,} columns")
    print(f"  Alarms: {len(alarms):,}")
    print(f"  Trips: {len(trips):,}")
    print(f"  Operator actions: {len(operators):,}")
    print("=" * 70)


if __name__ == "__main__":
    main()
