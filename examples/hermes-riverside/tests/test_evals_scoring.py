"""Pure scoring tests for evals/run.py. No live agent turns.

Exercises the four axes directly against fabricated answers, plus the Pareto
gate and aggregate helpers. Existing qa_pairs.yaml is also smoke-tested to
confirm the new 4-axis scorer scores every old pair without crashing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from evals.scoring import (
    AXES,
    AxisScores,
    Score,
    _brevity,
    _cite_coverage,
    _correctness,
    _tool_discipline,
    aggregate,
    pareto_non_regressing,
    score_pair,
)

PAIRS_PATH = Path(__file__).resolve().parent.parent / "evals" / "qa_pairs.yaml"


# --- individual axis scorers -----------------------------------------------


def test_correctness_all_keywords_present() -> None:
    assert _correctness("foo bar baz", ["foo", "baz"]) == 1.0


def test_correctness_partial() -> None:
    assert _correctness("foo", ["foo", "baz"]) == 0.5


def test_correctness_empty_expected_scores_one() -> None:
    assert _correctness("whatever", []) == 1.0


def test_correctness_is_case_insensitive() -> None:
    assert _correctness("The Grid Is Up", ["grid"]) == 1.0


def test_tool_discipline_all_called() -> None:
    assert _tool_discipline(["a", "b", "c"], ["a", "b"]) == 1.0


def test_tool_discipline_missing_one() -> None:
    assert _tool_discipline(["a"], ["a", "b"]) == 0.5


def test_tool_discipline_no_expected() -> None:
    assert _tool_discipline([], []) == 1.0


def test_cite_coverage_all_present() -> None:
    assert _cite_coverage("see SUB-01 and FDR-0002", ["SUB-01", "FDR-0002"]) == 1.0


def test_cite_coverage_missing() -> None:
    assert _cite_coverage("see SUB-01", ["SUB-01", "FDR-0002"]) == 0.5


def test_cite_coverage_none_expected() -> None:
    assert _cite_coverage("whatever", None) == 1.0


def test_brevity_on_target() -> None:
    answer = " ".join(["word"] * 100)
    assert _brevity(answer, 100) == 1.0


def test_brevity_over_target_penalizes() -> None:
    answer = " ".join(["word"] * 150)
    assert _brevity(answer, 100) == pytest.approx(0.5)


def test_brevity_under_target_penalizes() -> None:
    answer = " ".join(["word"] * 50)
    assert _brevity(answer, 100) == pytest.approx(0.5)


def test_brevity_empty_answer_scores_zero() -> None:
    assert _brevity("", 50) == 0.0


def test_brevity_no_target_scores_one() -> None:
    assert _brevity("short", None) == 1.0


def test_brevity_clamps_at_zero() -> None:
    answer = " ".join(["word"] * 1000)
    assert _brevity(answer, 10) == 0.0


# --- score_pair composition -----------------------------------------------


def test_score_pair_all_axes_one_when_everything_matches() -> None:
    pair = {
        "id": "x",
        "expected_keywords": ["hello"],
        "expected_tools": ["t1"],
        "expected_cited_ids": ["ID-1"],
        "target_word_count": 2,
    }
    s = score_pair(pair, "hello ID-1", ["t1"])
    assert s.axes.correctness == 1.0
    assert s.axes.tool_discipline == 1.0
    assert s.axes.cite_coverage == 1.0
    assert s.axes.brevity == 1.0


def test_score_pair_backward_compat_flags() -> None:
    pair = {"id": "x", "expected_keywords": ["foo"], "expected_tools": ["t"]}
    s = score_pair(pair, "foo", ["t"])
    assert s.tools_ok is True
    assert s.keywords_ok is True


def test_score_pair_degrades_gracefully_on_empty_answer() -> None:
    pair = {
        "id": "x",
        "expected_keywords": ["foo"],
        "expected_tools": ["t"],
        "target_word_count": 50,
    }
    s = score_pair(pair, "", [])
    assert s.axes.correctness == 0.0
    assert s.axes.tool_discipline == 0.0
    assert s.axes.brevity == 0.0
    assert s.axes.cite_coverage == 1.0  # no expected_cited_ids


# --- Pareto + aggregate ---------------------------------------------------


def test_pareto_equal_is_non_regressing() -> None:
    a = AxisScores(0.8, 0.9, 0.7, 0.85)
    assert pareto_non_regressing(a, a) is True


def test_pareto_strict_improvement_is_non_regressing() -> None:
    base = AxisScores(0.8, 0.9, 0.7, 0.85)
    better = AxisScores(0.9, 0.9, 0.7, 0.85)
    assert pareto_non_regressing(better, base) is True


def test_pareto_regression_on_any_axis_fails() -> None:
    base = AxisScores(0.8, 0.9, 0.7, 0.85)
    for axis in AXES:
        regressed = AxisScores(**{**base.as_dict(), axis: getattr(base, axis) - 0.01})
        assert pareto_non_regressing(regressed, base) is False, axis


def test_aggregate_means_the_axes() -> None:
    scores = [
        Score("a", AxisScores(1.0, 0.5, 0.5, 0.5), [], ""),
        Score("b", AxisScores(0.0, 1.0, 0.5, 0.5), [], ""),
    ]
    agg = aggregate(scores)
    assert agg.correctness == 0.5
    assert agg.tool_discipline == 0.75
    assert agg.cite_coverage == 0.5
    assert agg.brevity == 0.5


def test_aggregate_empty_is_all_zero() -> None:
    assert aggregate([]) == AxisScores(0.0, 0.0, 0.0, 0.0)


# --- REGRESSION: existing qa_pairs.yaml still scorable --------------------


def test_existing_qa_pairs_all_score_without_crash() -> None:
    """Every pair in evals/qa_pairs.yaml must score cleanly under the new 4-axis
    scorer. No expected_cited_ids or target_word_count → those axes default to 1.0.
    This is the load-bearing backward-compat guarantee."""
    pairs = yaml.safe_load(PAIRS_PATH.read_text())
    assert pairs, "evals/qa_pairs.yaml is empty"
    for pair in pairs:
        s = score_pair(pair, "placeholder answer with SUB-01 and 230", [])
        for axis in AXES:
            v = getattr(s.axes, axis)
            assert 0.0 <= v <= 1.0, f"{pair['id']} {axis} out of bounds: {v}"
        # Backward-compat: old pairs have no brevity/cite target → both axes == 1.0
        if "target_word_count" not in pair:
            assert s.axes.brevity == 1.0, f"{pair['id']} brevity should be 1.0"
        if "expected_cited_ids" not in pair:
            assert s.axes.cite_coverage == 1.0, f"{pair['id']} cite_coverage should be 1.0"
