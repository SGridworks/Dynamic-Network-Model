# Hermes at Riverside

> An example within [Sisyphean Power & Light / Dynamic Network Model](../../README.md).

An agentic substation copilot that reasons over Sisyphean Power & Light's Riverside substation (SUB-001) using the same synthetic data that powers the rest of this repo. Open source. Local-first. Built as a showcase for what the articles on [sgridworks.com/resources](https://sgridworks.com/resources.html) describe.

Live walkthrough on sgridworks.com: **[Hermes at Riverside](https://sgridworks.com/hermes-riverside-poc.html)**.

## What's in the box

**The showcase:** a Jupyter notebook — `notebook/hermes-riverside-showcase.ipynb` — that walks through five scenarios on Riverside: three VVO (volt-VAR) and two restoration. Each scenario shows the SP&L data the agent saw, the agent's reasoning, the tool calls it made, and what a utility would build on top. Traces were recorded once; the notebook runs offline with no LLM call required.

**The evidence:** the production code path lives alongside the notebook. A LiteLLM adapter for Ollama / vLLM / llama.cpp / Bedrock. A compliance gate in `hermes/config.py` that refuses Bedrock unless an AWS VPC endpoint is attested. A Streamlit UI with both replay and live-chat modes. A hand-rolled tool-calling loop that fits on one screen. None of it is hidden — a utility security team reading this repo can see exactly what would run in their environment.

## Source articles

The architecture is grounded in five articles:

1. [AI in the Control Room, Part 1 — Shadow AI](https://sgridworks.com/ai-control-room-part1-shadow-ai.html)
2. [AI in the Control Room, Part 2 — Regulatory Landscape](https://sgridworks.com/ai-control-room-part2-regulatory-landscape.html)
3. [AI in the Control Room, Part 3 — Three-Zone Architecture](https://sgridworks.com/ai-control-room-part3-three-zone-architecture.html)
4. [AI in the Control Room, Part 4 — Implementation](https://sgridworks.com/ai-control-room-part4-implementation.html)
5. [The Agentic Epoch — Autonomy at the Grid Edge](https://sgridworks.com/agentic-epoch-grid-edge.html)

The agent in this POC operates at **Rung 2 (Shadow)** per the Agentic Epoch framework: it recommends and explains; it never actuates.

## In progress — Atlas Phase 1a

Foundation work for the Substation Atlas is on the `feat/hermes-atlas-phase-1a` branch. Adds a `HERMES.md` v0.1 schema + loader, a 4-axis Pareto eval scorer (correctness, tool_discipline, cite_coverage, brevity), a self-improving `hermes autoresearch` loop with a kill-switch and rollback runbook, and a third archetype playbook (SUB-013 Gilbert Road — rural loop). The public atlas launch at `sgridworks.com/hermes-atlas` is Phase 1b; the `main` branch here stays at the POC until the atlas has observed ~7 consecutive clean nightly runs. See `docs/ROLLBACK.md` and `docs/SETUP-AUTORESEARCH.md` on that branch for the operational details.

## Quickstart — notebook (no LLM required)

```bash
# 1. Clone DNM (this example lives inside it at examples/hermes-riverside):
git clone https://github.com/SGridworks/Dynamic-Network-Model
cd Dynamic-Network-Model/examples/hermes-riverside

# 2. Install:
make setup

# 3. Open the notebook:
make notebook
```

The adapter walks up from `hermes/data/spl.py` to find the DNM repo root automatically — no env var needed when the example lives inside DNM.

Or just read the rendered HTML at `notebook/build/hermes-riverside-showcase.html`.

## Quickstart — live mode (LLM required)

```bash
ollama pull gemma4:e4b
cp .env.example .env   # defaults are local Ollama
make demo-live
```

## Provider matrix

| Provider    | Default | Where inference runs                       | Use when                                         |
|-------------|:-------:|--------------------------------------------|--------------------------------------------------|
| `ollama`    |   yes   | Local machine / on-prem node               | Laptop demos, air-gapped substations             |
| `vllm`      |         | On-prem GPU server                         | Higher throughput on utility-owned hardware      |
| `llama_cpp` |         | Edge / DIN-rail industrial PC              | Jetson-class hardware, CPU-only fallback         |
| `bedrock`   |         | AWS Bedrock via **VPC endpoint only**      | Highest quality, utility has approved VPC path   |

The `bedrock` provider is gated. See [`docs/SECURITY.md`](docs/SECURITY.md).

## Models

Default model: **Gemma 4 E4B** — Google's edge-optimized MoE variant, the model the *Agentic Epoch* article calls out by name. The notebook's traces were recorded against Gemma 4 E4B running on consumer-class Apple Silicon hardware — intentionally, to match the article's thesis about edge-feasible reasoning. A higher-quality Claude-over-VPC recording is one command away: `HERMES_LLM_PROVIDER=bedrock make record` (after satisfying the compliance gate).

## Layout

```
hermes/
  config.py       compliance gate
  llm/            LiteLLM provider adapter
  data/spl.py     SP&L adapter over Dynamic-Network-Model loaders
  agent/          tool specs, CEII-aware prompt, hand-rolled tool-calling loop
  showcase/       recorded-trace schema + replay renderer
  ui/             Streamlit (replay + live modes)
  cli.py          Typer app (chat / record / eval / summary)
scripts/
  scenarios.py    5 scenario definitions
  record_traces.py   one-shot trace recorder
  build_notebook.py  notebook generator
notebook/
  hermes-riverside-showcase.ipynb   the showcase
  build/                        HTML export
fixtures/traces/                recorded agent traces
docs/
  SECURITY.md     CEII/CIP posture; Bedrock-VPC gate
  DEPLOYMENT.md   three deployment modes
```

## License

Apache-2.0.
