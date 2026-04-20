"""Run showcase scenarios against a live backend and write replayable trace JSON.

Run once (or whenever scenarios change). Commit the output.

    .venv/bin/python -m hermes.cli record --scenario 01-afternoon-der
    .venv/bin/python -m hermes.cli record --scenario all
"""

from __future__ import annotations

import time
from pathlib import Path

from rich.console import Console

from hermes.agent.loop import run as run_turn
from hermes.agent.prompts import system_message
from hermes.config import load_or_exit
from hermes.showcase.trace import from_turn
from scripts.scenarios import SCENARIOS, Scenario, by_id

console = Console()


def _record(scenario: Scenario, out_dir: Path) -> Path:
    cfg = load_or_exit()
    history = [system_message()]
    console.print(f"[cyan]scenario {scenario.id}[/cyan]: {scenario.title}")
    t0 = time.monotonic()
    turn = run_turn(scenario.query, history=history)
    elapsed = time.monotonic() - t0
    trace = from_turn(
        scenario.id,
        scenario.title,
        scenario.query,
        turn,
        provider=cfg.provider,
        model=cfg.model,
        elapsed=elapsed,
    )
    target = out_dir / f"{scenario.id}.json"
    trace.save(target)
    console.print(
        f"  → wrote {target} "
        f"({len(trace.tool_calls)} tool calls, {elapsed:.1f}s)"
    )
    return target


def record_one(scenario_id: str, out_dir: Path) -> None:
    _record(by_id(scenario_id), out_dir)


def record_all(out_dir: Path) -> None:
    for s in SCENARIOS:
        _record(s, out_dir)


if __name__ == "__main__":
    record_all(Path("fixtures/traces"))
