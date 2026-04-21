"""Tests for hermes/autoresearch/apply.py.

The apply stage runs the eval harness against both the baseline and the
candidate, then gates on Pareto non-regression. Four paths:

  - accept: every axis matches or improves
  - reject_regression: one axis regresses
  - accept (tie): all axes exactly equal
  - reject_crash: eval function raises
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from evals.scoring import AxisScores, Score
from hermes.autoresearch.apply import (
    ApplyDecision,
    AxisDelta,
    apply_and_score,
)


def _score(**kwargs) -> Score:
    """Build a Score with AxisScores as kwargs and placeholder fields."""
    return Score(qid="x", axes=AxisScores(**kwargs), tools_called=[], answer="")


def _evaluator(baseline: AxisScores, candidate: AxisScores) -> Callable:
    """Return a fake evaluate() that returns one score per call, switching by path."""
    baseline_path_seen = {"count": 0}

    def fake_evaluate(path: Path, qa_pairs: list[dict]) -> list[Score]:
        # First call is the baseline; second is the candidate.
        if baseline_path_seen["count"] == 0:
            baseline_path_seen["count"] += 1
            return [_score(**baseline.as_dict())]
        return [_score(**candidate.as_dict())]

    return fake_evaluate


def test_accept_strict_improvement(tmp_path: Path) -> None:
    base = AxisScores(0.7, 0.8, 0.8, 0.5)
    cand = AxisScores(0.8, 0.8, 0.8, 0.7)
    evaluate = _evaluator(base, cand)
    result = apply_and_score(
        candidate_path=tmp_path / "cand.md",
        baseline_path=tmp_path / "base.md",
        qa_pairs=[{"id": "x"}],
        evaluate=evaluate,
    )
    assert result.decision == ApplyDecision.ACCEPT
    assert result.candidate == cand
    assert result.baseline == base
    assert result.delta == AxisDelta.of(cand, base)


def test_accept_tie_all_equal(tmp_path: Path) -> None:
    base = AxisScores(0.8, 0.9, 0.9, 0.7)
    result = apply_and_score(
        candidate_path=tmp_path / "cand.md",
        baseline_path=tmp_path / "base.md",
        qa_pairs=[{"id": "x"}],
        evaluate=_evaluator(base, base),
    )
    assert result.decision == ApplyDecision.ACCEPT


def test_reject_on_single_axis_regression(tmp_path: Path) -> None:
    base = AxisScores(0.8, 0.9, 0.9, 0.7)
    cand = AxisScores(0.8, 0.9, 0.89, 0.7)  # cite_coverage regresses by 0.01
    result = apply_and_score(
        candidate_path=tmp_path / "cand.md",
        baseline_path=tmp_path / "base.md",
        qa_pairs=[{"id": "x"}],
        evaluate=_evaluator(base, cand),
    )
    assert result.decision == ApplyDecision.REJECT_REGRESSION
    assert result.delta is not None
    assert result.delta.cite_coverage < 0


def test_reject_mixed_gain_and_regression(tmp_path: Path) -> None:
    """Even if 3 axes improve, any regression on the 4th rejects the candidate."""
    base = AxisScores(0.5, 0.5, 0.5, 0.5)
    cand = AxisScores(0.9, 0.9, 0.9, 0.49)
    result = apply_and_score(
        candidate_path=tmp_path / "cand.md",
        baseline_path=tmp_path / "base.md",
        qa_pairs=[{"id": "x"}],
        evaluate=_evaluator(base, cand),
    )
    assert result.decision == ApplyDecision.REJECT_REGRESSION


def test_reject_crash_when_evaluate_raises(tmp_path: Path) -> None:
    def boom(path: Path, qa_pairs: list[dict]) -> list[Score]:
        raise RuntimeError("ollama hung")

    result = apply_and_score(
        candidate_path=tmp_path / "cand.md",
        baseline_path=tmp_path / "base.md",
        qa_pairs=[{"id": "x"}],
        evaluate=boom,
    )
    assert result.decision == ApplyDecision.REJECT_CRASH
    assert result.error and "ollama hung" in result.error
    assert result.candidate is None
    assert result.delta is None
