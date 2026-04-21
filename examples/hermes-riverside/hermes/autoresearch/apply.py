"""Score a candidate HERMES.md via the eval harness and apply the Pareto gate.

The gate is strict: a candidate is accepted only if its aggregate axis scores
are all greater-than-or-equal to the baseline. A regression on any axis (even
by 0.01) rejects the candidate. Ties are acceptable.

Scoring goes through a caller-supplied `evaluate` callable so tests can run
without Ollama. The production wiring calls evals.run._evaluate against the
scratch file via prompts.system_message(hermes_md_path=...).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from evals.scoring import AxisScores, Score, aggregate, pareto_non_regressing


class ApplyDecision(enum.Enum):
    ACCEPT = "accept"
    REJECT_REGRESSION = "reject_regression"
    REJECT_CRASH = "reject_crash"


@dataclass
class AxisDelta:
    """Per-axis new minus baseline."""
    correctness: float
    tool_discipline: float
    cite_coverage: float
    brevity: float

    @classmethod
    def of(cls, new: AxisScores, baseline: AxisScores) -> "AxisDelta":
        return cls(
            correctness=new.correctness - baseline.correctness,
            tool_discipline=new.tool_discipline - baseline.tool_discipline,
            cite_coverage=new.cite_coverage - baseline.cite_coverage,
            brevity=new.brevity - baseline.brevity,
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "correctness": self.correctness,
            "tool_discipline": self.tool_discipline,
            "cite_coverage": self.cite_coverage,
            "brevity": self.brevity,
        }


@dataclass
class ApplyResult:
    decision: ApplyDecision
    baseline: AxisScores
    candidate: AxisScores | None
    delta: AxisDelta | None
    error: str | None


EvaluateCallable = Callable[[Path, list[dict]], list[Score]]
"""Given (hermes_md_path, qa_pairs), return a score per pair."""


def apply_and_score(
    candidate_path: Path,
    baseline_path: Path,
    qa_pairs: list[dict],
    evaluate: EvaluateCallable,
) -> ApplyResult:
    """Run the eval against both the baseline and the candidate, apply the
    Pareto gate, and report.

    Any exception during evaluation results in REJECT_CRASH. This is the
    correct behavior for the cron: if we can't score the candidate, we don't
    accept it.
    """
    try:
        baseline_scores = evaluate(baseline_path, qa_pairs)
        candidate_scores = evaluate(candidate_path, qa_pairs)
    except Exception as e:  # noqa: BLE001
        return ApplyResult(
            decision=ApplyDecision.REJECT_CRASH,
            baseline=AxisScores(0.0, 0.0, 0.0, 0.0),
            candidate=None,
            delta=None,
            error=str(e),
        )

    baseline_agg = aggregate(baseline_scores)
    candidate_agg = aggregate(candidate_scores)

    if pareto_non_regressing(candidate_agg, baseline_agg):
        decision = ApplyDecision.ACCEPT
    else:
        decision = ApplyDecision.REJECT_REGRESSION

    return ApplyResult(
        decision=decision,
        baseline=baseline_agg,
        candidate=candidate_agg,
        delta=AxisDelta.of(candidate_agg, baseline_agg),
        error=None,
    )
