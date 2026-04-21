"""Tests for hermes/autoresearch/diff.py — PR-body markdown rendering."""

from __future__ import annotations

import re

import yaml

from evals.scoring import AxisScores
from hermes.autoresearch.apply import ApplyDecision, ApplyResult, AxisDelta
from hermes.autoresearch.diff import DiffContext, render_pr_body


def _result() -> ApplyResult:
    base = AxisScores(0.7, 0.8, 0.9, 0.5)
    cand = AxisScores(0.8, 0.8, 0.9, 0.7)
    return ApplyResult(
        decision=ApplyDecision.ACCEPT,
        baseline=base,
        candidate=cand,
        delta=AxisDelta.of(cand, base),
        error=None,
    )


def _ctx() -> DiffContext:
    return DiffContext(
        substation_id="SUB-001",
        from_sha="abc1234",
        to_sha="def5678",
        iteration_label="42",
        target_axis="brevity",
    )


def test_frontmatter_round_trips_as_yaml() -> None:
    body = render_pr_body(_ctx(), "old\nline\n", "new\nline\n", _result())
    m = re.match(r"^---\n(.*?)\n---\n", body, re.DOTALL)
    assert m, "frontmatter missing"
    fm = yaml.safe_load(m.group(1))
    assert fm["substation_id"] == "SUB-001"
    assert fm["from_sha"] == "abc1234"
    assert fm["to_sha"] == "def5678"
    assert fm["target_axis"] == "brevity"
    assert set(fm["eval_delta"]) == {"correctness", "tool_discipline", "cite_coverage", "brevity"}


def test_body_has_iteration_header_and_target() -> None:
    body = render_pr_body(_ctx(), "a\n", "b\n", _result())
    assert "# Autoresearch iteration 42" in body
    assert "Target axis: **brevity**" in body


def test_axis_table_has_one_row_per_axis() -> None:
    body = render_pr_body(_ctx(), "a\n", "b\n", _result())
    for axis in ("correctness", "tool_discipline", "cite_coverage", "brevity"):
        assert re.search(rf"\|\s*{axis}\s*\|", body), f"missing row for {axis}"


def test_diff_block_contains_unified_diff_markers() -> None:
    body = render_pr_body(_ctx(), "line one\nline two\n", "line one\nline CHANGED\n", _result())
    assert "```diff" in body
    assert "--- HERMES.md" in body
    assert "+++ HERMES.md (proposed)" in body
    assert "-line two" in body
    assert "+line CHANGED" in body


def test_handles_result_with_no_candidate() -> None:
    result = ApplyResult(
        decision=ApplyDecision.REJECT_CRASH,
        baseline=AxisScores(0.0, 0.0, 0.0, 0.0),
        candidate=None,
        delta=None,
        error="boom",
    )
    body = render_pr_body(_ctx(), "a\n", "b\n", result)
    assert "Target axis:" in body  # header still renders
    # No axis-table rows for absent delta.
    assert not re.search(r"\|\s*correctness\s*\|\s*0\.\d", body)
