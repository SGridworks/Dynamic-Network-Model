"""Generate notebook/hermes-riverside-showcase.ipynb from scripts/scenarios.py + recorded traces.

Re-run after changing scenarios, prompt, traces, or narrative prose.

    .venv/bin/python scripts/build_notebook.py
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

from hermes.data import spl
from hermes.showcase.trace import Trace
from scripts.scenarios import SCENARIOS

REPO = Path(__file__).resolve().parent.parent
TRACE_DIR = REPO / "fixtures" / "traces"
OUT = REPO / "notebook" / "hermes-riverside-showcase.ipynb"


HEADER_MD = """# Hermes at Riverside — an agentic substation copilot on Sisyphean Power & Light

This notebook walks through five scenarios where **Hermes** reasons over SP&L's Riverside
substation (SUB-001) using the same data that powers the Dynamic Network Model. Three are VVO
(volt-VAR optimization) scenarios; two are restoration scenarios.

## How the traces in this notebook were produced

Every agent response in this notebook was **actually run**, not simulated. Hermes ran once
against each scenario on real consumer hardware and the full interaction (query → tool calls →
tool results → final response) was captured as a JSON fixture. The notebook replays those
fixtures offline. Nothing on this page is invented for the demo.

The inference path that produced the traces:

- **Hardware.** Apple Silicon Mac Mini (M-series). Consumer-class. No cloud GPU. No managed
  inference API.
- **Model.** `gemma4:e4b` — Google's Gemma 4 E4B open-weights MoE, the model named in
  [The Agentic Epoch](https://sgridworks.com/agentic-epoch-grid-edge.html). Quantized to
  Q4_K_M, ~9.6 GB on disk, runs at interactive latency on the hardware above.
- **Runtime.** [Ollama](https://ollama.com) serving the model over a standard HTTP,
  OpenAI-compatible API. Zero egress to any third party during a scenario.
- **Agent loop.** Hermes' tool-calling loop in this repo — 200 lines, hand-rolled,
  auditable. No LangChain.

The per-scenario `elapsed_seconds` field in each trace file is the real wall-clock time Hermes
took to reason and respond. The tool calls are the calls Hermes actually made, in the order it
made them. The final response is byte-for-byte what the model produced. Re-run
`python -m hermes.cli record --scenario all` on your own hardware to produce your own copy of
these traces.

The architecture this notebook showcases is described in five articles on
[sgridworks.com/resources](https://sgridworks.com/resources.html):

1. [Shadow AI](https://sgridworks.com/ai-control-room-part1-shadow-ai.html) — why governance beats prohibition
2. [Regulatory landscape](https://sgridworks.com/ai-control-room-part2-regulatory-landscape.html) — CEII, NERC CIP, data-tier thinking
3. [Three-zone architecture](https://sgridworks.com/ai-control-room-part3-three-zone-architecture.html) — where AI is allowed and where it isn't
4. [Implementation](https://sgridworks.com/ai-control-room-part4-implementation.html) — the 90-day path from zero to governed
5. [The Agentic Epoch](https://sgridworks.com/agentic-epoch-grid-edge.html) — the 5-rung autonomy ladder and the open stack

Hermes here operates at **Rung 2 (Shadow)**: it reasons and recommends, nothing actuates.
The code that would run this live — LiteLLM provider adapter, Bedrock-VPC compliance gate,
Streamlit UI — ships alongside this notebook. The notebook itself runs offline.
"""

RIVERSIDE_MD = """## Riverside substation

All numbers below are read live from the [Dynamic Network Model](https://github.com/SGridworks/Dynamic-Network-Model)
via the adapter in `hermes/data/spl.py`. Nothing on this page is invented for the demo.
"""

FOOTER_MD = """## What this doesn't show

- Anything actuating. By design. Rung 2 means recommendation only.
- Live customer data. The SP&L set is synthetic.
- Claude-tier reasoning. These traces were produced by Gemma 4 E4B on consumer hardware, which
  matches the story in the Agentic Epoch article (open weights, edge-feasible). Recording the
  same scenarios against Claude over a VPC endpoint would produce tighter prose and occasionally
  catch context the smaller model misses. The `scripts/record_traces.py` CLI supports both —
  point `HERMES_LLM_PROVIDER` at `bedrock` and re-run, after you've satisfied the compliance
  gate in `docs/SECURITY.md`.

## What a utility would do next

- Swap the SP&L adapter for the utility's own historian, CMMS, and one-line source of truth
  (the contract: `hermes/data/spl.py` is the only place that reads files)
- Record months of shadow-mode traces alongside live operator actions
- Wire the tool-trace stream into the utility SIEM for CIP-007 evidence
- When shadow-mode credibility is built, graduate to Rung 3 with human confirmation gates

The repo: [github.com/SGridworks/hermes-riverside-poc](https://github.com/SGridworks/hermes-riverside-poc)
"""


def _scenario_cells(scenario, trace: Trace | None):
    cells = []
    cells.append(nbf.v4.new_markdown_cell(f"## {scenario.title}\n\n{scenario.intro_md}"))

    # Preamble: one code cell per labeled loader call
    preamble_src = [
        "import json",
        "from scripts.scenarios import by_id",
        f"scenario = by_id({scenario.id!r})",
        "for label, fn in scenario.preamble:",
        "    print(f'--- {label} ---')",
        "    print(json.dumps(fn(), indent=2, default=str)[:1500])",
        "    print()",
    ]
    cells.append(nbf.v4.new_code_cell("\n".join(preamble_src)))

    # Agent transcript
    if trace is None:
        cells.append(
            nbf.v4.new_markdown_cell(
                f"> _No recorded trace for `{scenario.id}`. Run_ "
                f"`python -m hermes.cli record --scenario {scenario.id}`."
            )
        )
    else:
        cells.append(
            nbf.v4.new_markdown_cell(
                f"### Agent transcript\n\n"
                f"**Query.** {trace.query}\n\n"
                f"_Recorded against {trace.provider} / `{trace.model}` in "
                f"{trace.elapsed_seconds:.1f} s, {len(trace.tool_calls)} tool calls._\n\n"
                f"**Hermes.**\n\n{trace.final_text}"
            )
        )
        if trace.tool_calls:
            trace_md_lines = ["### Tool trace\n"]
            for i, tc in enumerate(trace.tool_calls, 1):
                import json as _json

                args = _json.dumps(tc.arguments) if tc.arguments else "{}"
                trace_md_lines.append(f"**{i}.** `{tc.name}({args})`")
                preview = _json.dumps(tc.result, default=str)
                if len(preview) > 500:
                    preview = preview[:500] + "…"
                trace_md_lines.append(f"```json\n{preview}\n```")
            cells.append(nbf.v4.new_markdown_cell("\n\n".join(trace_md_lines)))

    cells.append(nbf.v4.new_markdown_cell(scenario.takeaway_md))
    cells.append(nbf.v4.new_markdown_cell("---"))
    return cells


import re


_REDACT_PATTERNS = [
    # Absolute user paths: /Users/<anything>/ → ~/
    (re.compile(r"/Users/[^/\s'\"]+/"), "~/"),
    # Bare /Users/<name> with no trailing slash
    (re.compile(r"/Users/[A-Za-z0-9_.-]+"), "~"),
    # Private RFC1918 v4 like 10.0.5.1, 192.168.x.y
    (re.compile(r"\b10\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<redacted-ip>"),
    (re.compile(r"\b192\.168\.\d{1,3}\.\d{1,3}\b"), "<redacted-ip>"),
    # Cluster node hostnames
    (re.compile(r"\bmini[12]\b"), "<redacted-host>"),
]


def _redact(text: str) -> str:
    if not isinstance(text, str):
        return text
    for pat, repl in _REDACT_PATTERNS:
        text = pat.sub(repl, text)
    return text


def _redact_cell(cell):
    """Walk a cell's source and outputs; redact personal identifiers in strings."""
    src = cell.get("source")
    if isinstance(src, list):
        cell["source"] = [_redact(s) for s in src]
    elif isinstance(src, str):
        cell["source"] = _redact(src)
    for out in cell.get("outputs", []) or []:
        if "text" in out:
            t = out["text"]
            out["text"] = [_redact(x) for x in t] if isinstance(t, list) else _redact(t)
        data = out.get("data") or {}
        for k, v in list(data.items()):
            if isinstance(v, list):
                data[k] = [_redact(x) for x in v]
            elif isinstance(v, str):
                data[k] = _redact(v)


def build() -> Path:
    nb = nbf.v4.new_notebook()
    nb.cells = []
    nb.cells.append(nbf.v4.new_markdown_cell(HEADER_MD))
    nb.cells.append(nbf.v4.new_markdown_cell(RIVERSIDE_MD))

    # Live Riverside snapshot cell
    snapshot_src = [
        "from hermes.data import spl",
        "import json",
        "",
        "summary = spl.riverside_summary()",
        "feeders = spl.riverside_feeders()",
        "mg = spl.riverside_microgrid()",
        "hc = spl.riverside_hosting_capacity()",
        "solar = spl.riverside_solar_summary()",
        "topo = spl.riverside_topology()",
        "outages = spl.riverside_outages()",
        "",
        "print(f\"Substation:           {summary['name']} ({summary['substation_id']})\")",
        "print(f\"Voltage:              {summary['voltage_high_kv']} / {summary['voltage_low_kv']} kV\")",
        "print(f\"Rated / peak MVA:     {summary['rated_capacity_mva']} / {summary['peak_load_mva']}\")",
        "print(f\"Age:                  {summary['age_years']} years\")",
        "print(f\"Feeders:              {len(feeders)} — {', '.join(f['feeder_id'] for f in feeders)}\")",
        "print(f\"Microgrid:            {mg['facility_name']} on {mg['feeder_id']} (island {mg['island_duration_hours']}h)\")",
        "print(f\"Hosting capacity:     {hc['total_binding_kw']/1000:.1f} MW, limiting: {hc['limiting_factors']}\")",
        "print(f\"Solar installs:       {solar['total_sites']} sites, {solar['total_kw']/1000:.1f} MW\")",
        "print(f\"Topology:             {topo['nodes']['total']} nodes, {topo['edges']['total']} edges\")",
        "print(f\"Outage history:       {len(outages)} events\")",
    ]
    nb.cells.append(nbf.v4.new_code_cell("\n".join(snapshot_src)))

    for scenario in SCENARIOS:
        trace_path = TRACE_DIR / f"{scenario.id}.json"
        trace = Trace.load(trace_path) if trace_path.exists() else None
        nb.cells.extend(_scenario_cells(scenario, trace))

    nb.cells.append(nbf.v4.new_markdown_cell(FOOTER_MD))

    # Clear cell ids to avoid schema warnings across notebook runs.
    for c in nb.cells:
        c.id = c.get("id", None)
        _redact_cell(c)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as fh:
        nbf.write(nb, fh)
    return OUT


def redact_inplace(path: Path) -> None:
    """Redact an already-executed notebook in place. Use after nbconvert --execute."""
    nb = nbf.read(path, as_version=4)
    for c in nb.cells:
        _redact_cell(c)
    with path.open("w") as fh:
        nbf.write(nb, fh)


if __name__ == "__main__":
    p = build()
    print(f"Wrote {p}")
