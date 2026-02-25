#!/usr/bin/env python3
"""Comprehensive validation of BFP train data in sisyphean-power-and-light/generation/."""

import sys
import os

import pandas as pd
import numpy as np

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "sisyphean-power-and-light", "generation")
TS_DIR = os.path.join(BASE_DIR, "timeseries")
EV_DIR = os.path.join(BASE_DIR, "events")
REF_DIR = os.path.join(BASE_DIR, "reference")


class Report:
    def __init__(self):
        self.results = []

    def ok(self, cat, check, detail=""):
        self.results.append((cat, check, "PASS", detail))

    def fail(self, cat, check, detail=""):
        self.results.append((cat, check, "FAIL", detail))

    def warn(self, cat, check, detail=""):
        self.results.append((cat, check, "WARN", detail))

    def summary(self):
        cats = {}
        for cat, check, status, detail in self.results:
            cats.setdefault(cat, []).append((check, status, detail))
        for cat in cats:
            print(f"\n{'='*70}")
            print(f"  {cat}")
            print(f"{'='*70}")
            for check, status, detail in cats[cat]:
                tag = {"PASS": "PASS", "FAIL": "FAIL", "WARN": "WARN"}[status]
                line = f"  [{tag}] {check}"
                if detail:
                    line += f" -- {detail}"
                print(line)
        p = sum(1 for _, _, s, _ in self.results if s == "PASS")
        f = sum(1 for _, _, s, _ in self.results if s == "FAIL")
        w = sum(1 for _, _, s, _ in self.results if s == "WARN")
        print(f"\n{'='*70}")
        print(f"  TOTAL: {p} PASS | {f} FAIL | {w} WARN")
        print(f"{'='*70}\n")
        return f


def main():
    r = Report()

    # ==================================================================
    # 1. File Existence
    # ==================================================================
    C = "1. File Existence"
    expected_files = {
        "timeseries/bfp_train_1min.parquet": os.path.join(TS_DIR, "bfp_train_1min.parquet"),
        "timeseries/bfp_train_15min.parquet": os.path.join(TS_DIR, "bfp_train_15min.parquet"),
        "timeseries/bfp_train_hourly.parquet": os.path.join(TS_DIR, "bfp_train_hourly.parquet"),
        "events/alarm_log.csv": os.path.join(EV_DIR, "alarm_log.csv"),
        "events/trip_log.csv": os.path.join(EV_DIR, "trip_log.csv"),
        "events/operator_actions.csv": os.path.join(EV_DIR, "operator_actions.csv"),
        "reference/design_parameters.json": os.path.join(REF_DIR, "design_parameters.json"),
        "reference/heat_balance.csv": os.path.join(REF_DIR, "heat_balance.csv"),
        "reference/pump_curves.csv": os.path.join(REF_DIR, "pump_curves.csv"),
        "equipment_registry.csv": os.path.join(BASE_DIR, "equipment_registry.csv"),
        "tag_dictionary.csv": os.path.join(BASE_DIR, "tag_dictionary.csv"),
    }
    all_exist = True
    for label, path in expected_files.items():
        if os.path.isfile(path):
            r.ok(C, f"{label} exists")
        else:
            r.fail(C, f"{label} MISSING")
            all_exist = False

    if not all_exist:
        r.summary()
        print("Aborting: required files missing.")
        sys.exit(1)

    # Load data
    print("Loading datasets...")
    df_1min = pd.read_parquet(os.path.join(TS_DIR, "bfp_train_1min.parquet"))
    df_15min = pd.read_parquet(os.path.join(TS_DIR, "bfp_train_15min.parquet"))
    df_hourly = pd.read_parquet(os.path.join(TS_DIR, "bfp_train_hourly.parquet"))
    alarm_log = pd.read_csv(os.path.join(EV_DIR, "alarm_log.csv"))
    trip_log = pd.read_csv(os.path.join(EV_DIR, "trip_log.csv"))
    operator_actions = pd.read_csv(os.path.join(EV_DIR, "operator_actions.csv"))
    equipment_registry = pd.read_csv(os.path.join(BASE_DIR, "equipment_registry.csv"))
    tag_dictionary = pd.read_csv(os.path.join(BASE_DIR, "tag_dictionary.csv"))

    # Ensure timestamp columns are datetime
    for df in [df_1min, df_15min, df_hourly]:
        df["timestamp"] = pd.to_datetime(df["timestamp"])

    # ==================================================================
    # 2. Row Counts and Column Counts
    # ==================================================================
    C = "2. Row Counts"
    for name, df, expected_rows in [
        ("bfp_train_1min.parquet", df_1min, 527040),
        ("bfp_train_15min.parquet", df_15min, 35136),
        ("bfp_train_hourly.parquet", df_hourly, 8784),
    ]:
        actual_rows = len(df)
        if actual_rows == expected_rows:
            r.ok(C, f"{name}: {actual_rows} rows")
        else:
            r.fail(C, f"{name}: expected {expected_rows}, got {actual_rows}")

    # Column counts (all should have 88 columns)
    for name, df in [
        ("bfp_train_1min.parquet", df_1min),
        ("bfp_train_15min.parquet", df_15min),
        ("bfp_train_hourly.parquet", df_hourly),
    ]:
        actual_cols = len(df.columns)
        if actual_cols == 88:
            r.ok(C, f"{name}: {actual_cols} columns")
        else:
            r.fail(C, f"{name}: expected 88 columns, got {actual_cols}")

    # ==================================================================
    # 3. Timestamp Continuity
    # ==================================================================
    C = "3. Timestamp Continuity"
    ts_1min = df_1min["timestamp"].sort_values().reset_index(drop=True)
    gaps = ts_1min.diff().dropna()
    expected_gap = pd.Timedelta(minutes=1)
    bad_gaps = gaps[gaps != expected_gap]
    if len(bad_gaps) == 0:
        r.ok(C, f"1-min data: no gaps ({ts_1min.iloc[0]} to {ts_1min.iloc[-1]})")
    else:
        r.fail(C, f"1-min data: {len(bad_gaps)} timestamp gaps found",
               f"first gap at index {bad_gaps.index[0]}, "
               f"gap size = {bad_gaps.iloc[0]}")

    # 15-min continuity
    ts_15min = df_15min["timestamp"].sort_values().reset_index(drop=True)
    gaps_15 = ts_15min.diff().dropna()
    expected_gap_15 = pd.Timedelta(minutes=15)
    bad_gaps_15 = gaps_15[gaps_15 != expected_gap_15]
    if len(bad_gaps_15) == 0:
        r.ok(C, f"15-min data: no gaps ({ts_15min.iloc[0]} to {ts_15min.iloc[-1]})")
    else:
        r.fail(C, f"15-min data: {len(bad_gaps_15)} timestamp gaps found")

    # Hourly continuity
    ts_hourly = df_hourly["timestamp"].sort_values().reset_index(drop=True)
    gaps_h = ts_hourly.diff().dropna()
    expected_gap_h = pd.Timedelta(hours=1)
    bad_gaps_h = gaps_h[gaps_h != expected_gap_h]
    if len(bad_gaps_h) == 0:
        r.ok(C, f"hourly data: no gaps ({ts_hourly.iloc[0]} to {ts_hourly.iloc[-1]})")
    else:
        r.fail(C, f"hourly data: {len(bad_gaps_h)} timestamp gaps found")

    # Duplicate timestamps
    for name, df in [
        ("1-min", df_1min), ("15-min", df_15min), ("hourly", df_hourly),
    ]:
        if df["timestamp"].is_unique:
            r.ok(C, f"{name}: no duplicate timestamps")
        else:
            dupes = df["timestamp"].duplicated().sum()
            r.fail(C, f"{name}: {dupes} duplicate timestamps")

    # ==================================================================
    # 4. Physical Range Checks (on hourly rollup for speed)
    # ==================================================================
    C = "4. Physical Range Checks"
    h = df_hourly  # shorthand

    def check_range(col, lo, hi, units=""):
        """Check that all values in column fall within [lo, hi]."""
        if col not in h.columns:
            r.fail(C, f"{col} missing from hourly data")
            return
        vals = h[col]
        below = (vals < lo).sum()
        above = (vals > hi).sum()
        vmin = vals.min()
        vmax = vals.max()
        label = f"{col}: [{lo}, {hi}]"
        if units:
            label += f" {units}"
        if below == 0 and above == 0:
            r.ok(C, label, f"actual [{vmin:.2f}, {vmax:.2f}]")
        else:
            r.fail(C, label,
                   f"actual [{vmin:.2f}, {vmax:.2f}], "
                   f"{below} below, {above} above")

    # Unit MW
    check_range("U1_UNIT_MW_GROSS", 0, 310, "MW")

    # Feedwater flow
    check_range("U1_BFPA_FW_FLOW", 0, 300, "t/hr")
    check_range("U1_BFPB_FW_FLOW", 0, 300, "t/hr")

    # Bearing DE temps
    check_range("U1_BFPA_BRG_DE_TEMP", 0, 120, "degC")
    check_range("U1_BFPB_BRG_DE_TEMP", 0, 120, "degC")

    # Bearing NDE temps
    check_range("U1_BFPA_BRG_NDE_TEMP", 0, 120, "degC")
    check_range("U1_BFPB_BRG_NDE_TEMP", 0, 120, "degC")

    # Thrust active temps
    check_range("U1_BFPA_THR_ACT_TEMP", 0, 120, "degC")
    check_range("U1_BFPB_THR_ACT_TEMP", 0, 120, "degC")

    # Vibration DE X
    check_range("U1_BFPA_VIB_DE_X", 0, 150, "um")
    check_range("U1_BFPB_VIB_DE_X", 0, 150, "um")

    # Vibration NDE X
    check_range("U1_BFPA_VIB_NDE_X", 0, 150, "um")
    check_range("U1_BFPB_VIB_NDE_X", 0, 150, "um")

    # Seal DE leak
    check_range("U1_BFPA_SEAL_DE_LEAK", 0, 50, "cc/min")
    check_range("U1_BFPB_SEAL_DE_LEAK", 0, 50, "cc/min")

    # Lube oil header pressure
    check_range("U1_BFPA_LO_HDR_PRESS", 0, 3, "bar")
    check_range("U1_BFPB_LO_HDR_PRESS", 0, 3, "bar")

    # Ambient temperature
    check_range("U1_AMBIENT_TEMP", -10, 55, "degC")

    # ==================================================================
    # 5. Operational Logic Checks
    # ==================================================================
    C = "5. Operational Logic"

    # --- Outage window: Sep 1-14, both BFPs stopped, UNIT_MW = 0 ---
    outage_mask = (
        (h["timestamp"] >= "2024-09-01") &
        (h["timestamp"] < "2024-09-15")
    )
    outage = h[outage_mask]
    if len(outage) == 0:
        r.fail(C, "outage window", "no rows found for Sep 1-14")
    else:
        bfpa_run = outage["U1_BFPA_RUN_STATUS"]
        bfpb_run = outage["U1_BFPB_RUN_STATUS"]
        unit_mw = outage["U1_UNIT_MW_GROSS"]

        bfpa_stopped = (bfpa_run == 0).all()
        bfpb_stopped = (bfpb_run == 0).all()
        mw_zero = (unit_mw == 0).all()

        if bfpa_stopped and bfpb_stopped and mw_zero:
            r.ok(C, f"outage Sep 1-14: both BFPs stopped, UNIT_MW=0 ({len(outage)} rows)")
        else:
            details = []
            if not bfpa_stopped:
                details.append(f"BFPA running in {(bfpa_run != 0).sum()} rows")
            if not bfpb_stopped:
                details.append(f"BFPB running in {(bfpb_run != 0).sum()} rows")
            if not mw_zero:
                details.append(f"UNIT_MW>0 in {(unit_mw != 0).sum()} rows")
            r.fail(C, "outage Sep 1-14", "; ".join(details))

    # --- Only one BFP running at a time ---
    run_sum = h["U1_BFPA_RUN_STATUS"] + h["U1_BFPB_RUN_STATUS"]
    both_running = (run_sum > 1).sum()
    if both_running == 0:
        r.ok(C, "single BFP operation: sum(RUN_STATUS) <= 1 for all rows")
    else:
        r.fail(C, "single BFP operation",
               f"{both_running} rows with both BFPs running simultaneously")

    # --- When pump running: FW_FLOW > 0, SPEED > 0, MTR_POWER > 0 ---
    for pump in ["BFPA", "BFPB"]:
        running = h[h[f"U1_{pump}_RUN_STATUS"] == 1]
        if len(running) == 0:
            r.warn(C, f"{pump} running checks", "no running rows found")
            continue

        flow_ok = (running[f"U1_{pump}_FW_FLOW"] > 0).all()
        speed_ok = (running[f"U1_{pump}_SPEED"] > 0).all()
        power_ok = (running[f"U1_{pump}_MTR_POWER"] > 0).all()

        if flow_ok and speed_ok and power_ok:
            r.ok(C, f"{pump} running: FW_FLOW>0, SPEED>0, MTR_POWER>0 "
                 f"({len(running)} rows)")
        else:
            issues = []
            if not flow_ok:
                n = (running[f"U1_{pump}_FW_FLOW"] <= 0).sum()
                issues.append(f"FW_FLOW<=0 in {n} rows")
            if not speed_ok:
                n = (running[f"U1_{pump}_SPEED"] <= 0).sum()
                issues.append(f"SPEED<=0 in {n} rows")
            if not power_ok:
                n = (running[f"U1_{pump}_MTR_POWER"] <= 0).sum()
                issues.append(f"MTR_POWER<=0 in {n} rows")
            r.fail(C, f"{pump} running checks", "; ".join(issues))

    # --- When pump stopped: SPEED = 0, MTR_POWER = 0 ---
    for pump in ["BFPA", "BFPB"]:
        stopped = h[h[f"U1_{pump}_RUN_STATUS"] == 0]
        if len(stopped) == 0:
            r.warn(C, f"{pump} stopped checks", "no stopped rows found")
            continue

        speed_zero = (stopped[f"U1_{pump}_SPEED"] == 0).all()
        power_zero = (stopped[f"U1_{pump}_MTR_POWER"] == 0).all()

        if speed_zero and power_zero:
            r.ok(C, f"{pump} stopped: SPEED=0, MTR_POWER=0 ({len(stopped)} rows)")
        else:
            issues = []
            if not speed_zero:
                n = (stopped[f"U1_{pump}_SPEED"] != 0).sum()
                issues.append(f"SPEED!=0 in {n} rows")
            if not power_zero:
                n = (stopped[f"U1_{pump}_MTR_POWER"] != 0).sum()
                issues.append(f"MTR_POWER!=0 in {n} rows")
            r.fail(C, f"{pump} stopped checks", "; ".join(issues))

    # ==================================================================
    # 6. Fault Signature Verification
    # ==================================================================
    C = "6. Fault Signatures"

    # SEAL-001: BFP-A SEAL_DE_LEAK should be higher in May vs January
    jan = h[h["timestamp"].dt.month == 1]
    may = h[h["timestamp"].dt.month == 5]

    # Only compare when BFPA is running
    jan_running = jan[jan["U1_BFPA_RUN_STATUS"] == 1]
    may_running = may[may["U1_BFPA_RUN_STATUS"] == 1]

    if len(jan_running) > 0 and len(may_running) > 0:
        jan_seal = jan_running["U1_BFPA_SEAL_DE_LEAK"].mean()
        may_seal = may_running["U1_BFPA_SEAL_DE_LEAK"].mean()
        if may_seal > jan_seal:
            r.ok(C, f"SEAL-001: BFP-A SEAL_DE_LEAK May({may_seal:.2f}) > "
                 f"Jan({jan_seal:.2f})")
        else:
            r.fail(C, f"SEAL-001: BFP-A SEAL_DE_LEAK May({may_seal:.2f}) "
                   f"not > Jan({jan_seal:.2f})")
    else:
        r.warn(C, "SEAL-001: insufficient running data",
               f"Jan running={len(jan_running)}, May running={len(may_running)}")

    # BRG-001: BFP-B BRG_NDE_TEMP should be higher in Aug vs Jul
    jul = h[h["timestamp"].dt.month == 7]
    aug = h[h["timestamp"].dt.month == 8]

    jul_running = jul[jul["U1_BFPB_RUN_STATUS"] == 1]
    aug_running = aug[aug["U1_BFPB_RUN_STATUS"] == 1]

    if len(jul_running) > 0 and len(aug_running) > 0:
        jul_brg = jul_running["U1_BFPB_BRG_NDE_TEMP"].mean()
        aug_brg = aug_running["U1_BFPB_BRG_NDE_TEMP"].mean()
        if aug_brg > jul_brg:
            r.ok(C, f"BRG-001: BFP-B BRG_NDE_TEMP Aug({aug_brg:.2f}) > "
                 f"Jul({jul_brg:.2f})")
        else:
            r.fail(C, f"BRG-001: BFP-B BRG_NDE_TEMP Aug({aug_brg:.2f}) "
                   f"not > Jul({jul_brg:.2f})")
    else:
        r.warn(C, "BRG-001: insufficient running data",
               f"Jul running={len(jul_running)}, Aug running={len(aug_running)}")

    # ALIGN-001: BFP-A VIB_DE_X should be higher in Dec vs Oct
    oct = h[h["timestamp"].dt.month == 10]
    dec = h[h["timestamp"].dt.month == 12]

    oct_running = oct[oct["U1_BFPA_RUN_STATUS"] == 1]
    dec_running = dec[dec["U1_BFPA_RUN_STATUS"] == 1]

    if len(oct_running) > 0 and len(dec_running) > 0:
        oct_vib = oct_running["U1_BFPA_VIB_DE_X"].mean()
        dec_vib = dec_running["U1_BFPA_VIB_DE_X"].mean()
        if dec_vib > oct_vib:
            r.ok(C, f"ALIGN-001: BFP-A VIB_DE_X Dec({dec_vib:.2f}) > "
                 f"Oct({oct_vib:.2f})")
        else:
            r.fail(C, f"ALIGN-001: BFP-A VIB_DE_X Dec({dec_vib:.2f}) "
                   f"not > Oct({oct_vib:.2f})")
    else:
        r.warn(C, "ALIGN-001: insufficient running data",
               f"Oct running={len(oct_running)}, Dec running={len(dec_running)}")

    # ==================================================================
    # 7. SP&L Correlation: Unit MW seasonal pattern (summer > winter)
    # ==================================================================
    C = "7. SP&L Correlation"

    summer_months = [6, 7, 8]
    winter_months = [12, 1, 2]

    summer_mw = h[h["timestamp"].dt.month.isin(summer_months)]["U1_UNIT_MW_GROSS"]
    winter_mw = h[h["timestamp"].dt.month.isin(winter_months)]["U1_UNIT_MW_GROSS"]

    # Exclude outage (Sep) from summer; it's not in summer_months anyway
    summer_mean = summer_mw.mean()
    winter_mean = winter_mw.mean()

    if summer_mean > winter_mean:
        r.ok(C, f"Unit MW summer({summer_mean:.1f}) > winter({winter_mean:.1f}) MW")
    else:
        r.fail(C, f"Unit MW summer({summer_mean:.1f}) not > winter({winter_mean:.1f}) MW")

    # ==================================================================
    # 8. Event Log Checks
    # ==================================================================
    C = "8. Event Logs"

    # Alarm log has entries
    n_alarms = len(alarm_log)
    if n_alarms > 0:
        r.ok(C, f"alarm_log: {n_alarms} entries")
    else:
        r.fail(C, "alarm_log: empty")

    # Trip log has BFP-B trip
    if len(trip_log) > 0:
        bfpb_trips = trip_log[trip_log["equipment"].str.contains("BFPB|BFP-B",
                                                                   case=False,
                                                                   na=False)]
        if len(bfpb_trips) > 0:
            r.ok(C, f"trip_log: {len(bfpb_trips)} BFP-B trip(s) found")
        else:
            r.fail(C, "trip_log: no BFP-B trip found",
                   f"equipment values: {trip_log['equipment'].unique().tolist()}")
    else:
        r.fail(C, "trip_log: empty")

    # Operator actions has 7 entries
    n_actions = len(operator_actions)
    if n_actions == 7:
        r.ok(C, f"operator_actions: {n_actions} entries")
    else:
        r.fail(C, f"operator_actions: expected 7, got {n_actions}")

    # ==================================================================
    # Summary and exit
    # ==================================================================
    failures = r.summary()
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
