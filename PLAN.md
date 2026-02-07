# Digital Twin Light: Scenario Planning Engine — PLAN (FINAL)

## Status: ALL REQUIREMENTS LOCKED — 30/30 Questions Answered

---

## 1. Project Vision

A lightweight but scalable distribution system power flow model for scenario planning. Not a full digital twin requiring years of data curation, but a pragmatic model calibrated against real utility data (AMI/SCADA) that can stress-test distribution feeders against EV adoption, BTM solar growth, extreme weather, and policy changes.

**Philosophy:** AI accelerates analysis; engineers drive strategy.

**Scale Target:** 1,000 feeders (~50K–100K distribution transformers, ~500K–1M AMI meters).

**Deployment Model:** Single-utility private instances. Workstation-first (Phase 1), cloud optional later.

---

## 2. Complete Requirements Summary

### A. Data Ingestion

| Source | Formats | Details |
|--------|---------|---------|
| **GIS** | Shapefiles, GeoJSON, CSV (Esri/ArcGIS), file geodatabase (.gdb) | All feeder assets: poles, conductors, transformers, switches, meters, capacitors, regulators |
| **CYME** | CYME XML, `.mdb` database, CYMDIST text exports | Per-feeder and system-wide models. **Also source for conductor/transformer equipment libraries** (impedance, ampacity, kVA ratings). Import existing CYME study results for validation baseline. |
| **OMS** | CSV dump or Excel (platform-agnostic) | Primary/secondary cause codes, total CI & CMI, start/stop times, recovery steps, device operated |
| **AMI/SCADA** | 15-minute intervals at meter level | Auto-aggregate: meter → transformer → feeder. **Meter-to-transformer mapping inferred spatially** (GIS proximity + connectivity) in most cases. |
| **Weather** | Free API (Open-Meteo recommended) | Historical (for calibration) + forward-looking scenario data |

### B. Power Flow Engine

| Requirement | Decision |
|-------------|----------|
| **Solver** | OpenDSS (primary, via `opendssdirect.py`) — free, purpose-built for distribution |
| **Fidelity** | Full unbalanced 3-phase |
| **Simulation mode** | 8760 hourly QSTS (quasi-static time-series) |
| **Output metrics** | Thermal overloads, voltage violations (ANSI A/B), losses, hosting capacity, SAIDI/SAIFI |
| **Hosting capacity method** | **Stochastic (Monte Carlo) + EPRI DRIVE methodology** |
| **Validation** | Import existing CYME study results, compare against OpenDSS output on same feeder |

### C. Scenarios

| Requirement | Decision |
|-------------|----------|
| **EV charging** | **Built-in Level 1/2/3 charging profiles** with configurable parameters per client. User can also import custom profiles. |
| **EV & Solar curves** | User-provided adoption forecasts + sensitivity analysis (adjust penetration %, spatial allocation, timing) |
| **Scenario stacking** | Yes — compose EV + solar + weather + policy simultaneously |
| **Policy modeling** | TOU rate load-shape shifts, electrification mandates, interconnection rule changes |

### D. Architecture & Deployment

| Requirement | Decision |
|-------------|----------|
| **Language** | Python 3.11+ |
| **UI** | Web dashboard (map-based with layered GIS overlay) |
| **Deployment** | **Workstation-only in Phase 1** (Docker). Cloud optional in later phases. |
| **Database** | PostgreSQL + PostGIS + TimescaleDB |
| **AI approach** | Classical ML models (not LLM conversational) |
| **Data refresh** | One-time or periodic batch load (not real-time streaming) |
| **Visualization** | Map-based GIS overlay with user-configurable layers |
| **Authentication** | Simple local login (username/password) |
| **Multi-tenancy** | No — single-utility private instance |
| **Equipment libraries** | Parsed from CYME models (conductor types, transformer specs) |
| **Priority** | **Data ingestion first** (Phase 1) |

### E. AI / ML Capabilities (Full Suite)

**Core ML modules:**
1. **Load disaggregation** — Separate BTM solar generation from net metered AMI data
2. **Load forecasting** — Predict peak loads under weather scenarios
3. **Anomaly detection** — Flag bad/missing AMI and SCADA data quality issues
4. **Natural language scenario queries** — "Show me the 3 worst feeders if EV penetration doubles"
5. **Automated reporting / insight generation** — ML-generated planning study narratives
6. **Automated model calibration** — Tune OpenDSS model parameters to minimize error vs. SCADA. Bayesian optimization.
7. **Load clustering & segmentation** — Cluster transformers/feeders by load shape (k-means, DTW). Feeder archetypes.
8. **DER hosting capacity surrogate** — ML proxy trained on OpenDSS results for real-time what-if without full simulation.
9. **Outage risk scoring** — Weather + age + loading + OMS history → failure probability. Gradient boosting.
10. **Optimal mitigation ranking** — Rank fixes (reconductor, cap bank, new xfmr, battery) by cost-effectiveness.
11. **Load growth trend detection** — Changepoint detection on AMI time-series. Early warning.
12. **Asset degradation modeling** — IEEE C57.91 transformer thermal aging → remaining useful life.
13. **Scenario recommendation engine** — Suggest high-value scenarios based on system characteristics.
14. **Spatial correlation engine** — DBSCAN to cluster violations geographically, find systemic vs. isolated issues.
15. **Weather-load regression** — Feeder-specific temperature-to-load models for precise heatwave scenarios.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                          DATA INGESTION LAYER                               │
│                                                                             │
│  ┌──────────────┐ ┌───────────────┐ ┌────────────┐ ┌──────────────────────┐│
│  │  GIS Parser   │ │  CYME Parser  │ │ OMS Parser │ │   AMI Processor      ││
│  │              │ │               │ │            │ │                      ││
│  │ • Shapefile  │ │ • XML         │ │ • CSV      │ │ • 15-min meter data  ││
│  │ • GeoJSON   │ │ • .mdb        │ │ • Excel    │ │ • Spatial inference  ││
│  │ • CSV       │ │ • CYMDIST text│ │            │ │   of meter→xfmr     ││
│  │ • GDB       │ │               │ │ Fields:    │ │   mapping (GIS prox- ││
│  │              │ │ Also extracts:│ │ cause codes│ │   imity + connectiv.)││
│  │ All feeder  │ │ • Equipment   │ │ CI/CMI     │ │ • Auto-aggregate:   ││
│  │ assets +    │ │   libraries   │ │ times      │ │   meter→xfmr→feeder ││
│  │ coordinates │ │   (conductors,│ │ recovery   │ │ • Parallel chunk    ││
│  │              │ │   xfmr specs)│ │ device     │ │   processing (dask) ││
│  │ geopandas   │ │ • Validation  │ │            │ │                      ││
│  │ + fiona     │ │   baseline    │ │ pandas +   │ │ pandas + dask        ││
│  │              │ │   (study      │ │ openpyxl   │ │                      ││
│  │              │ │   results)    │ │            │ │                      ││
│  └──────┬───────┘ └──────┬────────┘ └─────┬──────┘ └──────────┬───────────┘│
│         │                │               │                    │            │
│  ┌──────┴────────────────┴───────────────┴────────────────────┘            │
│  │                                                                         │
│  │  ┌──────────────────┐                                                   │
│  │  │  Weather Client  │  Open-Meteo API (free, no key)                   │
│  │  │  • Historical    │  • Hourly temp, humidity, wind, solar irradiance │
│  │  │  • Forecast      │  • Archive back to 1940                          │
│  │  └────────┬─────────┘                                                   │
│  │           │                                                             │
│  └───────────┼─────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                    UNIFIED NETWORK MODEL (UNM)                              │
│                    PostgreSQL + PostGIS + TimescaleDB                        │
│                                                                             │
│  ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────────────┐ │
│  │ Network Graph      │ │ Asset Registry    │ │ Time-Series Store         │ │
│  │                   │ │                   │ │                           │ │
│  │ • Feeder trees    │ │ • Conductors      │ │ • AMI profiles (by xfmr) │ │
│  │ • Connectivity    │ │ • Transformers    │ │ • SCADA measurements     │ │
│  │ • Topology        │ │ • Switches        │ │ • Weather history        │ │
│  │ • Phasing         │ │ • Capacitors      │ │                           │ │
│  │ • Geospatial      │ │ • Regulators      │ │ TimescaleDB hypertables  │ │
│  │   coordinates     │ │ • Meters          │ │                           │ │
│  │                   │ │ • Poles           │ └───────────────────────────┘ │
│  │                   │ │ • Ratings         │                               │
│  └───────────────────┘ └───────────────────┘                               │
│                                                                             │
│  ┌───────────────────────────┐ ┌───────────────────────────────────────┐   │
│  │ Equipment Library          │ │ Meter-to-Transformer Map             │   │
│  │ (parsed from CYME)         │ │                                       │   │
│  │ • Conductor catalog        │ │ • Spatial proximity inference        │   │
│  │   (impedance, ampacity)   │ │ • Secondary connectivity validation  │   │
│  │ • Transformer catalog      │ │ • Manual override capability        │   │
│  │   (kVA, impedance, taps)  │ │ • Confidence scoring                 │   │
│  └───────────────────────────┘ └───────────────────────────────────────┘   │
│                                                                             │
│  ┌───────────────────────────┐ ┌───────────────────────────────────────┐   │
│  │ OMS History                │ │ CYME Validation Baseline              │   │
│  │ • Outage events → assets  │ │ • Imported CYME study results        │   │
│  │ • CI/CMI aggregation      │ │ • Voltage/loading per feeder         │   │
│  │ • Cause code analytics    │ │ • Used to validate OpenDSS conversion│   │
│  └───────────────────────────┘ └───────────────────────────────────────┘   │
│                                                                             │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                         ML / AI ENGINE                                      │
│                                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ Model Calibration   │  │ Load Disaggregation │  │ Load Forecasting    │ │
│  │ Bayesian optim.     │  │ CSSS / statistical  │  │ Temp→load regression│ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ Anomaly Detection   │  │ Load Clustering     │  │ DER Hosting         │ │
│  │ Isolation forest    │  │ k-means + DTW       │  │ Surrogate Model     │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ Outage Risk Scoring │  │ Mitigation Ranking  │  │ Growth Detection    │ │
│  │ XGBoost classifier  │  │ Cost-benefit optim. │  │ Changepoint / ARIMA │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ Asset Degradation   │  │ Spatial Correlation │  │ Scenario Recommender│ │
│  │ IEEE C57.91         │  │ DBSCAN clustering   │  │ Rule-based + ML     │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│  ┌─────────────────────┐  ┌─────────────────────┐                          │
│  │ NL Query Engine     │  │ Weather-Load Regr.  │                          │
│  │ spaCy → structured  │  │ Per-feeder models   │                          │
│  └─────────────────────┘  └─────────────────────┘                          │
│                                                                             │
│  Libraries: scikit-learn, XGBoost, statsmodels, Prophet, tslearn, spaCy    │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                        SCENARIO ENGINE                                      │
│                                                                             │
│  Composable, stackable scenario layers:                                     │
│                                                                             │
│  ┌────────────────┐  ┌───────────────┐  ┌───────────────┐  ┌────────────┐  │
│  │  EV Growth     │  │  BTM Solar    │  │  Weather      │  │  Policy    │  │
│  │                │  │  Growth       │  │  Extreme      │  │  Changes   │  │
│  │ BUILT-IN       │  │ User curves   │  │ Historical    │  │ TOU shifts │  │
│  │ PROFILES:      │  │ + sensitivity │  │ extremes or   │  │ Electrific.│  │
│  │ • Level 1      │  │ sweeps        │  │ synthetic     │  │ Interconn. │  │
│  │   (1.4kW)     │  │               │  │ heatwaves     │  │ rules      │  │
│  │ • Level 2      │  │ Spatial alloc │  │               │  │            │  │
│  │   (7.2kW)     │  │ by xfmr/fdr/  │  │ Weather→load │  │ Load shape │  │
│  │ • DCFC L3      │  │ customer class│  │ regression    │  │ transform  │  │
│  │   (50–350kW)  │  │               │  │               │  │            │  │
│  │ + configurable │  │               │  │               │  │            │  │
│  │   per client  │  │               │  │               │  │            │  │
│  │ + custom CSV  │  │               │  │               │  │            │  │
│  └───────┬────────┘  └───────┬───────┘  └───────┬───────┘  └─────┬──────┘  │
│          │                  │                  │                 │          │
│          └──────────────────┴────────┬─────────┴─────────────────┘          │
│                                      │                                      │
│                             ┌────────▼────────┐                             │
│                             │  SCENARIO        │                            │
│                             │  COMPOSITOR      │                            │
│                             │  Stack + resolve │                            │
│                             │  → 8760 profiles │                            │
│                             │  per transformer │                            │
│                             └────────┬─────────┘                            │
│                                      │                                      │
│  Config: YAML/JSON scenario files                                           │
│  Sensitivity: Latin Hypercube / grid search parameter sweeps                │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                     POWER FLOW SOLVER                                       │
│                                                                             │
│  Engine: OpenDSS via opendssdirect.py                                       │
│  Mode: Full unbalanced 3-phase, 8760 hourly QSTS                           │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  UNM → OpenDSS Model Converter                                  │       │
│  │  • Translate canonical model → .dss scripts                     │       │
│  │  • Use equipment library from CYME (conductor/xfmr catalogs)    │       │
│  │  • Validate against imported CYME study results                  │       │
│  │  • Cache converted models                                       │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  Execution Engine (1,000 feeders — workstation Phase 1)          │       │
│  │  • Parallel via multiprocessing (all CPU cores)                  │       │
│  │  • ~15–30 min on 16-core workstation                            │       │
│  │  • Checkpointing + progress tracking                            │       │
│  │  • Priority queue (ML-ranked worst-case first)                  │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  Hosting Capacity Engine                                         │       │
│  │  • EPRI DRIVE methodology implementation                         │       │
│  │  • Stochastic / Monte Carlo DER placement                       │       │
│  │  • Iterate: add DER at random locations until violation          │       │
│  │  • Statistical distribution of hosting capacity per bus          │       │
│  │  • Configurable: # of Monte Carlo iterations, DER types/sizes   │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                    RESULTS & ANALYTICS                                      │
│                                                                             │
│  • Thermal overload analysis (% rating, hours, max, cumulative)            │
│  • Voltage violations (ANSI A/B, hours, worst bus, profile)                │
│  • System losses (kWh by feeder, % change, line vs. transformer)           │
│  • Hosting capacity (kW per bus, statistical distribution from MC)          │
│  • Reliability indices (SAIDI/SAIFI from OMS + simulated stress)           │
│  • Scenario diff (base vs. A vs. B — delta metrics, new violations)        │
│  • Asset risk ranking (closest to failure across all dimensions)            │
│                                                                             │
│  Results stored in PostgreSQL with feeder/asset/scenario indexing            │
│                                                                             │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                    WEB DASHBOARD                                            │
│                                                                             │
│  Backend: FastAPI        Frontend: React + MapLibre GL JS + deck.gl         │
│  Task Queue: Celery + Redis     Auth: Simple local login                    │
│  Deployment: Docker + docker-compose (workstation Phase 1)                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │  MAP VIEW (Primary) — Layered GIS overlay                       │        │
│  │                                                                 │        │
│  │  Base layer: Feeder geographic layout from GIS                  │        │
│  │                                                                 │        │
│  │  User-togglable layers:                                         │        │
│  │  • Thermal loading (color-coded: green → yellow → red)         │        │
│  │  • Voltage profile (gradient by bus)                            │        │
│  │  • Hosting capacity (kW remaining, from stochastic analysis)   │        │
│  │  • EV adoption overlay (allocated EV locations)                 │        │
│  │  • BTM solar overlay (allocated PV locations)                   │        │
│  │  • Outage history heatmap (OMS data)                            │        │
│  │  • Asset age / degradation (IEEE C57.91 loss-of-life)          │        │
│  │  • Outage risk score                                            │        │
│  │  • Scenario diff (delta from base case)                         │        │
│  │  • Load growth trend alerts                                     │        │
│  │  • Customer density / load density                              │        │
│  │                                                                 │        │
│  │  Interactions:                                                  │        │
│  │  • Click any asset → detail panel (time-series, ratings, OMS)  │        │
│  │  • Zoom to feeder / substation                                  │        │
│  │  • Filter by violation type / severity                          │        │
│  │  • Compare scenarios side-by-side (split map)                  │        │
│  │  • Add/remove/reorder layers                                    │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                             │
│  Other views: Scenario Builder, Simulation Manager, Results Dashboard,     │
│  Data Manager, Scenario Comparison, Asset Detail, Reports (PDF/CSV),       │
│  ML Insights panel                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Technology Stack

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Language** | Python 3.11+ | Power systems ecosystem, ML/data libs |
| **Power Flow** | OpenDSS via `opendssdirect.py` | Free, unbalanced 3-phase, native QSTS, EPRI standard |
| **GIS Parsing** | `geopandas` + `fiona` + `pyogrio` | All formats: shp, geojson, gdb, csv |
| **CYME Parsing** | Custom: `lxml` (XML), `mdbtools`/`pyodbc` (.mdb), regex (text) | No standard lib; must also extract equipment catalogs |
| **Data Processing** | `pandas` + `numpy` + `dask` (for AMI at scale) | Dask for out-of-core processing of ~1M meters |
| **Spatial Analysis** | `scipy.spatial` + PostGIS | Meter-to-transformer spatial inference (KDTree + connectivity) |
| **Weather API** | Open-Meteo | Free, no API key, hourly, historical back to 1940 |
| **Database** | PostgreSQL 16 + PostGIS 3.4 + TimescaleDB | Spatial queries + time-series hypertables |
| **Backend API** | FastAPI | Async, WebSocket for job progress, auto OpenAPI docs |
| **Frontend** | React 18 + TypeScript | Component-based, large ecosystem |
| **Map Engine** | MapLibre GL JS + deck.gl | Open-source WebGL, handles 100K+ features, layer system |
| **Charts** | Apache ECharts or Plotly.js | Time-series, bar charts, heatmaps |
| **Task Queue** | Celery + Redis | Long-running 8760 sims + Monte Carlo hosting capacity |
| **Parallel Compute** | `multiprocessing` (Phase 1 workstation) | 1,000 feeders feasible on 16 cores |
| **ML/AI** | scikit-learn, XGBoost, statsmodels, Prophet, tslearn, spaCy | Classical ML stack |
| **Containerization** | Docker + docker-compose | Workstation deployment, portable |
| **Auth** | Simple local login (Flask-Login or FastAPI auth) | Username/password, no SSO needed |
| **File Storage** | Local filesystem (Phase 1) | Uploaded files, OpenDSS model cache |

---

## 5. Database Schema (High-Level)

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ substations │────<│ feeders      │────<│ segments     │
│             │     │              │     │ (conductors) │
│ id          │     │ id           │     │ id           │
│ name        │     │ substation_id│     │ feeder_id    │
│ geom (point)│     │ name         │     │ from_node    │
│ voltage_kv  │     │ head_device  │     │ to_node      │
└─────────────┘     │ geom (line)  │     │ phase        │
                    └──────────────┘     │ conductor_type│ ──→ conductor_catalog
                                        │ length       │
                                        │ rating_amps  │
┌──────────────┐    ┌──────────────┐    │ geom (line)  │
│ transformers │───<│ meters       │    └──────────────┘
│              │    │              │
│ id           │    │ id           │    ┌───────────────────────┐
│ feeder_id    │    │ xfmr_id      │    │ conductor_catalog     │
│ xfmr_type ───│──→ │ customer_type│    │ (from CYME)           │
│ kva_rating   │    │ geom (point) │    │ id, name, r1, x1,    │
│ phase        │    │ mapping_conf │    │ r0, x0, ampacity,    │
│ impedance_%  │    │  (confidence │    │ gmr, diameter        │
│ geom (point) │    │   score)     │    └───────────────────────┘
│ install_date │    └──────────────┘
└──────────────┘                        ┌───────────────────────┐
                                        │ transformer_catalog   │
┌──────────────┐  ┌──────────────┐     │ (from CYME)           │
│ capacitors   │  │ regulators   │     │ id, name, kva,       │
│ id, feeder_id│  │ id, feeder_id│     │ impedance_%, r, x,   │
│ kvar, phase  │  │ bandwidth    │     │ no_load_loss,        │
│ control_type │  │ pt_ratio     │     │ tap_range, conn_type │
│ geom (point) │  │ reg_setting  │     └───────────────────────┘
└──────────────┘  │ geom (point) │
                  └──────────────┘     ┌───────────────────────┐
                                       │ ev_charging_profiles  │
┌──────────────────────────────────┐   │ (built-in + custom)   │
│ ami_readings (TimescaleDB)       │   │ id, name, level,      │
│ meter_id, timestamp, kw, kvar,   │   │ kw_rating, hourly_    │
│ voltage (15-min intervals)       │   │ shape[24], weekend_   │
├──────────────────────────────────┤   │ shape[24], seasonal   │
│ scada_readings (TimescaleDB)     │   └───────────────────────┘
│ device_id, timestamp, mw, mvar,  │
│ voltage, tap_position, status    │   ┌───────────────────────┐
├──────────────────────────────────┤   │ cyme_validation       │
│ weather_data (TimescaleDB)       │   │ feeder_id, bus_id,    │
│ station_id, timestamp, temp_f,   │   │ voltage_pu, loading_%,│
│ humidity, wind_mph, solar_ghi    │   │ source (cyme study)   │
├──────────────────────────────────┤   └───────────────────────┘
│ oms_events                       │
│ id, feeder_id, device_id,        │   ┌───────────────────────┐
│ start_time, end_time,            │   │ hosting_capacity      │
│ primary_cause, secondary_cause,  │   │ feeder_id, bus_id,    │
│ customers_interrupted, cmi,      │   │ scenario_id,          │
│ recovery_steps                   │   │ hc_kw_mean, hc_kw_p5, │
├──────────────────────────────────┤   │ hc_kw_p95,            │
│ scenarios                        │   │ limiting_factor,      │
│ id, name, config_yaml,           │   │ mc_iterations         │
│ created_at, status               │   └───────────────────────┘
├──────────────────────────────────┤
│ simulation_results               │
│ scenario_id, feeder_id, hour,    │
│ asset_id, metric_type,           │
│ value, violation_flag            │
└──────────────────────────────────┘
```

---

## 6. Phased Implementation Plan

### Phase 1: Foundation — Data Ingestion + Unified Network Model (PRIORITY)
**Goal:** Ingest all data sources into a canonical network model. This is the critical path.

| Module | Work Items | Key Libraries |
|--------|-----------|---------------|
| **Project scaffold** | Python project (pyproject.toml), Docker + docker-compose (PostgreSQL + PostGIS + TimescaleDB + Redis), alembic migrations, CI | Docker, alembic, pytest |
| **GIS parser** | Multi-format reader (shp, geojson, csv, gdb) → canonical asset tables with geospatial coordinates | geopandas, fiona, pyogrio |
| **CYME parser** | 3-format reader (XML, .mdb, CYMDIST text). Extract: network topology, phasing, loads, equipment. **Also extract conductor & transformer catalogs.** Import existing CYME study results for validation. | lxml, mdbtools/pyodbc, regex |
| **GIS ↔ CYME reconciler** | Match/merge GIS spatial assets with CYME electrical model nodes. Fuzzy spatial join + manual override UI. | PostGIS spatial join, fuzzywuzzy |
| **Meter-to-transformer mapper** | Spatial inference: find nearest transformer for each meter using GIS coordinates. Score confidence. Validate against secondary connectivity if available. Manual override. | scipy.spatial.KDTree, PostGIS |
| **OMS ingestion** | CSV/Excel → oms_events table, link to devices/feeders | pandas, openpyxl |
| **AMI ingestion** | 15-min meter data → TimescaleDB. Auto-aggregate to transformer level (using inferred mapping) and feeder level. Parallel chunk processing for scale. | dask, TimescaleDB |
| **Weather client** | Open-Meteo API client: historical backfill for service territory, on-demand fetch | httpx, asyncio |
| **Equipment library** | Conductor and transformer catalogs parsed from CYME, stored as reference tables | — |
| **Data validation** | Schema validation, completeness checks, summary reports, data quality dashboard | pydantic, great_expectations |

**Deliverable:** Upload GIS + CYME + OMS + AMI → populated PostgreSQL with validated network model, equipment libraries, meter-xfmr mapping, and CYME validation baseline.

### Phase 2: Power Flow Engine
**Goal:** Convert UNM to OpenDSS, run 8760 QSTS, validate against CYME.

| Module | Work Items |
|--------|-----------|
| **UNM → OpenDSS converter** | Generate `.dss` scripts from canonical model using CYME equipment catalogs (conductor impedances, xfmr specs). |
| **CYME validation pipeline** | Run OpenDSS on same feeders as imported CYME study. Compare voltage/loading at all buses. Report error metrics (RMSE, max deviation). Iterate until acceptable fidelity. |
| **Single-feeder QSTS runner** | Run one feeder × 8760 hours. Extract V, I, P, Q at all buses/branches. |
| **Parallel execution engine** | `multiprocessing` pool — one feeder per core. 1,000 feeders on 16 cores ≈ 15–30 min. |
| **Hosting capacity engine** | EPRI DRIVE methodology + stochastic Monte Carlo placement. Configurable iterations, DER types/sizes. |
| **Results extractor** | Parse OpenDSS output → structured results in PostgreSQL. |
| **Checkpointing** | Save partial results, resume on failure. |
| **Progress API** | WebSocket endpoint for real-time progress to UI. |

**Deliverable:** Validated OpenDSS models matching CYME within acceptable tolerance. Full-system 8760 QSTS + hosting capacity analysis.

### Phase 3: Scenario Engine
**Goal:** Composable scenarios with built-in EV profiles and sensitivity analysis.

| Module | Work Items |
|--------|-----------|
| **Scenario schema** | YAML/JSON config format for defining and stacking scenarios. |
| **EV growth module** | **Built-in charging profiles**: Level 1 (1.4 kW, 120V), Level 2 (7.2 kW, 240V), DCFC Level 3 (50–350 kW). Configurable per client (adjust kW, time-of-day distribution, weekday/weekend, seasonal). Also accept custom CSV profiles. Spatial allocation engine (by xfmr, feeder, customer class). |
| **BTM solar module** | User curves + sensitivity. Allocate to transformers. Weather-driven irradiance model for 8760 PV profiles. |
| **Weather scenario module** | Select historical extreme events from Open-Meteo archive, or generate synthetic heatwaves. Drive load via weather-load regression. |
| **Policy module** | TOU rate → load shape transformer. Electrification mandates → additive load. Interconnection rules → DER caps. |
| **Scenario compositor** | Stack layers, resolve conflicts, generate final 8760 profiles per transformer. |
| **Sensitivity engine** | Parameter sweep (Latin Hypercube or grid search). E.g., sweep EV penetration 10%–50% in 5% steps. |

**Deliverable:** "High EV (Level 2, 30%) + High Solar (20%) + 2023 Heatwave + New TOU" as one stacked scenario.

### Phase 4: ML/AI Engine
**Goal:** Classical ML models that accelerate analysis.

| Module | ML Technique | Priority |
|--------|-------------|----------|
| **Weather-load regression** | Per-feeder temp→load models | High (enables weather scenarios) |
| **Auto-calibration** | Bayesian optimization to match SCADA | High (improves model accuracy) |
| **Anomaly detection** | Isolation forest on AMI/SCADA | High (data quality) |
| **Load disaggregation** | Statistical decomposition (CSSS) | Medium (BTM solar) |
| **Load clustering** | k-means + DTW on load shapes | Medium (scenario allocation) |
| **Load growth detection** | Changepoint detection, ARIMA | Medium (early warning) |
| **DER surrogate model** | Gradient boosting trained on OpenDSS | Medium (interactive what-if) |
| **Outage risk scoring** | XGBoost classifier | Medium |
| **Asset degradation** | IEEE C57.91 thermal aging | Medium |
| **Mitigation ranking** | Cost-benefit optimization | Lower |
| **Spatial correlation** | DBSCAN on violation clusters | Lower |
| **Scenario recommender** | Rule-based + clustering | Lower |
| **NL query engine** | spaCy → structured queries | Lower |

**Deliverable:** ML models trained, integrated, surfacing insights.

### Phase 5: Web Dashboard + Map Visualization
**Goal:** Full web UI with layered map and all workflows.

| Module | Work Items |
|--------|-----------|
| **FastAPI backend** | REST API: data, scenarios, simulations, results, ML insights |
| **Auth** | Simple local login (username/password, session-based) |
| **Data Manager UI** | Upload/validate/manage GIS, CYME, OMS, AMI files |
| **Scenario Builder UI** | Create/edit scenarios, adjust EV profiles, configure sweeps, stack layers |
| **Simulation Manager UI** | Launch jobs, progress bar (WebSocket), queue management |
| **Map View** | MapLibre GL JS + deck.gl base map, feeder geometry from GIS |
| **Map layers** | Togglable: thermal, voltage, hosting capacity, EV, solar, outage heatmap, risk, degradation, scenario diff, growth alerts, customer density |
| **Asset detail panel** | Click asset → time-series charts, ratings, OMS history, hosting capacity |
| **Scenario comparison** | Split-map side-by-side or overlay; delta tables/charts |
| **Results dashboard** | Summary metrics, ranked violation lists, feeder scorecards |
| **Reports** | Export PDF/CSV summaries per feeder, per scenario |
| **ML insights panel** | Anomaly alerts, growth trends, risk scores, mitigation recommendations |

**Deliverable:** Docker-deployed web dashboard on workstation with full map visualization.

### Phase 6: Hardening & Production
**Goal:** Reliable, documented, ready for client deployment.

| Module | Work Items |
|--------|-----------|
| **Testing** | Unit tests, integration tests, CYME↔OpenDSS validation regression tests |
| **Performance** | DB query optimization, OpenDSS batch tuning, AMI aggregation performance |
| **Data pipeline** | Periodic batch refresh for AMI/SCADA (scheduled ETL) |
| **Monitoring** | Logging, error alerting, job health |
| **Documentation** | User guide, data format specs, API docs, deployment guide |
| **Cloud (optional)** | Docker → AWS ECS/Fargate for burst compute if needed |

---

## 7. Key Design Decisions & Implications

### Meter-to-Transformer Spatial Inference (Q24)
This is a non-trivial module. The approach:
1. Build KDTree from transformer GIS coordinates
2. For each meter, find K nearest transformers
3. Score by: distance, feeder membership, phase compatibility, secondary conductor connectivity (if available in GIS)
4. Assign with confidence score (high/medium/low)
5. Expose low-confidence mappings in UI for manual review
6. Allow manual override and bulk correction

### EPRI DRIVE + Stochastic Hosting Capacity (Q26)
This adds significant compute to Phase 2. The approach:
1. For each feeder, define DER size/type distribution
2. Monte Carlo: randomly place DER at N locations, run power flow, check for violations
3. Repeat M iterations (configurable, e.g., 100–500)
4. Result: statistical distribution of hosting capacity per bus (mean, P5, P95)
5. Limiting factor identification (thermal vs. voltage)
6. DRIVE-compliant output format

### Built-in EV Profiles with Client Configuration (Q25)
Default profiles based on industry data:

| Level | kW | Voltage | Default Hours | Notes |
|-------|-----|---------|--------------|-------|
| Level 1 | 1.4 | 120V/12A | 6 PM – 6 AM (residential) | Trickle charge |
| Level 2 | 7.2 | 240V/30A | 6 PM – 2 AM peak | Most common home EVSE |
| Level 2 | 11.5 | 240V/48A | 6 PM – 12 AM peak | High-power home |
| DCFC L3 | 50–150 | 480V 3-phase | Midday + evening peaks | Commercial sites |
| DCFC L3 | 150–350 | 480V 3-phase | Midday peak | Highway corridor |

Each parameter (kW, time-of-day shape, weekend variation, seasonal adjustment) is configurable per client engagement. Clients can also upload fully custom CSV profiles.

### Equipment Libraries from CYME (Q29)
The CYME parser must extract not just topology but also:
- **Conductor catalog**: name, R1/X1/R0/X0 per mile, ampacity, GMR, diameter
- **Transformer catalog**: name, kVA ratings, impedance %, R/X, no-load loss, tap range, connection type
- **Regulator settings**: bandwidth, PT ratio, voltage set point
- **Capacitor specs**: kVAR rating, control type/settings

These become the equipment library that the OpenDSS converter uses to generate accurate `.dss` models.

---

## 8. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **CYME parsing (3 formats + equipment catalogs)** | High — undocumented formats, no standard library | Start with XML (best structured). Request sample files immediately. Build incrementally. |
| **Meter-to-transformer spatial inference** | High — bad mapping = bad load allocation = bad results | Confidence scoring. Manual override UI. Validate aggregated load vs. SCADA at feeder head. |
| **CYME → OpenDSS conversion fidelity** | Medium — model translation loses nuance | Systematic validation: compare against imported CYME study results. Report RMSE. Iterate. |
| **Stochastic hosting capacity compute** | Medium — Monte Carlo × 1,000 feeders = expensive | Configurable iterations. Run on subset of feeders. ML surrogate for interactive screening. |
| **8760 × 1,000 feeders compute** | Medium — 8.76M solves | Multiprocessing handles in ~15–30 min on 16 cores. Acceptable for workstation. |
| **AMI data volume** | Medium — ~35B rows/year | TimescaleDB compression + pre-aggregation to transformer level. Manageable on single instance. |
| **GIS ↔ CYME topology disagreement** | Medium — different as-built vs. as-modeled | Reconciliation tool with spatial join + manual override. |
| **OpenDSS on Linux/Docker** | Low | `opendssdirect.py` supports Linux. Validate early. |

---

## 9. Estimated Project Structure

```
digital-twin-light/
├── docker-compose.yml              # PostgreSQL + PostGIS + TimescaleDB + Redis
├── Dockerfile
├── pyproject.toml
├── alembic/                         # Database migrations
│   └── versions/
├── src/
│   ├── dtl/                         # Main package: "Digital Twin Light"
│   │   ├── __init__.py
│   │   ├── config.py                # App configuration
│   │   ├── ingestion/               # PHASE 1
│   │   │   ├── gis_parser.py        # Shapefile/GeoJSON/CSV/GDB → assets
│   │   │   ├── cyme_parser.py       # XML/.mdb/text → network + equipment
│   │   │   ├── cyme_equipment.py    # Extract conductor/xfmr catalogs
│   │   │   ├── cyme_validation.py   # Import CYME study results
│   │   │   ├── oms_parser.py        # CSV/Excel → outage events
│   │   │   ├── ami_processor.py     # 15-min data, chunk processing
│   │   │   ├── weather_client.py    # Open-Meteo API
│   │   │   ├── meter_xfmr_mapper.py # Spatial inference of meter→xfmr
│   │   │   └── validators.py        # Schema/completeness checks
│   │   ├── model/                   # PHASE 1
│   │   │   ├── network.py           # Unified Network Model
│   │   │   ├── assets.py            # Asset dataclasses
│   │   │   ├── topology.py          # Graph/connectivity (networkx)
│   │   │   ├── equipment.py         # Conductor/xfmr catalog models
│   │   │   └── schemas.py           # Pydantic schemas
│   │   ├── solver/                  # PHASE 2
│   │   │   ├── opendss_converter.py # UNM → .dss scripts
│   │   │   ├── opendss_runner.py    # Single-feeder QSTS
│   │   │   ├── parallel_engine.py   # Multiprocessing pool
│   │   │   ├── hosting_capacity.py  # EPRI DRIVE + Monte Carlo
│   │   │   ├── results_extractor.py # OpenDSS output → DB
│   │   │   └── cyme_validator.py    # Compare vs. CYME results
│   │   ├── scenarios/               # PHASE 3
│   │   │   ├── schema.py            # YAML/JSON scenario config
│   │   │   ├── ev_growth.py         # Built-in + custom EV profiles
│   │   │   ├── ev_profiles.py       # Level 1/2/3 default profiles
│   │   │   ├── solar_growth.py      # PV adoption + irradiance model
│   │   │   ├── weather_scenario.py  # Historical extremes / synthetic
│   │   │   ├── policy.py            # TOU, electrification, interconn.
│   │   │   ├── compositor.py        # Stack + resolve → 8760 profiles
│   │   │   └── sensitivity.py       # LHS / grid search sweeps
│   │   ├── ml/                      # PHASE 4
│   │   │   ├── calibration.py       # Bayesian model tuning
│   │   │   ├── disaggregation.py    # BTM solar separation
│   │   │   ├── forecasting.py       # Weather-load regression
│   │   │   ├── anomaly.py           # Isolation forest on AMI/SCADA
│   │   │   ├── clustering.py        # Load shape k-means/DTW
│   │   │   ├── surrogate.py         # DER hosting capacity proxy
│   │   │   ├── risk_scoring.py      # Outage probability
│   │   │   ├── mitigation.py        # Cost-benefit ranking
│   │   │   ├── growth_detection.py  # Changepoint / ARIMA
│   │   │   ├── degradation.py       # IEEE C57.91 xfmr aging
│   │   │   ├── spatial.py           # DBSCAN violation clustering
│   │   │   └── nl_query.py          # NLP → structured query
│   │   ├── analytics/               # PHASE 2–4
│   │   │   ├── thermal.py
│   │   │   ├── voltage.py
│   │   │   ├── losses.py
│   │   │   ├── hosting_capacity.py
│   │   │   ├── reliability.py
│   │   │   └── comparison.py        # Scenario diff engine
│   │   ├── api/                     # PHASE 5
│   │   │   ├── main.py              # FastAPI app
│   │   │   ├── auth.py              # Simple local login
│   │   │   ├── routes/
│   │   │   │   ├── data.py          # Upload/manage endpoints
│   │   │   │   ├── network.py       # Network model endpoints
│   │   │   │   ├── scenarios.py     # Scenario CRUD + launch
│   │   │   │   ├── simulations.py   # Job management
│   │   │   │   ├── results.py       # Query results
│   │   │   │   ├── map.py           # GeoJSON/vector tile endpoints
│   │   │   │   └── ml.py            # ML insights endpoints
│   │   │   ├── websocket.py         # Job progress streaming
│   │   │   └── dependencies.py
│   │   └── db/
│   │       ├── models.py            # SQLAlchemy + GeoAlchemy2 models
│   │       ├── session.py
│   │       └── queries.py
│   └── frontend/                    # PHASE 5
│       ├── package.json
│       ├── tsconfig.json
│       ├── src/
│       │   ├── App.tsx
│       │   ├── components/
│       │   │   ├── MapView/         # MapLibre + deck.gl layers
│       │   │   ├── LayerPanel/      # Toggle/configure map layers
│       │   │   ├── ScenarioBuilder/ # Create/edit/stack scenarios
│       │   │   ├── EVProfileEditor/ # Configure EV charging profiles
│       │   │   ├── SimulationManager/
│       │   │   ├── ResultsDashboard/
│       │   │   ├── AssetDetail/     # Click-through detail panels
│       │   │   ├── DataManager/     # File upload + validation
│       │   │   ├── ScenarioCompare/ # Side-by-side analysis
│       │   │   └── MLInsights/      # Risk scores, trends, anomalies
│       │   ├── layers/              # Map layer definitions
│       │   │   ├── thermalLayer.ts
│       │   │   ├── voltageLayer.ts
│       │   │   ├── hostingCapLayer.ts
│       │   │   ├── evOverlay.ts
│       │   │   ├── solarOverlay.ts
│       │   │   ├── outageHeatmap.ts
│       │   │   ├── riskOverlay.ts
│       │   │   ├── scenarioDiff.ts
│       │   │   └── assetAge.ts
│       │   └── api/                 # API client
│       └── public/
├── data/
│   └── ev_profiles/                 # Built-in EV charging profiles
│       ├── level1_residential.csv
│       ├── level2_residential.csv
│       ├── level2_high_power.csv
│       ├── dcfc_commercial.csv
│       └── dcfc_highway.csv
├── tests/
│   ├── test_ingestion/
│   ├── test_solver/
│   ├── test_scenarios/
│   ├── test_ml/
│   ├── test_api/
│   └── fixtures/                    # Sample CYME/GIS/OMS/AMI test data
└── docs/
    ├── data_format_specs.md         # Expected input file formats
    └── deployment.md
```

---

## 10. Summary of All 30 Requirements Decisions

| # | Question | Answer |
|---|----------|--------|
| 1 | GIS formats | All: Shapefile, GeoJSON, CSV, GDB |
| 2 | CYME formats | All: XML, .mdb, CYMDIST text. Per-feeder + system-wide |
| 3 | OMS format | CSV/Excel, platform-agnostic. Cause codes, CI/CMI, times, device |
| 4 | AMI/SCADA | 15-min meter level, auto-aggregate to xfmr/feeder |
| 5 | Weather API | Free provider, need historical data |
| 6 | Solver | OpenDSS or pandapower (free) |
| 7 | Fidelity | Full unbalanced 3-phase |
| 8 | Simulation | 8760 hourly QSTS |
| 9 | Output metrics | All: thermal, voltage, losses, hosting capacity, SAIDI/SAIFI |
| 10 | EV/Solar curves | User-provided + sensitivity/modification capability |
| 11 | Scenario stacking | Yes |
| 12 | Policy changes | All: TOU, electrification, interconnection rules |
| 13 | Tech stack | Python, no constraints |
| 14 | UI | Web dashboard or local |
| 15 | Deployment | Local workstation + cloud |
| 16 | Database | PostgreSQL + PostGIS |
| 17 | AI role | All capabilities + additional ideas |
| 18 | AI approach | Classical ML models |
| 19 | Scale | 1,000 feeders |
| 20 | Visualization | Map-based overlay with configurable layers |
| 21 | Data refresh | One-time or periodic batch |
| 22 | Multi-tenancy | No — single-utility private instances |
| 23 | CYME validation | Import existing CYME study for validation baseline |
| 24 | Meter-xfmr mapping | Spatial inference (GIS proximity), most cases |
| 25 | EV profiles | Built-in Level 1/2/3 + configurable per client |
| 26 | Hosting capacity | Stochastic Monte Carlo + EPRI DRIVE |
| 27 | Authentication | Simple local login |
| 28 | Cloud compute | Workstation-only Phase 1 |
| 29 | Equipment libraries | Parse from CYME |
| 30 | Timeline priority | Data ingestion first (Phase 1) |
