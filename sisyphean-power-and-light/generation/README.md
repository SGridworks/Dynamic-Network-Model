# SP&L Generating Station 1 -- BFP Train Dataset

**Dataset Version:** 1.0
**Date:** February 25, 2026
**Parent Dataset:** Sisyphean Power & Light v2.0

---

## Overview

One year of 1-minute operational data for the Boiler Feed Pump (BFP) train at SP&L Generating Station 1. The dataset covers two 100% capacity motor-driven BFPs, their lube oil systems, mechanical seals, and the surrounding feedwater boundary conditions. Three embedded fault scenarios provide labeled degradation signatures for predictive maintenance and anomaly detection work.

---

## LEGAL DISCLAIMER -- SYNTHETIC DATA

**This dataset contains ENTIRELY SYNTHETIC data for educational purposes only.**

- All tag values, alarm logs, trip records, and equipment identifiers are computer-generated. No real plant data is included.
- Equipment model numbers (KSB CHTD 8/6, ABB AXR 500MK4) reference real product lines for educational realism but do not represent any installed equipment.
- SP&L Generating Station 1 is fictional. No power plant operates under this name.
- Not for operational use, equipment sizing, or procurement decisions.

**For questions or concerns:** adam@sgridworks.com

---

## System Description

SP&L Generating Station 1 is a 300 MW 2x1 combined-cycle gas turbine (CCGT) plant consisting of two GE 7F gas turbines and one steam turbine. The BFP train feeds the HP drum of the single-pressure HRSG.

| Parameter | Value |
|-----------|-------|
| Plant designation | SP&L Generating Station 1 (Unit 1) |
| Configuration | 2x1 CCGT |
| Rated output | 300 MW gross |
| Minimum stable load | 100 MW |
| Gas turbines | 2x GE 7F, 105 MW each |
| Steam turbine | 1x, 100 MW |
| HP drum pressure | 130 bar(g) |
| HP steam temperature | 565 C |
| Deaerator pressure | 7.0 bar(g) |
| Deaerator temperature | 165 C |

---

## System Boundary

The dataset boundary runs from suction isolation valves to discharge isolation valves for each BFP. The deaerator (DA) is upstream and outside the boundary. HP heaters and the HRSG drum are downstream and outside the boundary. DA pressure, temperature, and level are included as boundary inputs.

```
                         SYSTEM BOUNDARY
                 ........................................
                 :                                      :
                 :    +----------+      +----------+    :
                 :    |  BFP-A   |      |  BFP-A   |    :
    DA           :    | SUCTION  |----->|   PUMP   |---------+    :
    STORAGE  ====+===>|  VALVE   |      | 8-stage  |    :    |    :
    TANK     |   :    +----------+      +----+-----+    :    |    :
  (outside)  |   :         |    LO SKID A    |          :    |    :
             |   :         |   +---------+   |          :    |    :
             |   :         +---|  MOTOR   |---+          :    |    :
             |   :             | 1800 kW  |             :    |    :
             |   :             +---------+              :    |    :
             |   :                                      :    |    :
             |   :    +----------+      +----------+    :    |    :     HP HEATERS
             |   :    |  BFP-B   |      |  BFP-B   |    :    +--->====> & HRSG DRUM
             +===+===>| SUCTION  |----->|   PUMP   |---------+    :     (outside)
                 :    |  VALVE   |      | 8-stage  |    :         :
                 :    +----------+      +----+-----+    :         :
                 :         |    LO SKID B    |          :         :
                 :         |   +---------+   |          :         :
                 :         +---|  MOTOR   |---+          :         :
                 :             | 1800 kW  |             :         :
                 :             +---------+              :         :
                 :                                      :         :
                 :......................................:         :
                                                                  :
    Boundary inputs:           Boundary outputs:                  :
    - DA pressure              - FW header pressure               :
    - DA temperature           - FW header temperature            :
    - DA level                 - FW header flow                   :
    - Ambient temp             - Unit MW (gross & net)            :
    - CW supply temp                                              :
```

---

## Equipment Roster

### BFP Pumps (2x100%, A=duty, B=standby)

| Parameter | Value |
|-----------|-------|
| OEM / Model | KSB CHTD 8/6 |
| Type | Barrel-casing multistage centrifugal |
| Stages | 8 |
| Rated speed | 2985 RPM |
| Rated flow | 300 t/hr |
| BEP flow | 260 t/hr (100% BEP) |
| Minimum continuous flow | 75 t/hr |
| Rated differential pressure | 153 bar |
| Shutoff head | 180 bar |
| BEP efficiency | 80% |
| NPSH required at BEP | 19.3 m |
| Install year | 2019 |

### Drive Motors

| Parameter | Value |
|-----------|-------|
| OEM / Model | ABB AXR 500MK4 |
| Type | Squirrel-cage induction |
| Rated power | 1800 kW |
| Voltage | 6.6 kV |
| Rated current | 190 A |
| Power factor | 0.88 |
| Efficiency | 97% |
| Speed | 2985 RPM |

### Lube Oil Systems

| Parameter | Value |
|-----------|-------|
| OEM / Model | Bijur Delimon FLM-2200 |
| Type | Forced-feed lube oil skid |
| Normal header pressure | 1.4 -- 1.8 bar(g) |
| Low pressure alarm | 0.9 bar(g) |
| Low pressure trip | 0.6 bar(g) |
| Normal supply temperature | 42 -- 48 C |
| Normal return temperature | 55 -- 62 C |
| High temperature alarm | 68 C |

---

## Alarm and Trip Setpoints

| Measurement | Normal Range | Alarm | Trip |
|-------------|-------------|-------|------|
| Journal bearing temp | 60 -- 70 C | 85 C | 95 C |
| Thrust bearing temp | 65 -- 75 C | 95 C | 105 C |
| Motor bearing temp | 55 -- 68 C | 90 C | 100 C |
| Shaft vibration | 20 -- 40 um pk-pk | 80 um | 110 um |
| Axial displacement | -0.15 -- +0.15 mm | +/-0.3 mm | +/-0.5 mm |
| LO header pressure | 1.4 -- 1.8 bar(g) | 0.9 bar(g) | 0.6 bar(g) |
| LO temperature | 42 -- 48 C supply | 68 C | -- |
| Seal leakage | 0.5 -- 3.0 cc/min | 15 cc/min | -- |
| Seal temperature | 40 -- 55 C | 70 C | -- |

---

## Tag Naming Convention

All tags follow a flat PI-style convention:

```
U1_BFPA_TAGNAME
^^  ^^^^ ^^^^^^^
|   |    +-- Measurement identifier
|   +------- Equipment (BFPA, BFPB, or system-level)
+----------- Unit number
```

**Prefixes:**

| Prefix | Scope |
|--------|-------|
| `U1_BFPA_*` | BFP-A pump, motor, seals, lube oil (36 tags) |
| `U1_BFPB_*` | BFP-B pump, motor, seals, lube oil (36 tags) |
| `U1_*` | System / boundary tags (FW header, unit MW, DA, ambient) (14 tags) |

The full tag dictionary is in `tag_dictionary.csv` (88 tags total). Each entry includes description, engineering units, valid range, scan rate, and pump assignment.

---

## File Inventory

```
generation/
├── timeseries/
│   ├── bfp_train_1min.parquet      # 527,040 rows x 88 cols (1-minute intervals)
│   ├── bfp_train_15min.parquet     # 35,136 rows x 88 cols (15-minute rollup)
│   └── bfp_train_hourly.parquet    # 8,784 rows x 88 cols (hourly rollup)
│
├── events/
│   ├── alarm_log.csv               # 71 alarm events (ACTIVE/CLEARED pairs)
│   ├── trip_log.csv                # 1 trip event (BFP-B bearing trip)
│   └── operator_actions.csv        # 7 operator actions (start/stop/swap)
│
├── reference/
│   ├── pump_curves.csv             # 27-point H-Q, efficiency, power, NPSH curves
│   ├── heat_balance.csv            # 15-point unit load vs. BFP operating conditions
│   └── design_parameters.json      # Full equipment specs, setpoints, fault definitions
│
├── equipment_registry.csv          # 6 equipment records (2 pumps, 2 motors, 2 LO skids)
├── tag_dictionary.csv              # 88 tag definitions with units and ranges
└── README.md                       # This file
```

**Total files:** 11
**Timeseries records:** 527,040 (1-min) + 35,136 (15-min) + 8,784 (hourly) = 570,960

---

## Temporal Coverage

| Attribute | Value |
|-----------|-------|
| Start | 2024-01-01 00:00 |
| End | 2024-12-31 23:59 |
| Duration | 366 days (2024 is a leap year) |
| 1-minute rows | 527,040 |
| 15-minute rows | 35,136 |
| Hourly rows | 8,784 |
| Columns (all resolutions) | 88 |

---

## Embedded Fault Scenarios

Three fault signatures are embedded in the timeseries data with gradual onset ramps. These provide labeled windows for supervised learning and anomaly detection.

### SEAL-001: BFP-A DE Seal Degradation

| Attribute | Value |
|-----------|-------|
| Pump | A |
| Window | 2024-04-01 to 2024-06-01 |
| Duration | ~61 days |
| Mechanism | Gradual DE mechanical seal face wear |
| Observable in | `U1_BFPA_SEAL_DE_LEAK` (rising), `U1_BFPA_SEAL_DE_TEMP` (rising) |
| Outcome | Planned swap to BFP-B on Jun 1 for seal replacement |

### BRG-001: BFP-B NDE Bearing Wear

| Attribute | Value |
|-----------|-------|
| Pump | B |
| Window | 2024-07-15 to 2024-08-20 |
| Duration | ~36 days |
| Mechanism | Progressive NDE journal bearing babbitt wear |
| Observable in | `U1_BFPB_BRG_NDE_TEMP` (rising), `U1_BFPB_VIB_NDE_X/Y` (rising) |
| Outcome | Trip on Aug 20 at 96.2 C (trip setpoint 95 C). Emergency swap to BFP-A. |

### ALIGN-001: BFP-A Coupling Misalignment

| Attribute | Value |
|-----------|-------|
| Pump | A |
| Window | 2024-10-15 to 2024-12-31 |
| Duration | ~77 days |
| Mechanism | Post-outage thermal growth coupling misalignment |
| Observable in | `U1_BFPA_VIB_DE_X/Y` (rising 2x component), `U1_BFPA_BRG_DE_TEMP` (gradual rise) |
| Outcome | Slow degradation continues through year-end (open fault) |

### Transient Events

In addition to the three labeled fault windows, the data contains shorter transient disturbances:

- **Cavitation events** -- Low-load periods where suction conditions approach NPSH limits, visible in pressure oscillations
- **LO cooler degradation** -- Seasonal cooling water temperature rise (summer) affects lube oil return temperatures
- **Recirculation valve hunting** -- Intermittent recirc valve position oscillations during load transitions near minimum continuous flow

---

## SP&L Tie-In

This generation dataset is designed to integrate with the existing SP&L distribution-side data:

- **Unit MW tracks system demand.** The `U1_UNIT_MW_GROSS` and `U1_UNIT_MW_NET` tags follow the same diurnal and seasonal load patterns as the SP&L substation and feeder load data.
- **Timestamps align.** The 2024 calendar year overlaps with the load profile and AMI data in `sisyphean-power-and-light/timeseries/`.
- **Unit serves ~65% of SP&L demand.** At 300 MW rated capacity, Generating Station 1 supplies roughly 65% of SP&L's system peak. The remainder comes from purchased power and peakers.
- **Weather correlation.** `U1_AMBIENT_TEMP` and `U1_CW_SUPPLY_TEMP` correlate with `weather/hourly_observations.csv`, providing a generation-to-distribution weather link.

---

## Key Design Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Rated unit output | 300 MW gross | design_parameters.json |
| Minimum stable load | 100 MW | design_parameters.json |
| BFP rated flow | 300 t/hr | design_parameters.json |
| BFP BEP flow | 260 t/hr | design_parameters.json |
| BFP min continuous flow | 75 t/hr | design_parameters.json |
| BFP rated DP | 153 bar | design_parameters.json |
| BFP shutoff head | 180 bar | pump_curves.csv |
| BFP BEP efficiency | 80% | pump_curves.csv |
| Motor rated power | 1800 kW | design_parameters.json |
| Motor voltage | 6.6 kV | design_parameters.json |
| Motor rated current | 190 A | design_parameters.json |
| HP drum pressure | 130 bar(g) | design_parameters.json |
| DA pressure | 7.0 bar(g) | design_parameters.json |
| FW flow at 100% load | 250 t/hr | heat_balance.csv |
| BFP power at 100% load | 1354 kW | heat_balance.csv |

---

## Quick Start

### Load 1-Minute Data

```python
import pandas as pd

DATA_DIR = "/path/to/sisyphean-power-and-light/generation"

# Load the full 1-minute timeseries
df = pd.read_parquet(f"{DATA_DIR}/timeseries/bfp_train_1min.parquet")
print(f"Shape: {df.shape}")          # (527040, 88)
print(f"Range: {df.index.min()} to {df.index.max()}")

# Quick look at BFP-A operating point
cols_a = [c for c in df.columns if c.startswith("U1_BFPA_")]
print(df[cols_a].describe())
```

### Load Hourly Rollup (Faster for Exploration)

```python
df_hr = pd.read_parquet(f"{DATA_DIR}/timeseries/bfp_train_hourly.parquet")
print(f"Shape: {df_hr.shape}")       # (8784, 88)
```

### Load Tag Dictionary

```python
tags = pd.read_csv(f"{DATA_DIR}/tag_dictionary.csv")
print(tags[["tag_id", "description", "units"]].head(10))
```

### Load Design Parameters

```python
import json

with open(f"{DATA_DIR}/reference/design_parameters.json") as f:
    params = json.load(f)

print(f"BFP model: {params['bfp']['oem']} {params['bfp']['model']}")
print(f"Stages: {params['bfp']['stages']}")
print(f"Rated DP: {params['bfp']['rated_dp_bar']} bar")
```

### Isolate a Fault Window

```python
# Extract the BRG-001 bearing wear window
brg_fault = df.loc["2024-07-15":"2024-08-20"]
print(f"BRG-001 window: {brg_fault.shape[0]} rows")

# Plot NDE bearing temp trend
brg_fault["U1_BFPB_BRG_NDE_TEMP"].resample("1h").mean().plot(
    title="BFP-B NDE Bearing Temperature (BRG-001)"
)
```

---

## Data Generation

All data was programmatically generated using deterministic scripts with `random_state=42` for reproducibility. The generation process:

1. Computed unit MW load profiles from SP&L system demand curves (diurnal + seasonal)
2. Derived BFP operating conditions from heat balance relationships
3. Added realistic sensor noise, thermal lags, and measurement uncertainty
4. Injected fault degradation ramps per the three scenario definitions
5. Generated alarm and trip events from threshold crossings
6. Rolled up 1-minute data to 15-minute (mean) and hourly (mean) resolutions

---

## Known Limitations

- **Single operating mode.** Both BFPs are constant-speed, motor-driven. No variable-frequency drive behavior is modeled.
- **Simplified thermal model.** Bearing and seal temperatures use first-order lag models, not full FEA thermal networks.
- **No vibration spectral data.** Only overall vibration amplitudes are provided, not FFT spectra or orbit plots.
- **Flat boundary conditions.** DA pressure/temperature/level are modeled as slowly varying boundary inputs, not as a coupled dynamic system.
- **No water chemistry.** Feedwater conductivity, dissolved oxygen, pH, and silica are not included.
- **Planned outage is a gap.** The Sep 1--15 planned outage window has the unit offline (zero flows, ambient temperatures). No maintenance work order data is provided for the outage scope.

---

## Citation

```
SP&L Generating Station 1 - BFP Train Dataset v1.0
Sisyphean Gridworks, 2026
Part of: Sisyphean Power & Light Dataset v2.0
https://github.com/SGridworks/Dynamic-Network-Model
```

---

## Support

- **Issues:** https://github.com/SGridworks/Dynamic-Network-Model/issues
- **Email:** adam@sgridworks.com
- **Documentation:** https://sgridworks.com/ml-playground

---

*Dataset created 2026-02-25 as part of the SP&L generation-side expansion.*
