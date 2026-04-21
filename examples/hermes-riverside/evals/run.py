"""Eval harness entry point.

Pure scoring logic lives in evals/scoring.py so tests can reach it without
triggering the agent/LLM import graph. This file wires the scorer to the
live agent turn.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from evals.scoring import AxisScores, Score, aggregate, score_pair
from hermes.agent.loop import run as run_turn
from hermes.agent.prompts import system_message
from hermes.config import load_or_exit


def _evaluate(pair: dict) -> Score:
    history = [system_message()]
    turn = run_turn(pair["q"], history=history)
    tools_called = [t.name for t in turn.traces]
    answer = turn.final_text or ""
    return score_pair(pair, answer, tools_called)


def _render_md(cfg_label: str, scores: list[Score]) -> str:
    n = len(scores)
    agg = aggregate(scores)
    lines = [
        f"# Eval results — {cfg_label}",
        "",
        f"- pairs: **{n}**",
        f"- correctness:     **{agg.correctness:.2f}**",
        f"- tool_discipline: **{agg.tool_discipline:.2f}**",
        f"- cite_coverage:   **{agg.cite_coverage:.2f}**",
        f"- brevity:         **{agg.brevity:.2f}**",
        "",
        "| id | corr | tool | cite | brev | tools called |",
        "|---|---|---|---|---|---|",
    ]
    for s in scores:
        a = s.axes
        lines.append(
            f"| `{s.qid}` | {a.correctness:.2f} | {a.tool_discipline:.2f} | "
            f"{a.cite_coverage:.2f} | {a.brevity:.2f} | "
            f"{', '.join(s.tools_called) or '(none)'} |"
        )
    lines.append("")
    lines.append("## Answer snippets")
    for s in scores:
        snippet = s.answer[:300].replace("\n", " ")
        lines.append(f"- **{s.qid}**: {snippet}")
    return "\n".join(lines) + "\n"


def run(pairs_path: Path, out_path: Path) -> None:
    cfg = load_or_exit()
    pairs = yaml.safe_load(pairs_path.read_text())
    scores = []
    for pair in pairs:
        try:
            s = _evaluate(pair)
        except Exception as e:  # noqa: BLE001
            s = Score(
                qid=pair["id"],
                axes=AxisScores(0.0, 0.0, 0.0, 0.0),
                tools_called=[],
                answer=f"ERROR: {e}",
            )
        scores.append(s)
        a = s.axes
        print(
            f"{s.qid}: corr={a.correctness:.2f} tool={a.tool_discipline:.2f} "
            f"cite={a.cite_coverage:.2f} brev={a.brevity:.2f}"
        )

    label = f"provider={cfg.provider} model={cfg.model}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render_md(label, scores))
    print(f"\nWrote {out_path}")
