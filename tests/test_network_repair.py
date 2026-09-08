"""Electrical regression checks, runnable with unittest in an OpenDSS environment."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

try:
    import opendssdirect as dss
except ImportError:
    dss = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODEL = ROOT / "sisyphean-power-and-light/network"


@unittest.skipIf(dss is None, "OpenDSS environment required")
class NetworkRepairTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((MODEL / "model_manifest.json").read_text())
        dss.Text.Command(f'compile "{MODEL / "master.dss"}"')

    def test_complete_feeders_and_no_unenergized_phases(self):
        edges = pd.read_csv(ROOT / "demo_data/network_edges.csv")
        expected = edges[edges.feeder_id.isin(self.manifest["feeders"]) & edges.edge_type.ne("tie")]
        self.assertEqual(dss.Lines.Count(), len(expected))
        self.assertTrue(dss.Solution.Converged())
        self.assertTrue(np.isfinite(dss.Circuit.AllBusMagPu()).all())
        self.assertGreater(min(dss.Circuit.AllBusMagPu()), 0.1)
        for row in expected.itertuples():
            dss.Lines.Name(f"line_{row.edge_id}")
            suffix = "." + ".".join(str("ABC".index(p) + 1) for p in row.phase)
            self.assertTrue(dss.Lines.Bus1().endswith(suffix))
            self.assertTrue(dss.Lines.Bus2().endswith(suffix))

    def test_transformer_and_der_voltage_ratings_match_connections(self):
        for xid, c in self.manifest["connections"].items():
            dss.Transformers.Name(xid)
            dss.Transformers.Wdg(2)
            self.assertAlmostEqual(dss.Transformers.kV(), c["kv"])
            dss.Circuit.SetActiveElement(f"Transformer.{xid}")
            self.assertEqual(dss.CktElement.NumPhases(), c["phases"])
        for collection, prefix in ((dss.PVsystems, "pv_"), (dss.Storages, "batt_")):
            idx = collection.First()
            while idx:
                xid = collection.Name()[len(prefix):].upper()
                c = self.manifest["connections"][xid]
                self.assertAlmostEqual(float(dss.Properties.Value("kV")), c["kv"])
                self.assertEqual(dss.CktElement.BusNames()[0].lower(), c["bus"].lower())
                idx = collection.Next()

    def test_base_load_matches_reference_feeder_demand(self):
        profiles = pd.read_parquet(ROOT / "sisyphean-power-and-light/timeseries/substation_load_hourly.parquet")
        reference = profiles[profiles.timestamp.eq(pd.Timestamp(self.manifest["reference_hour"]))].set_index("feeder_id")
        for feeder in self.manifest["feeders"]:
            kw = kvar = 0.0
            for xid, c in self.manifest["connections"].items():
                if c["feeder_id"] == feeder:
                    dss.Loads.Name(f"load_{xid}")
                    kw += dss.Loads.kW()
                    kvar += dss.Loads.kvar()
            self.assertAlmostEqual(kw, reference.loc[feeder, "total_load_mw"] * 1000, places=4)
            self.assertAlmostEqual(kvar, reference.loc[feeder, "load_mvar"] * 1000, places=4)

    def test_summary_uses_phase_extrema(self):
        from run_powerflow import build_summary, extract_bus_voltages

        summary = build_summary(extract_bus_voltages())
        self.assertAlmostEqual(summary["v_min"], min(dss.Circuit.AllBusMagPu()), places=4)
        self.assertEqual(summary["phases_under_095"], sum(v < .95 for v in dss.Circuit.AllBusMagPu()))

    def test_invalid_base_cannot_claim_positive_hosting_capacity(self):
        from run_hosting_capacity import sweep_transformer

        xid, c = next(iter(self.manifest["connections"].items()))
        result, _ = sweep_transformer(MODEL / "master.dss", xid, c["kva"])
        self.assertFalse(result["base_case_feasible"])
        self.assertEqual(result["hc_kw"], 0)
        self.assertEqual(result["limiting_factor"], "base_case_infeasible")

    def test_qsts_requires_observed_hours_and_uses_each_feeder(self):
        from run_qsts import load_feeder_profiles, load_solar_profile, run_qsts_season

        profiles = load_feeder_profiles(self.manifest["feeders"])
        solar = load_solar_profile()
        self.assertEqual(len(solar), 8784)
        with self.assertRaisesRegex(ValueError, "Missing feeder hours"):
            run_qsts_season(MODEL, profiles.iloc[:0], solar, "fall", "2024-10-14", 1)
        result = run_qsts_season(MODEL, profiles, solar, "winter", "2024-01-15", 1)
        expected = profiles[profiles.timestamp.eq(pd.Timestamp("2024-01-15"))].total_load_mw.sum() * 1000
        self.assertAlmostEqual(result[0]["gross_load_kw"], expected, places=4)

    def test_hosting_capacity_returns_last_passing_step(self):
        from run_hosting_capacity import sweep_transformer

        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory)
            (model / "master.dss").write_text(
                "Clear\nNew Circuit.test bus1=source basekv=12.47 pu=1 phases=3\n"
                "New Transformer.XFMR-TEST phases=1 windings=2 "
                "buses=[source.1.0 bus_XFMR-TEST_sec.1.0] conns=[wye wye] "
                "kvs=[7.1995578568 0.24] kvas=[10 10] XHL=2.5\n"
                "Set voltagebases=[12.47 0.4156921938]\nCalcVoltageBases\nSolve\n"
            )
            (model / "model_manifest.json").write_text(json.dumps({"connections": {
                "XFMR-TEST": {"bus": "bus_XFMR-TEST_sec.1", "phases": 1, "kv": 0.24}
            }}))
            try:
                result, curve = sweep_transformer(model / "master.dss", "XFMR-TEST", 10)
            finally:
                # OpenDSS changes CWD; leave the temporary model before cleanup.
                dss.Text.Command(f'compile "{MODEL / "master.dss"}"')
            self.assertTrue(result["base_case_feasible"])
            self.assertFalse(curve[-1]["feasible"])
            passing = [p["pv_kw"] for p in curve if p["feasible"]]
            self.assertAlmostEqual(result["hc_kw"], max(passing))
            self.assertLess(result["hc_kw"], curve[-1]["pv_kw"])


if __name__ == "__main__":
    unittest.main()
