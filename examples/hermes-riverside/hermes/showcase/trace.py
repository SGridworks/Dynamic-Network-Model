"""Recorded-trace schema and replay renderer.

A Trace is the complete record of one showcase scenario — the user prompt,
every tool call and result, and the agent's final answer — captured once
against a live LLM backend and replayed offline in the notebook or Streamlit.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)


class Trace(BaseModel):
    scenario_id: str
    title: str
    query: str
    final_text: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    provider: str
    model: str
    elapsed_seconds: float | None = None
    recorded_at: str | None = None

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> "Trace":
        return cls.model_validate_json(path.read_text())


def from_turn(scenario_id: str, title: str, query: str, turn, provider: str, model: str, elapsed: float | None = None) -> Trace:
    """Convert an agent Turn (hermes.agent.loop.Turn) into a persistable Trace."""
    from datetime import datetime, timezone

    return Trace(
        scenario_id=scenario_id,
        title=title,
        query=query,
        final_text=turn.final_text,
        tool_calls=[
            ToolCall(name=t.name, arguments=t.arguments, result=_truncate(asdict(t)["result"]))
            for t in turn.traces
        ],
        provider=provider,
        model=model,
        elapsed_seconds=elapsed,
        recorded_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def _truncate(obj: Any, max_chars: int = 20_000) -> Any:
    """Tool results can be large. Cap the JSON so committed fixtures stay reviewable."""
    s = json.dumps(obj)
    if len(s) <= max_chars:
        return obj
    return {"_truncated": True, "preview": s[:max_chars], "original_len": len(s)}


# --- Rendering --------------------------------------------------------------


def render_markdown(trace: Trace) -> str:
    """One-shot markdown for notebook display (IPython.display.Markdown)."""
    lines = [
        f"**Query:** {trace.query}",
        "",
        f"_{trace.provider} / {trace.model}_",
        "",
        "---",
        "",
        f"**Otter:** {trace.final_text}",
        "",
    ]
    if trace.tool_calls:
        lines.append("<details><summary>Tool trace ({} calls)</summary>".format(len(trace.tool_calls)))
        lines.append("")
        for i, tc in enumerate(trace.tool_calls, 1):
            args = json.dumps(tc.arguments) if tc.arguments else "{}"
            lines.append(f"{i}. `{tc.name}({args})`")
            preview = json.dumps(tc.result, default=str)
            if len(preview) > 400:
                preview = preview[:400] + "…"
            lines.append(f"   ```json")
            lines.append(f"   {preview}")
            lines.append(f"   ```")
        lines.append("")
        lines.append("</details>")
    return "\n".join(lines)


def load_all(trace_dir: Path) -> list[Trace]:
    return sorted(
        (Trace.load(p) for p in trace_dir.glob("*.json")),
        key=lambda t: t.scenario_id,
    )
