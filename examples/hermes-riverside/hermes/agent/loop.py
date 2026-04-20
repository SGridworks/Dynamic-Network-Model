"""Tool-calling loop over OpenAI-compatible chat.completions.

Hand-rolled (no LangChain). Tolerant of:
  - models that emit tool calls via structured output (Claude, newer Qwen/Gemma)
  - models that emit tool calls as JSON embedded in content (older or less tuned models)
The second path is why we ship with Gemma-friendly fallbacks.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from hermes.agent import tools as T
from hermes.agent.prompts import system_message
from hermes.llm import get_client

MAX_STEPS = 8


@dataclass
class ToolTrace:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class Turn:
    user: str
    final_text: str
    traces: list[ToolTrace] = field(default_factory=list)
    raw_messages: list[dict] = field(default_factory=list)


def _message_to_dict(msg: Any) -> dict:
    """LiteLLM returns a ModelResponse; normalize the assistant message."""
    if isinstance(msg, dict):
        return msg
    out: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
    calls = getattr(msg, "tool_calls", None)
    if calls:
        out["tool_calls"] = [
            {
                "id": c.id,
                "type": "function",
                "function": {
                    "name": c.function.name,
                    "arguments": c.function.arguments,
                },
            }
            for c in calls
        ]
    return out


_FALLBACK_TOOL_RE = re.compile(
    r"```(?:json|tool_call)?\s*(\{.*?\})\s*```", re.DOTALL
)


def _fallback_tool_calls_from_content(content: str) -> list[dict]:
    """If the model emits `{\"tool\":\"name\",\"arguments\":{...}}` in content, extract it.

    Supports:
      ```json {"tool":"...","arguments":{...}} ```
      plain JSON on its own line
    """
    if not content:
        return []
    candidates: list[str] = []
    candidates.extend(m.group(1) for m in _FALLBACK_TOOL_RE.finditer(content))
    # Also try the whole content as a JSON object.
    stripped = content.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        candidates.append(stripped)

    out = []
    for c in candidates:
        try:
            obj = json.loads(c)
        except json.JSONDecodeError:
            continue
        name = obj.get("tool") or obj.get("name")
        args = obj.get("arguments") or obj.get("args") or {}
        if name and name in T.REGISTRY:
            out.append({
                "id": f"fallback-{len(out)}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            })
    return out


def run(
    user_text: str,
    history: list[dict] | None = None,
    completion: Callable[..., Any] | None = None,
    on_trace: Callable[[ToolTrace], None] | None = None,
) -> Turn:
    """Run one user turn. Returns the turn record + appends to history (in place)."""
    completion = completion or get_client()
    history = history if history is not None else [system_message()]
    history.append({"role": "user", "content": user_text})
    traces: list[ToolTrace] = []

    for _ in range(MAX_STEPS):
        resp = completion(messages=history, tools=T.TOOL_SPECS, tool_choice="auto")
        msg = _message_to_dict(resp.choices[0].message)
        history.append(msg)

        tool_calls = msg.get("tool_calls") or _fallback_tool_calls_from_content(msg.get("content", ""))

        if not tool_calls:
            return Turn(user=user_text, final_text=msg.get("content") or "", traces=traces, raw_messages=list(history))

        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            try:
                args = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else (fn["arguments"] or {})
            except json.JSONDecodeError:
                args = {}
            result = T.call(name, **args)
            trace = ToolTrace(name=name, arguments=args, result=result)
            traces.append(trace)
            if on_trace:
                on_trace(trace)
            history.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": json.dumps(result)[:8000],
            })

    return Turn(
        user=user_text,
        final_text="(loop exceeded max steps without final answer)",
        traces=traces,
        raw_messages=list(history),
    )


def chat(history: list[dict] | None = None) -> Iterator[Turn]:
    """Generator: yields one Turn per user input. For REPL-style use."""
    history = history if history is not None else [system_message()]
    while True:
        try:
            user_text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not user_text:
            continue
        yield run(user_text, history=history)
