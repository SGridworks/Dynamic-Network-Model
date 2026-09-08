# SP&L data repair and verification

Verified locally on September 8, 2026. SP&L remains entirely synthetic.

## Dataset integrity

The combined loader exposes **31 tables and 4,174,868 rows**. The reduction from
8,173,460 rows removes empty hourly bins inserted between seasonal samples; it
does not discard observed demand.

| Defect | Repair |
| --- | --- |
| 35,018 transformers and 4,097,184 hourly rows assigned to incorrect substations | Join the actual feeder registry; unknown IDs raise an error |
| Transformer conversion discarded geometry, phases, and voltages | Preserve V1 registry attributes by transformer ID; retain V2 health enrichment unchanged |
| 3,998,592 empty hourly bins | Group only observed hours; require four unique quarter-hour readings per hour |
| Loader replaced reactive demand and voltage with generated values tied to a stored DSS run | Preserve source hourly MW/Mvar/voltage; derive power factor consistently from P/Q |
| AMI sample referenced an older customer hierarchy and classes | Rebuild July 15–21, 2024 from the current V1 interval corpus |
| Validator missed valid-but-wrong foreign keys and returned success after failure | Check cross-table membership, finite electrical values, unique intervals and class balance; return nonzero on failure |

The hourly table now contains **349,440 populated records**: 104 feeders × five
years × four seasonal weeks × 168 hours. These are sampled windows, not continuous
history. The AMI sample remains **336,000 readings for 500 customers over one week**.
MW averages preserve energy when multiplied by interval duration; gaps must not
be treated as zero demand or silently interpolated across seasons.

## Electrical export and study corrections

The default model now includes **both FDR-0001 and FDR-0002 completely**: 1,064
lines, 521 distribution transformers, 1,587 buses, 2,475 elements and 2,772 phase
nodes. The old export selected 12 feeder IDs, truncated to 1,000 lines, and actually
contained one complete feeder and part of a second.

The exporter now preserves A/B/C connections, uses correct single-phase winding
voltage conventions, supplies explicit PV/storage voltage ratings, and derives
source voltage/capacity from the substation registry. Its manifest records the
coverage and every secondary connection. Feeder MW/Mvar for the reference hour
(January 15, 2024 at noon) is allocated by customer contracted-demand weights.
This allocation is an explicit synthetic assumption; it is not transformer-level
measurement calibration.

Scenario customer counts now use exported transformer membership. Scenario DSS
files use relative paths and reuse the repaired base equipment definitions. QSTS
uses each feeder's observed MW/Mvar independently, rejects missing hours, starts
the fall sample on October 15, and includes all 8,784 solar-shape hours in leap
year 2024. Signed source power preserves net export. Phase and bus violation
counts are separate.

Hosting-capacity sweeps use the actual secondary connection, check absolute
voltage and thermal limits, and return the last passing injection step. A base
case that already violates limits cannot receive a positive capacity allowance.

Winding voltage conventions follow the
[DSS-Extensions transformer specification](https://dss-extensions.org/dss-format/Transformer.html).

## Verified results and remaining model limits

- General dataset validator: **189 PASS, 0 FAIL, 2 WARN**.
- Data/wildfire regression tests: **47 passed**.
- OpenDSS regression tests: **7 passed**, executed in an OpenDSS-enabled environment.
- Hermes example tests: **109 passed** in the example's existing environment.
- QSTS: **672/672 snapshots converged**, no missing result values.
- Four scenario solves converged; convergence does not mean constraints are satisfied.
- Base model: **5 buses / 8 phases below 0.95 pu**, minimum **0.8496 pu**, maximum
  **1.0356 pu**, and no unenergized phase values.

The two data warnings are intentional coverage/interpretation limits: AMI covers
only summer, and some sums of customer **contracted** kW exceed transformer kVA.
Contracted demand is not coincident apparent loading; the ratio alone is not an
overload result.

The remaining electrical violations reflect constraints in the synthetic inputs.
For example, XFMR-000184 is rated 10 kVA and has a 255.4 kW active PV installation;
XFMR-000491 is rated 15 kVA and has 294 kW of active PV. These records were not
arbitrarily resized or removed to force a clean solve. Consequently, all 521
power-flow hosting rows are explicitly marked **base_case_infeasible** with zero
additional allowance. This means a capacity conclusion is withheld pending
engineering remediation, not that zero is a certified hosting capacity.

The separate 36,668-row V1 hosting-capacity table is a synthetic screening proxy.
It must not be presented as an OpenDSS-validated capacity result. Historical
notebook outputs and older comprehensive test reports have not been regenerated;
rerun them before interpreting their displayed results as current.

## Reproduce from a clean checkout

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-data.txt
python validate_demo_data.py
python -m pytest tests/ -q
```

Rebuild the repaired V2 data and electrical artifacts:

```bash
python convert_transformer_data.py
python convert_load_profiles.py
python convert_customer_intervals.py
python generate_opendss_model.py
python run_powerflow.py
python run_scenarios.py
python run_qsts.py
python run_hosting_capacity.py
```

The dataset CI workflow runs validation and regressions on dataset changes.
Regeneration overwrites derived artifacts; preserve a backup when comparing
against earlier study runs.
