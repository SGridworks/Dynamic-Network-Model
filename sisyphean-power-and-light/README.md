# Sisyphean Power & Light: V2 data and electrical studies

SP&L is entirely fictional. All assets, customers, observations, and geographic
coordinates are synthetic. These files support education and prototype studies;
they are not calibrated utility planning data.

The original registry is in `../demo_data/`. Use
`demo_data.load_demo_data.load_all()` from the repository root to combine the
original registry with these V2 files. See [DATA-QUALITY.md](../DATA-QUALITY.md)
for repair evidence, verification commands, and limitations.

## Current inventory

| Directory | Contents |
| --- | --- |
| `assets/` | 36,668 transformers with original registry geometry, phases and voltages plus synthetic health attributes; maintenance and switching examples |
| `outages/` | 3,746 events spanning 2020–2024, crew dispatch and reliability examples |
| `weather/` | 52,608 hourly observations spanning 2020–2025 |
| `timeseries/substation_load_hourly.parquet` | 349,440 feeder-hour records: four sampled seasonal weeks per year, 2020–2024, across 104 feeders |
| `timeseries/ami_15min_sample.parquet` | 336,000 intervals for 500 customers, July 15–21, 2024 |
| `generation/` | Boiler-feed-pump telemetry: 527,040 minute rows, 35,136 quarter-hour rows and 8,784 hourly rows; 88 columns |
| `wildfire/` | Eight synthetic wildfire datasets; see [wildfire/README.md](wildfire/README.md) |
| `network/` | Two complete radial feeders, FDR-0001 and FDR-0002, from Riverside SUB-001 |
| `scenarios/` | Four synthetic DER/stress scenario specifications |

The hourly filename is historical: records are keyed by **feeder**, not substation.
Gaps between sampled weeks are intentional. The converter does not fabricate
intervening hours. Demand is MW, reactive demand is Mvar, and voltage is per-unit.
Hourly MW/Mvar/voltage are source means; power factor is derived from hourly P/Q.
Class shares are synthetic time-of-day allocations.

## Electrical model

The current export has 1,064 lines, 521 distribution transformers, 1,587 buses,
and 2,475 circuit elements. `network/model_manifest.json` records exact coverage,
secondary connections, source reference hour and load-allocation weights.

The generator preserves explicit A/B/C connections and winding voltage conventions.
Inter-feeder ties are excluded to retain radial operation. One export must contain
feeders at one substation and voltage level. The default includes both feeders
completely; it does not truncate a list of 12 feeders at an arbitrary line count.

Loads reproduce the selected reference hour's feeder MW/Mvar, allocated by
customer contracted-demand weights. That allocation is an explicit synthetic
assumption, not a calibration to transformer measurements. PV and storage use
the matching transformer secondary voltage and phases.

The reference snapshot converges, but some source DER capacities greatly exceed
their transformer ratings. Those constraints remain visible. Numerical convergence
does not establish electrical feasibility.

## Reproduce

From the repository root, in an environment with `requirements-data.txt` installed:

```bash
python convert_transformer_data.py
python convert_load_profiles.py
python convert_customer_intervals.py
python validate_demo_data.py
python generate_opendss_model.py
python run_powerflow.py
python run_scenarios.py
python run_qsts.py
python run_hosting_capacity.py
python -m pytest tests/
```

QSTS uses each feeder's observed MW/Mvar and four complete 2024 seasonal weeks.
Missing hours cause an error. Solar shapes cover all 8,784 leap-year hours.
Power-flow summaries distinguish phase violations from bus counts.

Hosting-capacity studies refuse to grant additional capacity when the base circuit
already violates voltage or thermal limits. Rows marked `base_case_infeasible`
require engineering remediation before a hosting-capacity study can proceed.
The original all-transformer hosting table in `demo_data/` is a separate synthetic
screening proxy, not the result of these OpenDSS solves.

Historical notebook outputs and older test reports are examples from earlier
dataset versions. Regenerate results and rerun a notebook before treating its
displayed values as current.
