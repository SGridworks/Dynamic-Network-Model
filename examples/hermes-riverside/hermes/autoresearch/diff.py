"""Render the `hermes diff` PR-body markdown.

Shape:

    ---
    substation_id: SUB-001
    from_sha: abc1234
    to_sha: def5678
    eval_delta:
      correctness: 0.03
      ...
    ---

    # Autoresearch iteration N

    Target axis: correctness.

    ## Axis table
    | axis | baseline | candidate | delta |

    ## Diff
    ```diff
    <unified diff>
    ```
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path

import yaml

from evals.scoring import AXES
from hermes.autoresearch.apply import ApplyResult


@dataclass(frozen=True)
class DiffContext:
    substation_id: str
    from_sha: str
    to_sha: str
    iteration_label: str
    target_axis: str


def render_pr_body(
    ctx: DiffContext,
    old_text: str,
    new_text: str,
    result: ApplyResult,
) -> str:
    fm = {
        "substation_id": ctx.substation_id,
        "from_sha": ctx.from_sha,
        "to_sha": ctx.to_sha,
        "target_axis": ctx.target_axis,
        "eval_delta": result.delta.as_dict() if result.delta else {},
    }
    fm_yaml = yaml.safe_dump(fm, sort_keys=False).strip()

    lines = [
        "---",
        fm_yaml,
        "---",
        "",
        f"# Autoresearch iteration {ctx.iteration_label}",
        "",
        f"Target axis: **{ctx.target_axis}**.",
        "",
        "## Axis table",
        "",
        "| axis | baseline | candidate | delta |",
        "|---|---|---|---|",
    ]
    b = result.baseline
    c = result.candidate
    d = result.delta
    if c is not None and d is not None:
        for axis in AXES:
            bv = getattr(b, axis)
            cv = getattr(c, axis)
            dv = getattr(d, axis)
            lines.append(f"| {axis} | {bv:.2f} | {cv:.2f} | {dv:+.2f} |")
    lines.extend(["", "## Diff", "", "```diff"])
    for dl in unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile="HERMES.md",
        tofile="HERMES.md (proposed)",
        lineterm="",
    ):
        lines.append(dl)
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def write_pr_body(ctx: DiffContext, old_text: str, new_text: str, result: ApplyResult, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_pr_body(ctx, old_text, new_text, result))
