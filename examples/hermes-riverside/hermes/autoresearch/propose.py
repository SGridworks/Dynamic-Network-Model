"""Propose a HERMES.md edit targeted at the lowest-scoring axis.

The LLM receives:
  - the current playbook text
  - the most recent axis scores (baseline)
  - which axis is lowest (the target)

It must return an ENTIRE new HERMES.md file, frontmatter preserved. The
response is validated against the schema + section contract before anything
else runs. Invalid responses raise InvalidProposal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from evals.scoring import AXES, AxisScores
from hermes.schema import SchemaViolation, load_frontmatter

PROPOSAL_SYSTEM_PROMPT = """\
You are an editor improving a substation operations playbook called HERMES.md.
You will be given the current playbook text and recent eval scores on four
axes: correctness, tool_discipline, cite_coverage, brevity.

Your job: propose one targeted improvement to raise the lowest-scoring axis
WITHOUT regressing any other axis.

OUTPUT FORMAT (strict — these rules are non-negotiable):

1. Your entire response is ONLY the new HERMES.md file. No commentary before
   or after. No markdown code fences around the file. Just the file.

2. The response MUST start with `---` on the first line (the YAML frontmatter
   opener). Keep all frontmatter fields exactly as given unless incrementing
   the `version` field.

3. The response MUST contain these exact `##` section headers, on their own
   lines, in this order: `## Identity`, `## Playbooks`, `## Memory`. Never
   rename them. Never omit any. Never merge them. Never drop a section
   because you did not touch it — repeat it verbatim from the input.

4. Every `### <event_kind>` subsection that was in the input MUST still be
   in the output with its code-block template preserved. If you edit a
   playbook, edit in place; do not delete others.

Keep edits minimal. If you cannot find a safe improvement, return the file
UNCHANGED (still obeying all rules above). It is better to return an
unchanged file than a truncated one.
"""


class InvalidProposal(ValueError):
    """Raised when an LLM-proposed edit fails schema or structural checks."""


@dataclass(frozen=True)
class ProposalContext:
    current_text: str
    baseline: AxisScores
    target_axis: str

    @classmethod
    def from_scores(cls, current_text: str, baseline: AxisScores) -> "ProposalContext":
        lowest = min(AXES, key=lambda a: getattr(baseline, a))
        return cls(current_text=current_text, baseline=baseline, target_axis=lowest)


LLMCallable = Callable[[list[dict]], str]
"""A function that takes a litellm-style messages list and returns the raw text."""

PROPOSE_RETRIES = 3
"""How many times to ask the LLM before giving up and returning InvalidProposal.

Smaller models are stochastically sloppy about preserving all required sections
on long-form rewrites. One bad sample is cheap to retry; three bad samples is
a real signal the model cannot handle the task.
"""


def propose_edit(ctx: ProposalContext, llm: LLMCallable) -> str:
    """Call the LLM and validate the response. Retries up to PROPOSE_RETRIES
    times on structural failures before raising InvalidProposal with the last
    error.

    Returns the candidate HERMES.md text on success.
    """
    user = _render_user_prompt(ctx)
    messages = [
        {"role": "system", "content": PROPOSAL_SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
    last_err: InvalidProposal | None = None
    for _ in range(PROPOSE_RETRIES):
        raw = llm(messages)
        try:
            return _validate_candidate(raw)
        except InvalidProposal as e:
            last_err = e
    assert last_err is not None
    raise last_err


def _render_user_prompt(ctx: ProposalContext) -> str:
    b = ctx.baseline
    return (
        f"Baseline axis scores (higher is better, 0.0-1.0):\n"
        f"  correctness:     {b.correctness:.2f}\n"
        f"  tool_discipline: {b.tool_discipline:.2f}\n"
        f"  cite_coverage:   {b.cite_coverage:.2f}\n"
        f"  brevity:         {b.brevity:.2f}\n"
        f"\nTarget axis to raise: {ctx.target_axis}\n"
        f"\nCURRENT HERMES.md:\n\n"
        f"{ctx.current_text}\n"
    )


def _validate_candidate(raw: str) -> str:
    stripped = raw.strip()
    if not stripped:
        raise InvalidProposal("LLM returned empty response")
    if not stripped.startswith("---"):
        raise InvalidProposal(
            "candidate does not start with YAML frontmatter (expected `---`)"
        )
    try:
        load_frontmatter(stripped + ("\n" if not stripped.endswith("\n") else ""))
    except SchemaViolation as e:
        raise InvalidProposal(f"candidate frontmatter invalid: {e}") from e
    # Ensure the three required sections appear as full-line `## Heading` entries.
    for heading in ("Identity", "Playbooks", "Memory"):
        pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
        if not pattern.search(stripped):
            raise InvalidProposal(f"candidate missing required section: ## {heading}")
    return stripped + ("\n" if not stripped.endswith("\n") else "")
