from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from hermes.agent.loop import run as run_turn
from hermes.agent.prompts import system_message
from hermes.config import load_or_exit


@dataclass
class Score:
    qid: str
    tools_ok: bool
    keywords_ok: bool
    tools_called: list[str]
    answer: str


def _evaluate(pair: dict) -> Score:
    history = [system_message()]
    turn = run_turn(pair["q"], history=history)
    called = [t.name for t in turn.traces]
    expected_tools = set(pair.get("expected_tools", []))
    tools_ok = expected_tools.issubset(set(called))
    ans = (turn.final_text or "").lower()
    keywords_ok = all(kw.lower() in ans for kw in pair.get("expected_keywords", []))
    return Score(
        qid=pair["id"],
        tools_ok=tools_ok,
        keywords_ok=keywords_ok,
        tools_called=called,
        answer=turn.final_text or "",
    )


def _render_md(cfg_label: str, scores: list[Score]) -> str:
    n = len(scores)
    t_ok = sum(1 for s in scores if s.tools_ok)
    k_ok = sum(1 for s in scores if s.keywords_ok)
    both = sum(1 for s in scores if s.tools_ok and s.keywords_ok)
    lines = [
        f"# Eval results — {cfg_label}",
        "",
        f"- pairs: **{n}**",
        f"- tools correct: **{t_ok}/{n}** ({t_ok/n:.0%})",
        f"- keywords correct: **{k_ok}/{n}** ({k_ok/n:.0%})",
        f"- both: **{both}/{n}** ({both/n:.0%})",
        "",
        "| id | tools | keywords | tools called |",
        "|---|---|---|---|",
    ]
    for s in scores:
        lines.append(
            f"| `{s.qid}` | {'ok' if s.tools_ok else 'miss'} | "
            f"{'ok' if s.keywords_ok else 'miss'} | {', '.join(s.tools_called) or '(none)'} |"
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
            s = Score(qid=pair["id"], tools_ok=False, keywords_ok=False, tools_called=[], answer=f"ERROR: {e}")
        scores.append(s)
        print(f"{s.qid}: tools={'ok' if s.tools_ok else 'miss'} kw={'ok' if s.keywords_ok else 'miss'}")

    label = f"provider={cfg.provider} model={cfg.model}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_render_md(label, scores))
    print(f"\nWrote {out_path}")
