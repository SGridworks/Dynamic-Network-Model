# Feeder generation and walkthrough

The [generator notebook](../../notebooks/00-feeder-generation.ipynb) runs the existing
SP&L infrastructure generator in a temporary directory. It creates the six core
asset and network tables, loads them through an isolated V1 loader, checks the
hierarchy and feeder trees, and verifies repeatability without changing the
checked-in datasets. Install the notebook dependencies listed at its top and run
it from the repository root or `notebooks/` directory.

The example uses fictional, Phoenix-referenced straight-line geometry. It includes
guidance for replacing that geometry and topology construction with actual street
corridors. A Golden case has not been implemented here.

## Original Python companion

`feeder_walkthrough.py` is the read-only companion to the September 8, 2026
methodology note. It checks the published dataset through the combined loader;
it does not generate a new case or run OpenDSS.

From the repository root:

```bash
python -m pip install -r requirements-data.txt
python examples/feeder-generation/feeder_walkthrough.py --repo . --feeder FDR-0001
```

At reference commit `580909edc9cf7233195cdcd52d1b65f40f02eb48`, FDR-0001 has
364 transformers, 2,372 customers, 740 structural nodes, and 739 structural edges.
The tree includes one open tail segment and excludes interfeeder ties.

## Interpretation

The notebook omits time series, DER, V2 conversions, and electrical studies. Its
network sampling differs from the full generator because that generator uses a
shared random stream across stages. The notebook checks repeatability for its
own documented call order, seed, and environment.

Structural connectivity does not establish energized connectivity or electrical
feasibility. The current exporter needs additional switch-state and equipment-
availability handling, and the reference base model has voltage violations.
See [DATA-QUALITY.md](../../DATA-QUALITY.md).
