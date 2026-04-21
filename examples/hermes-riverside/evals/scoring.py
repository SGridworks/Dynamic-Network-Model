"""Pure scoring functions for the eval harness.

Lives separately from run.py so tests can import these without triggering
the full agent/LLM import graph.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

AXES = ("correctness", "tool_discipline", "cite_coverage", "brevity")


@dataclass
class AxisScores:
    correctness: float
    tool_discipline: float
    cite_coverage: float
    brevity: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class Score:
    qid: str
    axes: AxisScores
    tools_called: list[str]
    answer: str

    @property
    def tools_ok(self) -> bool:
        return self.axes.tool_discipline >= 1.0

    @property
    def keywords_ok(self) -> bool:
        return self.axes.correctness >= 1.0


def _correctness(answer: str, expected_keywords: list[str]) -> float:
    if not expected_keywords:
        return 1.0
    hits = sum(1 for kw in expected_keywords if kw.lower() in answer.lower())
    return hits / len(expected_keywords)


def _tool_discipline(called: list[str], expected: list[str]) -> float:
    if not expected:
        return 1.0
    hits = sum(1 for t in expected if t in called)
    return hits / len(expected)


def _cite_coverage(answer: str, expected_ids: list[str] | None) -> float:
    if not expected_ids:
        return 1.0
    hits = sum(1 for cid in expected_ids if cid in answer)
    return hits / len(expected_ids)


def _brevity(answer: str, target_word_count: int | None) -> float:
    if target_word_count is None or target_word_count <= 0:
        return 1.0
    actual = len(answer.split())
    if actual == 0:
        return 0.0
    delta = abs(actual - target_word_count)
    return max(0.0, 1.0 - delta / target_word_count)


def score_pair(pair: dict, answer: str, tools_called: list[str]) -> Score:
    axes = AxisScores(
        correctness=_correctness(answer, pair.get("expected_keywords", [])),
        tool_discipline=_tool_discipline(tools_called, pair.get("expected_tools", [])),
        cite_coverage=_cite_coverage(answer, pair.get("expected_cited_ids")),
        brevity=_brevity(answer, pair.get("target_word_count")),
    )
    return Score(qid=pair["id"], axes=axes, tools_called=tools_called, answer=answer)


def pareto_non_regressing(new: AxisScores, baseline: AxisScores) -> bool:
    """True iff new is >= baseline on every axis (ties allowed)."""
    return all(getattr(new, a) >= getattr(baseline, a) for a in AXES)


def aggregate(scores: list[Score]) -> AxisScores:
    """Mean of each axis across a score list."""
    n = len(scores)
    if n == 0:
        return AxisScores(0.0, 0.0, 0.0, 0.0)
    return AxisScores(
        correctness=sum(s.axes.correctness for s in scores) / n,
        tool_discipline=sum(s.axes.tool_discipline for s in scores) / n,
        cite_coverage=sum(s.axes.cite_coverage for s in scores) / n,
        brevity=sum(s.axes.brevity for s in scores) / n,
    )
