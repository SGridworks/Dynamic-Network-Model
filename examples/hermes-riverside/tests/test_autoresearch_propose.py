"""Tests for hermes/autoresearch/propose.py.

Four failure modes:
  - empty LLM response
  - missing frontmatter
  - invalid frontmatter (bad enum, bad ID)
  - missing required `##` section

Plus the happy path: a valid candidate round-trips without mutation.
"""

from __future__ import annotations

import pytest

from evals.scoring import AxisScores
from hermes.autoresearch.propose import (
    InvalidProposal,
    ProposalContext,
    propose_edit,
)

VALID_CANDIDATE = """---
schema_version: "0.1"
substation_id: SUB-001
substation_name: Riverside
archetype:
  topology: urban_radial
  load_mix: der_heavy
  climate: desert_sw
  criticality: elevated
version: 0.1.1
---

# HERMES.md

## Identity

You are Hermes at Riverside. This is a valid proposed edit.

## Playbooks

### upper_band_voltage

A playbook template.

```
Trigger: {source} reports {value} on {feeder_id}.

Respond.
```

## Memory

Memory posture.
"""

BASELINE = AxisScores(correctness=0.7, tool_discipline=0.85, cite_coverage=0.9, brevity=0.5)


def _mk_ctx(current: str = VALID_CANDIDATE) -> ProposalContext:
    return ProposalContext.from_scores(current_text=current, baseline=BASELINE)


def test_target_axis_picks_lowest() -> None:
    ctx = _mk_ctx()
    assert ctx.target_axis == "brevity"  # 0.5 is lowest


def test_happy_path_returns_validated_candidate() -> None:
    ctx = _mk_ctx()
    llm = lambda _msgs: VALID_CANDIDATE  # noqa: E731
    out = propose_edit(ctx, llm)
    assert out.strip() == VALID_CANDIDATE.strip()


def test_empty_response_raises() -> None:
    ctx = _mk_ctx()
    with pytest.raises(InvalidProposal, match="empty"):
        propose_edit(ctx, lambda _msgs: "")


def test_whitespace_only_response_raises() -> None:
    ctx = _mk_ctx()
    with pytest.raises(InvalidProposal, match="empty"):
        propose_edit(ctx, lambda _msgs: "   \n\n  ")


def test_missing_frontmatter_raises() -> None:
    ctx = _mk_ctx()
    garbage = "# Just markdown\n\n## Identity\n\n## Playbooks\n\n### x\n\n```t```\n\n## Memory\n"
    with pytest.raises(InvalidProposal, match="frontmatter"):
        propose_edit(ctx, lambda _msgs: garbage)


def test_invalid_topology_enum_raises() -> None:
    ctx = _mk_ctx()
    bad = VALID_CANDIDATE.replace("topology: urban_radial", "topology: not_real")
    with pytest.raises(InvalidProposal, match="frontmatter"):
        propose_edit(ctx, lambda _msgs: bad)


def test_missing_identity_section_raises() -> None:
    ctx = _mk_ctx()
    no_identity = VALID_CANDIDATE.replace("## Identity", "## NotIdentity")
    with pytest.raises(InvalidProposal, match="Identity"):
        propose_edit(ctx, lambda _msgs: no_identity)


def test_missing_playbooks_section_raises() -> None:
    ctx = _mk_ctx()
    bad = VALID_CANDIDATE.replace("## Playbooks", "## Absent")
    with pytest.raises(InvalidProposal, match="Playbooks"):
        propose_edit(ctx, lambda _msgs: bad)


def test_missing_memory_section_raises() -> None:
    ctx = _mk_ctx()
    bad = VALID_CANDIDATE.replace("## Memory", "## MemoryGone")
    with pytest.raises(InvalidProposal, match="Memory"):
        propose_edit(ctx, lambda _msgs: bad)


def test_llm_timeout_bubbles_up_untouched() -> None:
    """If the LLM callable raises, we do NOT catch it. The cron layer sees the
    raw exception and decides whether to retry or halt."""
    ctx = _mk_ctx()

    def exploding_llm(_msgs):
        raise TimeoutError("Ollama unreachable")

    with pytest.raises(TimeoutError, match="Ollama unreachable"):
        propose_edit(ctx, exploding_llm)


def test_user_prompt_includes_baseline_scores() -> None:
    """Inspect the messages list the LLM sees to confirm the axis values are
    in the user prompt."""
    ctx = _mk_ctx()
    captured = []

    def capturing_llm(messages):
        captured.extend(messages)
        return VALID_CANDIDATE

    propose_edit(ctx, capturing_llm)
    user_content = next(m["content"] for m in captured if m["role"] == "user")
    assert "0.70" in user_content
    assert "0.50" in user_content
    assert "Target axis to raise: brevity" in user_content
