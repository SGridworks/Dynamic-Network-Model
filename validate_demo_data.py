#!/usr/bin/env python3
"""Comprehensive validation of SP&L demo data."""

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import networkx as nx
from demo_data.load_demo_data import load_all


class Report:
    def __init__(self):
        self.results = []

    def ok(self, cat, check, detail=""):
        self.results.append((cat, check, "PASS", detail))

    def fail(self, cat, check, detail):
        self.results.append((cat, check, "FAIL", detail))

    def warn(self, cat, check, detail):
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
                    line += f" — {detail}"
                print(line)
        p = sum(1 for _, _, s, _ in self.results if s == "PASS")
        f = sum(1 for _, _, s, _ in self.results if s == "FAIL")
        w = sum(1 for _, _, s, _ in self.results if s == "WARN")
        print(f"\n{'='*70}")
        print(f"  TOTAL: {p} PASS | {f} FAIL | {w} WARN")
        print(f"{'='*70}\n")


def main():
    print("Loading all datasets...")
    d = load_all()
    subs = d["substations"]
    fdrs = d["feeders"]
    xfmrs = d["transformers"]
    custs = d["customers"]
    solar = d["solar_installations"]
    ev = d["ev_chargers"]
    batt = d["battery_installations"]
    lp = d["load_profiles"]
    cid = d["customer_interval_data"]
    wx = d["weather_data"]
    out = d["outage_history"]
    gs = d["growth_scenarios"]
    sp = d["solar_profiles"]
    evp = d["ev_charging_profiles"]
    nodes = d["network_nodes"]
    edges = d["network_edges"]
    r = Report()

    # ── Category 0: Row Counts ──
    C = "0. Row Counts"
    for name, df, expected in [
        ("substations", subs, 15), ("feeders", fdrs, 65),
        ("transformers", xfmrs, 21545), ("customers", custs, None),
        ("solar_installations", solar, None), ("ev_chargers", ev, None),
        ("battery_installations", batt, None),
        ("network_nodes", nodes, 43827), ("network_edges", edges, 43826),
        ("load_profiles", lp, 873600), ("customer_interval_data", cid, 6720000),
        ("weather_data", wx, 43848), ("outage_history", out, None),
        ("growth_scenarios", gs, 85), ("solar_profiles", sp, 288),
        ("ev_charging_profiles", evp, 48),
    ]:
        actual = len(df)
        if expected is None:
            r.ok(C, f"{name}: {actual} rows")
        elif actual == expected:
            r.ok(C, f"{name}: {actual} rows")
        else:
            r.fail(C, f"{name}: expected {expected}, got {actual}")

    # ── Category 1: Referential Integrity ──
    C = "1. Referential Integrity"
    sub_ids = set(subs.index)
    fdr_ids = set(fdrs.index)
    xfmr_ids = set(xfmrs.index)
    cust_ids = set(custs.index)
    node_ids = set(nodes.index)

    def check_fk(child_name, child_col, parent_name, parent_ids):
        orphans = child_col[~child_col.isin(parent_ids)]
        n = len(orphans)
        total = len(child_col)
        label = f"{child_name} -> {parent_name}"
        if n == 0:
            r.ok(C, f"{label} ({total}/{total} valid)")
        else:
            samples = orphans.unique()[:5].tolist()
            r.fail(C, f"{label}", f"{n}/{total} orphans, e.g. {samples}")

    check_fk("feeders.substation_id", fdrs["substation_id"], "substations", sub_ids)
    check_fk("transformers.feeder_id", xfmrs["feeder_id"], "feeders", fdr_ids)
    check_fk("transformers.substation_id", xfmrs["substation_id"], "substations", sub_ids)
    check_fk("customers.transformer_id", custs["transformer_id"], "transformers", xfmr_ids)
    check_fk("customers.feeder_id", custs["feeder_id"], "feeders", fdr_ids)
    check_fk("customers.substation_id", custs["substation_id"], "substations", sub_ids)
    check_fk("solar.customer_id", solar["customer_id"], "customers", cust_ids)
    check_fk("solar.transformer_id", solar["transformer_id"], "transformers", xfmr_ids)
    check_fk("solar.feeder_id", solar["feeder_id"], "feeders", fdr_ids)
    check_fk("solar.substation_id", solar["substation_id"], "substations", sub_ids)
    check_fk("ev.customer_id", ev["customer_id"], "customers", cust_ids)
    check_fk("ev.transformer_id", ev["transformer_id"], "transformers", xfmr_ids)
    check_fk("ev.feeder_id", ev["feeder_id"], "feeders", fdr_ids)
    check_fk("ev.substation_id", ev["substation_id"], "substations", sub_ids)
    check_fk("load_profiles.feeder_id", lp["feeder_id"], "feeders", fdr_ids)
    check_fk("load_profiles.substation_id", lp["substation_id"], "substations", sub_ids)
    check_fk("cid.customer_id", cid["customer_id"], "customers", cust_ids)
    check_fk("cid.transformer_id", cid["transformer_id"], "transformers", xfmr_ids)
    check_fk("cid.feeder_id", cid["feeder_id"], "feeders", fdr_ids)
    check_fk("cid.substation_id", cid["substation_id"], "substations", sub_ids)
    check_fk("outage.feeder_id", out["feeder_id"], "feeders", fdr_ids)
    check_fk("outage.substation_id", out["substation_id"], "substations", sub_ids)
    check_fk("edges.from_node_id", edges["from_node_id"], "nodes", node_ids)
    check_fk("edges.to_node_id", edges["to_node_id"], "nodes", node_ids)
    check_fk("edges.feeder_id", edges["feeder_id"], "feeders", fdr_ids)
    check_fk("edges.substation_id", edges["substation_id"], "substations", sub_ids)
    # nodes.feeder_id (non-empty, excluding tie switches which have no feeder)
    nf = nodes[(nodes["feeder_id"].notna()) & (nodes["feeder_id"] != "") & (nodes["feeder_id"].astype(str).str.strip() != "")]
    check_fk("nodes.feeder_id", nf["feeder_id"], "feeders", fdr_ids)
    check_fk("nodes.substation_id", nodes["substation_id"], "substations", sub_ids)

    # ── Category 2: Cross-Table Counts ──
    C = "2. Cross-Table Counts"
    # feeders.num_customers vs actual
    actual_cust_per_fdr = custs.groupby("feeder_id").size()
    discreps = []
    for fid in fdrs.index:
        stated = fdrs.loc[fid, "num_customers"]
        actual = actual_cust_per_fdr.get(fid, 0)
        discreps.append(abs(stated - actual))
    mean_d = sum(discreps) / len(discreps)
    max_d = max(discreps)
    if max_d == 0:
        r.ok(C, "feeders.num_customers vs actual")
    else:
        r.warn(C, "feeders.num_customers vs actual",
               f"mean discrepancy={mean_d:.0f}, max={max_d}. "
               "Column is cosmetic/estimated, not exact.")

    # substations.num_transformers (power xfmrs at sub, not dist xfmrs)
    vals = subs["num_transformers"]
    if vals.between(1, 5).all():
        r.ok(C, "substations.num_transformers in [1,5]")
    else:
        r.fail(C, "substations.num_transformers range", f"range [{vals.min()},{vals.max()}]")

    # load_profiles per feeder
    lp_counts = lp.groupby("feeder_id").size()
    bad_lp = lp_counts[lp_counts != 13440]
    if len(bad_lp) == 0:
        r.ok(C, "load_profiles: 13440 intervals per feeder (5 years x 4 seasons)")
    else:
        r.fail(C, "load_profiles intervals/feeder", f"{len(bad_lp)} feeders wrong, e.g. {dict(bad_lp.head())}")

    # customer_interval_data per customer
    cid_counts = cid.groupby("customer_id").size()
    bad_cid = cid_counts[cid_counts != 13440]
    if len(bad_cid) == 0:
        r.ok(C, "cid: 13440 intervals per customer (5 years x 4 seasons)")
    else:
        r.fail(C, "cid intervals/customer", f"{len(bad_cid)} customers wrong, e.g. {dict(bad_cid.head())}")

    n_cid_custs = cid["customer_id"].nunique()
    if 450 <= n_cid_custs <= 550:
        r.ok(C, f"cid sample size: {n_cid_custs} customers")
    else:
        r.warn(C, f"cid sample size: {n_cid_custs}", "expected ~500")

    # ── Category 3: DER Flag Consistency ──
    C = "3. DER Flag Consistency"
    solar_custs = set(solar["customer_id"])
    ev_custs = set(ev["customer_id"])
    has_solar_set = set(custs[custs["has_solar"]].index)
    has_ev_set = set(custs[custs["has_ev"]].index)

    miss_solar = has_solar_set - solar_custs
    extra_solar = solar_custs - has_solar_set
    if not miss_solar and not extra_solar:
        r.ok(C, "has_solar flag matches solar_installations")
    else:
        r.fail(C, "has_solar mismatch", f"{len(miss_solar)} flagged but no record, {len(extra_solar)} record but not flagged")

    miss_ev = has_ev_set - ev_custs
    extra_ev = ev_custs - has_ev_set
    if not miss_ev and not extra_ev:
        r.ok(C, "has_ev flag matches ev_chargers")
    else:
        r.fail(C, "has_ev mismatch", f"{len(miss_ev)} flagged but no record, {len(extra_ev)} record but not flagged")

    batt_custs = set(batt["customer_id"])
    has_batt_set = set(custs[custs["has_battery"]].index)
    miss_batt = has_batt_set - batt_custs
    extra_batt = batt_custs - has_batt_set
    if not miss_batt and not extra_batt:
        r.ok(C, "has_battery flag matches battery_installations")
    else:
        r.fail(C, "has_battery mismatch", f"{len(miss_batt)} flagged but no record, {len(extra_batt)} record but not flagged")

    # Battery hierarchy consistency
    batt_merged = batt.merge(custs[["transformer_id", "feeder_id", "substation_id"]],
                              left_on="customer_id", right_index=True, suffixes=("_batt", "_cust"))
    bxfmr = (batt_merged["transformer_id_batt"] == batt_merged["transformer_id_cust"]).all()
    bfdr = (batt_merged["feeder_id_batt"] == batt_merged["feeder_id_cust"]).all()
    bsub = (batt_merged["substation_id_batt"] == batt_merged["substation_id_cust"]).all()
    if bxfmr and bfdr and bsub:
        r.ok(C, "battery hierarchy matches customer hierarchy")
    else:
        r.fail(C, "battery hierarchy mismatch", f"xfmr={bxfmr}, fdr={bfdr}, sub={bsub}")

    # Solar hierarchy consistency
    solar_merged = solar.merge(custs[["transformer_id", "feeder_id", "substation_id"]],
                                left_on="customer_id", right_index=True, suffixes=("_solar", "_cust"))
    xfmr_match = (solar_merged["transformer_id_solar"] == solar_merged["transformer_id_cust"]).all()
    fdr_match = (solar_merged["feeder_id_solar"] == solar_merged["feeder_id_cust"]).all()
    sub_match = (solar_merged["substation_id_solar"] == solar_merged["substation_id_cust"]).all()
    if xfmr_match and fdr_match and sub_match:
        r.ok(C, "solar hierarchy matches customer hierarchy")
    else:
        r.fail(C, "solar hierarchy mismatch",
               f"xfmr={xfmr_match}, fdr={fdr_match}, sub={sub_match}")

    # EV hierarchy consistency
    ev_merged = ev.merge(custs[["transformer_id", "feeder_id", "substation_id"]],
                          left_on="customer_id", right_index=True, suffixes=("_ev", "_cust"))
    xfmr_match = (ev_merged["transformer_id_ev"] == ev_merged["transformer_id_cust"]).all()
    fdr_match = (ev_merged["feeder_id_ev"] == ev_merged["feeder_id_cust"]).all()
    sub_match = (ev_merged["substation_id_ev"] == ev_merged["substation_id_cust"]).all()
    if xfmr_match and fdr_match and sub_match:
        r.ok(C, "EV hierarchy matches customer hierarchy")
    else:
        r.fail(C, "EV hierarchy mismatch",
               f"xfmr={xfmr_match}, fdr={fdr_match}, sub={sub_match}")

    # ── Category 4: Spatial Consistency ──
    C = "4. Spatial Consistency"
    LAT_MIN, LAT_MAX = 33.2, 33.7
    LON_MIN, LON_MAX = -112.3, -111.85

    def check_coords(name, lats, lons):
        lat_ok = lats.between(LAT_MIN, LAT_MAX).all()
        lon_ok = lons.between(LON_MIN, LON_MAX).all()
        if lat_ok and lon_ok:
            r.ok(C, f"{name} coords in Phoenix range")
        else:
            bad_lat = (~lats.between(LAT_MIN, LAT_MAX)).sum()
            bad_lon = (~lons.between(LON_MIN, LON_MAX)).sum()
            r.fail(C, f"{name} coords out of range", f"{bad_lat} bad lat, {bad_lon} bad lon")

    check_coords("substations", subs["latitude"], subs["longitude"])
    check_coords("feeders(head)", fdrs["latitude_head"], fdrs["longitude_head"])
    check_coords("feeders(tail)", fdrs["latitude_tail"], fdrs["longitude_tail"])
    check_coords("transformers", xfmrs["latitude"], xfmrs["longitude"])
    check_coords("nodes", nodes["latitude"], nodes["longitude"])

    # Feeder head at substation
    fdr_sub = fdrs.merge(subs[["latitude", "longitude"]].rename(
        columns={"latitude": "sub_lat", "longitude": "sub_lon"}),
        left_on="substation_id", right_index=True)
    head_lat_diff = (fdr_sub["latitude_head"] - fdr_sub["sub_lat"]).abs()
    head_lon_diff = (fdr_sub["longitude_head"] - fdr_sub["sub_lon"]).abs()
    max_diff = max(head_lat_diff.max(), head_lon_diff.max())
    if max_diff < 0.001:
        r.ok(C, f"feeder heads at substations (max diff={max_diff:.6f} deg)")
    else:
        r.fail(C, "feeder heads not at substations", f"max diff={max_diff:.4f} deg")

    # Customer near transformer (sample 10k for speed)
    sample_custs = custs.sample(min(10000, len(custs)), random_state=42)
    cust_xfmr = sample_custs.merge(xfmrs[["latitude", "longitude"]],
                                     left_on="transformer_id", right_index=True,
                                     suffixes=("_c", "_x"))
    dlat = (cust_xfmr["latitude_c"] - cust_xfmr["latitude_x"]).abs() * 69  # miles
    dlon = (cust_xfmr["longitude_c"] - cust_xfmr["longitude_x"]).abs() * 57.5
    dist = (dlat**2 + dlon**2).apply(math.sqrt)
    max_dist = dist.max()
    p99_dist = dist.quantile(0.99)
    if max_dist < 0.5:  # 0.5 miles
        r.ok(C, f"customers near transformers (max={max_dist:.3f} mi, p99={p99_dist:.3f} mi)")
    else:
        far = (dist > 0.5).sum()
        r.warn(C, "customers far from transformers",
               f"{far}/{len(dist)} > 0.5mi, max={max_dist:.3f} mi, p99={p99_dist:.3f} mi")

    # Solar co-located with customer (sample)
    solar_sample = solar.head(5000)
    solar_cust = solar_sample.merge(custs[["latitude", "longitude"]],
                                     left_on="customer_id", right_index=True,
                                     suffixes=("_s", "_c"))
    slat_diff = (solar_cust["latitude_s"] - solar_cust["latitude_c"]).abs().max()
    slon_diff = (solar_cust["longitude_s"] - solar_cust["longitude_c"]).abs().max()
    if slat_diff < 0.0001 and slon_diff < 0.0001:
        r.ok(C, "solar co-located with customers")
    else:
        r.warn(C, "solar not co-located", f"max lat diff={slat_diff:.6f}, lon diff={slon_diff:.6f}")

    # ── Category 5: Capacity/Loading ──
    C = "5. Capacity/Loading"
    # Substation peak < rated
    sub_overload = subs[subs["peak_load_mva"] >= subs["rated_capacity_mva"]]
    if len(sub_overload) == 0:
        r.ok(C, "all substations: peak < rated capacity")
    else:
        r.fail(C, "substation overloads", f"{len(sub_overload)} substations overloaded")

    sub_loading = subs["peak_load_mva"] / subs["rated_capacity_mva"]
    r.ok(C, f"substation loading range: [{sub_loading.min():.2f}, {sub_loading.max():.2f}]")

    # Feeder peak < rated
    fdr_overload = fdrs[fdrs["peak_load_mw"] >= fdrs["rated_capacity_mw"]]
    if len(fdr_overload) == 0:
        r.ok(C, "all feeders: peak < rated capacity")
    else:
        r.fail(C, "feeder overloads", f"{len(fdr_overload)} feeders overloaded")

    # Standard transformer kVA sizes
    std_kva = {10, 15, 25, 37.5, 50, 75, 100, 167, 250, 333, 500}
    actual_kva = set(xfmrs["rated_kva"].unique())
    non_std = actual_kva - std_kva
    if not non_std:
        r.ok(C, "all transformer kVA ratings are standard sizes")
    else:
        r.warn(C, "non-standard transformer kVA", f"{non_std}")

    # Customer demand vs transformer capacity
    cust_demand = custs.groupby("transformer_id")["contracted_demand_kw"].sum()
    xfmr_cap = xfmrs["rated_kva"]
    loading = cust_demand / xfmr_cap
    overloaded = (loading > 2.0).sum()
    if overloaded == 0:
        r.ok(C, f"transformer loading: max ratio={loading.max():.2f}")
    else:
        r.warn(C, "transformer demand/capacity",
               f"{overloaded}/{len(loading)} xfmrs have demand/kVA > 2.0, "
               f"max={loading.max():.1f}, mean={loading.mean():.2f}")

    # Load profile peaks vs feeder capacity
    lp_peaks = lp.groupby("feeder_id")["load_mw"].max()
    fdr_cap = fdrs["rated_capacity_mw"]
    lp_ratio = lp_peaks / fdr_cap
    over = (lp_ratio > 1.0).sum()
    if over == 0:
        r.ok(C, f"load profile peaks within feeder capacity (max ratio={lp_ratio.max():.2f})")
    else:
        r.warn(C, "load profile exceeds feeder capacity", f"{over} feeders, max ratio={lp_ratio.max():.2f}")

    # ── Category 6: Network Topology ──
    C = "6. Network Topology"
    # Self-loops
    self_loops = edges[edges["from_node_id"] == edges["to_node_id"]]
    if len(self_loops) == 0:
        r.ok(C, "no self-loops in edges")
    else:
        r.fail(C, "self-loops found", f"{len(self_loops)} self-loop edges")

    # Node type distribution
    nt_dist = nodes["node_type"].value_counts().to_dict()
    r.ok(C, f"node types: {nt_dist}")

    # Edge type distribution
    et_dist = edges["edge_type"].value_counts().to_dict()
    r.ok(C, f"edge types: {et_dist}")

    # Feeder tree topology (excluding ties)
    non_tie = edges[edges["edge_type"] != "tie"]
    feeder_ids_in_edges = non_tie["feeder_id"].unique()
    tree_pass = 0
    tree_fail_list = []
    for fid in feeder_ids_in_edges:
        fe = non_tie[non_tie["feeder_id"] == fid]
        G = nx.Graph()
        for _, row in fe.iterrows():
            G.add_edge(row["from_node_id"], row["to_node_id"])
        if nx.is_tree(G):
            tree_pass += 1
        else:
            nc = nx.number_connected_components(G)
            tree_fail_list.append(f"{fid}(components={nc},nodes={G.number_of_nodes()},edges={G.number_of_edges()})")
    if not tree_fail_list:
        r.ok(C, f"all {tree_pass} feeder subgraphs are valid trees")
    else:
        r.fail(C, "feeder tree topology failures", "; ".join(tree_fail_list[:5]))

    # Tie switches connect different feeders
    # Each tie has 2 edges: fdr_a_TAIL -> TIE and TIE -> fdr_b_TAIL
    # We pair them by grouping on the tie switch node
    ties = edges[edges["edge_type"] == "tie"]
    if len(ties) > 0:
        # Get the feeder_id from the edge itself (not the node) — more reliable
        tie_fdrs = ties["feeder_id"].values
        # Group by pairs: consecutive tie edges share a tie switch
        tie_pairs_ok = True
        bad_pairs = 0
        for i in range(0, len(ties) - 1, 2):
            if tie_fdrs[i] == tie_fdrs[i + 1]:
                bad_pairs += 1
                tie_pairs_ok = False
        if tie_pairs_ok:
            r.ok(C, f"all {len(ties)//2} tie switches connect different feeders")
        else:
            r.fail(C, "tie switches on same feeder", f"{bad_pairs} tie pairs")

    # ── Category 7: Temporal Completeness ──
    C = "7. Temporal Completeness"
    # Weather: full year
    wx_ts = wx["timestamp"].sort_values()
    wx_start = wx_ts.iloc[0]
    wx_end = wx_ts.iloc[-1]
    wx_gaps = wx_ts.diff().dropna()
    wx_gap_ok = (wx_gaps == pd.Timedelta(hours=1)).all()
    if wx_gap_ok:
        r.ok(C, f"weather: hourly, no gaps ({wx_start} to {wx_end})")
    else:
        bad_gaps = (wx_gaps != pd.Timedelta(hours=1)).sum()
        r.fail(C, "weather gaps", f"{bad_gaps} non-1h gaps")

    if wx["timestamp"].is_unique:
        r.ok(C, "weather: no duplicate timestamps")
    else:
        r.fail(C, "weather: duplicate timestamps")

    # Load profiles: seasonal start dates
    lp_dates = lp["timestamp"].dt.date.unique()
    seasons_found = set()
    for d in lp_dates:
        m = d.month
        if m in (1, 2):
            seasons_found.add("winter")
        elif m in (3, 4, 5):
            seasons_found.add("spring")
        elif m in (6, 7, 8):
            seasons_found.add("summer")
        elif m in (9, 10, 11, 12):
            seasons_found.add("fall")
    if len(seasons_found) == 4:
        r.ok(C, f"load profiles cover 4 seasons: {seasons_found}")
    else:
        r.fail(C, "load profiles missing seasons", f"found: {seasons_found}")

    # CID: 4 seasons x 5 years
    cid_months = set(cid["timestamp"].dt.month.unique())
    expected_cid_months = {1, 4, 7, 10}  # Jan, Apr, Jul, Oct
    if expected_cid_months <= cid_months:
        r.ok(C, f"customer interval data covers 4 seasons (months: {sorted(cid_months)})")
    else:
        missing = expected_cid_months - cid_months
        r.fail(C, "cid missing season months", f"missing: {missing}, found: {sorted(cid_months)}")

    # Outage: end > start
    if (out["end_time"] > out["start_time"]).all():
        r.ok(C, "all outages: end_time > start_time")
    else:
        bad = (out["end_time"] <= out["start_time"]).sum()
        r.fail(C, "outage end <= start", f"{bad} events")

    # Outage duration consistency
    calc_dur = (out["end_time"] - out["start_time"]).dt.total_seconds() / 3600
    dur_diff = (calc_dur - out["duration_hours"]).abs()
    if dur_diff.max() < 0.2:
        r.ok(C, f"outage durations consistent (max diff={dur_diff.max():.3f} hrs)")
    else:
        bad = (dur_diff >= 0.2).sum()
        r.fail(C, "outage duration mismatch", f"{bad} events, max diff={dur_diff.max():.2f} hrs")

    # Outage years
    out_years = out["start_time"].dt.year.unique()
    expected_out_years = {2020, 2021, 2022, 2023, 2024}
    if set(out_years) == expected_out_years:
        r.ok(C, f"outages span 2020-2024 ({len(out_years)} years)")
    else:
        r.warn(C, "outage years", f"expected {sorted(expected_out_years)}, found: {sorted(out_years)}")

    # ── Category 8: Value Ranges ──
    C = "8. Value Ranges"
    # Substation voltages
    high_v = set(subs["voltage_high_kv"].unique())
    if high_v <= {69, 115, 230}:
        r.ok(C, f"substation high voltage: {sorted(high_v)} kV")
    else:
        r.fail(C, "unexpected high voltage", str(high_v))

    low_v = set(subs["voltage_low_kv"].unique())
    if low_v <= {12.47, 13.8, 24.9}:
        r.ok(C, f"substation low voltage: {sorted(low_v)} kV")
    else:
        r.fail(C, "unexpected low voltage", str(low_v))

    # Feeder direction
    dirs = set(fdrs["direction"].unique())
    if dirs <= {"N", "S", "E", "W"}:
        r.ok(C, f"feeder directions: {sorted(dirs)}")
    else:
        r.fail(C, "unexpected directions", str(dirs))

    # Feeder length
    fl = fdrs["length_miles"]
    if fl.between(1.5, 10).all():
        r.ok(C, f"feeder length: [{fl.min():.1f}, {fl.max():.1f}] miles")
    else:
        r.warn(C, "feeder length range", f"[{fl.min():.1f}, {fl.max():.1f}]")

    # Customer types
    ctypes = set(custs["customer_type"].unique())
    expected_types = {"residential", "commercial", "industrial", "municipal"}
    if ctypes == expected_types:
        r.ok(C, f"customer types: {sorted(ctypes)}")
    else:
        r.fail(C, "unexpected customer types", str(ctypes - expected_types))

    # Load profile voltage
    lpv = lp["voltage_pu"]
    if lpv.between(0.90, 1.10).all():
        r.ok(C, f"load profile voltage_pu: [{lpv.min():.3f}, {lpv.max():.3f}]")
    else:
        bad = (~lpv.between(0.90, 1.10)).sum()
        r.fail(C, "load profile voltage out of range", f"{bad} records")

    # Load profile power factor
    lppf = lp["power_factor"]
    if lppf.between(0.80, 1.00).all():
        r.ok(C, f"load profile PF: [{lppf.min():.3f}, {lppf.max():.3f}]")
    else:
        bad = (~lppf.between(0.80, 1.00)).sum()
        r.fail(C, "load profile PF out of range", f"{bad} records")

    # Weather temperature
    wt = wx["temperature_f"]
    if wt.between(25, 135).all():
        r.ok(C, f"weather temp: [{wt.min():.1f}, {wt.max():.1f}] F")
    else:
        r.fail(C, "weather temp out of range", f"[{wt.min():.1f}, {wt.max():.1f}]")

    # Weather GHI
    ghi = wx["ghi_w_per_m2"]
    if ghi.between(0, 1200).all():
        r.ok(C, f"weather GHI: [{ghi.min():.0f}, {ghi.max():.0f}] W/m2")
    else:
        r.fail(C, "GHI out of range")

    # CID power factor
    cidpf = cid["power_factor"]
    if cidpf.between(0.80, 1.00).all():
        r.ok(C, f"cid PF: [{cidpf.min():.3f}, {cidpf.max():.3f}]")
    else:
        bad = (~cidpf.between(0.80, 1.00)).sum()
        r.fail(C, "cid PF out of range", f"{bad} records")

    # CID energy = demand * 0.25
    energy_calc = cid["demand_kw"] * 0.25
    energy_diff = (cid["energy_kwh"] - energy_calc).abs()
    if energy_diff.max() < 0.01:
        r.ok(C, "cid energy_kwh = demand_kw * 0.25 (consistent)")
    else:
        bad = (energy_diff >= 0.01).sum()
        r.warn(C, "cid energy/demand mismatch", f"{bad} records, max diff={energy_diff.max():.4f}")

    # Edge impedance positive
    if (edges["impedance_r_ohm_per_mile"] > 0).all():
        r.ok(C, "edge impedance R all positive")
    else:
        r.fail(C, "edge impedance R <= 0", f"{(edges['impedance_r_ohm_per_mile'] <= 0).sum()} edges")

    if (edges["impedance_x_ohm_per_mile"] > 0).all():
        r.ok(C, "edge impedance X all positive")
    else:
        r.fail(C, "edge impedance X <= 0", f"{(edges['impedance_x_ohm_per_mile'] <= 0).sum()} edges")

    # Edge length consistency
    len_diff = (edges["length_ft"] - edges["length_miles"] * 5280).abs()
    max_len_diff = len_diff.max()
    if max_len_diff < 1.0:
        r.ok(C, f"edge length_ft = length_miles*5280 (max diff={max_len_diff:.2f} ft)")
    else:
        r.warn(C, "edge length unit mismatch", f"max diff={max_len_diff:.1f} ft")

    # Transformer secondary voltage
    sec_v = set(xfmrs["secondary_voltage_v"].unique())
    expected_sec = {120, 208, 240, 480}
    if sec_v <= expected_sec:
        r.ok(C, f"transformer secondary voltages: {sorted(sec_v)}")
    else:
        r.warn(C, "unexpected secondary voltages", str(sec_v - expected_sec))

    # Solar azimuth (south-facing for Phoenix)
    az = solar["azimuth_deg"]
    if az.between(130, 230).all():
        r.ok(C, f"solar azimuth: [{az.min():.0f}, {az.max():.0f}] deg (south-facing)")
    else:
        bad = (~az.between(130, 230)).sum()
        r.warn(C, "solar azimuth out of south-facing range", f"{bad} installations")

    # Solar tilt
    tilt = solar["tilt_deg"]
    if tilt.between(10, 45).all():
        r.ok(C, f"solar tilt: [{tilt.min():.0f}, {tilt.max():.0f}] deg")
    else:
        r.warn(C, "solar tilt range", f"[{tilt.min():.0f}, {tilt.max():.0f}]")

    # ── Category 9: Growth Scenarios ──
    C = "9. Growth Scenarios"
    gs_reset = gs.reset_index()
    n_scen = gs_reset["scenario_id"].nunique()
    if n_scen == 5:
        r.ok(C, f"5 unique scenarios: {sorted(gs_reset['scenario_id'].unique())}")
    else:
        r.fail(C, f"expected 5 scenarios, got {n_scen}")

    years_per = gs_reset.groupby("scenario_id")["year"].apply(lambda x: sorted(x.unique()))
    expected_years = list(range(2024, 2041))
    all_years_ok = True
    for sid, yrs in years_per.items():
        if yrs != expected_years:
            all_years_ok = False
            r.fail(C, f"{sid} years", f"expected 2024-2040, got {yrs[0]}-{yrs[-1]} ({len(yrs)} years)")
    if all_years_ok:
        r.ok(C, "all scenarios cover 2024-2040 (17 years each)")

    # 2024 baseline
    baseline = gs_reset[gs_reset["year"] == 2024]
    ev_base = baseline["ev_adoption_pct"].unique()
    solar_base = baseline["solar_adoption_pct"].unique()
    batt_base = baseline["battery_adoption_pct"].unique()
    if len(ev_base) == 1 and abs(ev_base[0] - 8.0) < 1:
        r.ok(C, f"2024 EV baseline: {ev_base[0]}%")
    else:
        r.warn(C, "2024 EV baseline", f"values: {ev_base}")
    if len(solar_base) == 1 and abs(solar_base[0] - 12.0) < 1:
        r.ok(C, f"2024 solar baseline: {solar_base[0]}%")
    else:
        r.warn(C, "2024 solar baseline", f"values: {solar_base}")

    # Monotonic growth
    for col in ["ev_adoption_pct", "solar_adoption_pct", "battery_adoption_pct"]:
        mono_ok = True
        for sid in gs_reset["scenario_id"].unique():
            vals = gs_reset[gs_reset["scenario_id"] == sid].sort_values("year")[col].values
            if not all(vals[i] <= vals[i+1] for i in range(len(vals)-1)):
                mono_ok = False
                break
        if mono_ok:
            r.ok(C, f"{col} monotonically non-decreasing")
        else:
            r.fail(C, f"{col} not monotonic", f"scenario {sid}")

    # Baseline matches actual penetration
    actual_solar_pct = custs["has_solar"].mean() * 100
    actual_ev_pct = custs["has_ev"].mean() * 100
    actual_batt_pct = custs["has_battery"].mean() * 100
    for name, actual, baseline_val in [
        ("solar", actual_solar_pct, solar_base[0]),
        ("EV", actual_ev_pct, ev_base[0]),
        ("battery", actual_batt_pct, batt_base[0]),
    ]:
        diff = abs(actual - baseline_val)
        if diff < 2:
            r.ok(C, f"2024 {name} baseline matches actual ({actual:.1f}% vs {baseline_val:.1f}%)")
        else:
            r.warn(C, f"2024 {name} baseline mismatch",
                   f"actual={actual:.1f}%, scenario={baseline_val:.1f}%, diff={diff:.1f}pp")

    # ── Category 10: Profile Data ──
    C = "10. Profile Data"
    # Solar profiles: 12 months
    sp_months = sp["timestamp"].dt.month.nunique()
    if sp_months == 12:
        r.ok(C, "solar profiles cover 12 months")
    else:
        r.fail(C, "solar profiles months", f"found {sp_months}")

    # Nighttime gen = 0
    night = sp[sp["generation_pct_of_capacity"] == 0]
    night_ghi = sp[sp["ghi_w_per_m2"] == 0]
    if len(night) > 0:
        r.ok(C, f"solar profiles: {len(night)}/288 records have zero generation (nighttime)")
    else:
        r.warn(C, "solar profiles: no zero-generation records")

    # Peak generation > 50% in summer
    summer_sp = sp[sp["timestamp"].dt.month.isin([6, 7, 8])]
    if len(summer_sp) > 0:
        peak = summer_sp["generation_pct_of_capacity"].max()
        if peak > 50:
            r.ok(C, f"solar summer peak: {peak:.1f}%")
        else:
            r.warn(C, "solar summer peak low", f"{peak:.1f}%")

    # EV profiles: both day types
    day_types = set(evp["day_type"].unique())
    if "weekday" in day_types and "weekend" in day_types:
        r.ok(C, f"EV profiles: both day types present ({day_types})")
    else:
        r.fail(C, "EV profiles missing day type", str(day_types))

    # EV values non-negative
    ev_cols = ["residential_load_pct", "commercial_load_pct", "dcfc_load_pct"]
    ev_neg = sum((evp[c] < 0).sum() for c in ev_cols if c in evp.columns)
    if ev_neg == 0:
        r.ok(C, "EV profile values all non-negative")
    else:
        r.fail(C, "EV profile negative values", f"{ev_neg} records")

    # Print report
    r.summary()


if __name__ == "__main__":
    main()
