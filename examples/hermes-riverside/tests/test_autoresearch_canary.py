"""Canary tests for the autoresearch pipeline.

Each case in evals/autoresearch_canary.yaml specifies an LLM response and the
expected outcome. The test runs the response through propose → apply with
synthetic baseline/candidate scores and asserts the outcome matches.

This is the load-bearing test that lets us say "autoresearch works" with more
than hand-waving.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from evals.scoring import AxisScores, Score
from hermes.autoresearch.apply import ApplyDecision, apply_and_score
from hermes.autoresearch.propose import (
    InvalidProposal,
    ProposalContext,
    propose_edit,
)

CANARY_PATH = Path(__file__).resolve().parent.parent / "evals" / "autoresearch_canary.yaml"


def _load_cases() -> list[dict]:
    return yaml.safe_load(CANARY_PATH.read_text())


def _axes(d: dict) -> AxisScores:
    return AxisScores(
        correctness=d["correctness"],
        tool_discipline=d["tool_discipline"],
        cite_coverage=d["cite_coverage"],
        brevity=d["brevity"],
    )


def _run_case(case: dict, tmp_path: Path) -> str:
    """Run one canary case end-to-end. Returns the outcome string."""
    baseline = _axes(case["baseline"])
    ctx = ProposalContext.from_scores(
        current_text="---\nschema_version: \"0.1\"\n---\n",  # dummy; unused
        baseline=baseline,
    )

    llm = lambda _msgs: case["llm_response"]  # noqa: E731
    try:
        candidate_text = propose_edit(ctx, llm)
    except InvalidProposal:
        return "rejected_proposal"

    # Propose accepted the structure; now run the Pareto gate with the supplied
    # candidate scores.
    cand_axes = _axes(case["candidate"]) if "candidate" in case else baseline

    target = tmp_path / "HERMES-baseline.md"
    target.write_text("baseline placeholder")
    scratch = tmp_path / "HERMES-candidate.md"
    scratch.write_text(candidate_text)

    first_call = {"done": False}

    def fake_evaluate(path: Path, qa_pairs: list[dict]) -> list[Score]:
        if not first_call["done"]:
            first_call["done"] = True
            axes = baseline
        else:
            axes = cand_axes
        return [Score(qid="x", axes=axes, tools_called=[], answer="")]

    result = apply_and_score(
        candidate_path=scratch,
        baseline_path=target,
        qa_pairs=[{"id": "x"}],
        evaluate=fake_evaluate,
    )
    return result.decision.value


def test_canary_file_loads_and_is_non_empty() -> None:
    cases = _load_cases()
    assert cases, "autoresearch_canary.yaml parsed empty"
    for case in cases:
        assert "id" in case
        assert "kind" in case
        assert case["kind"] in {"obvious_bad", "obvious_good", "ambiguous"}
        assert case["expected_outcome"] in {
            "rejected_proposal",
            "reject_regression",
            ApplyDecision.ACCEPT.value,
        }


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_canary_case(case: dict, tmp_path: Path) -> None:
    actual = _run_case(case, tmp_path)
    assert actual == case["expected_outcome"], (
        f"{case['id']} ({case['kind']}): expected {case['expected_outcome']}, got {actual}"
    )


def test_canary_has_coverage_for_each_kind() -> None:
    """We want at least one of each kind so regressions in any category are caught."""
    cases = _load_cases()
    kinds = {c["kind"] for c in cases}
    assert kinds == {"obvious_bad", "obvious_good", "ambiguous"}
    assert sum(1 for c in cases if c["kind"] == "obvious_bad") >= 3
    assert sum(1 for c in cases if c["kind"] == "obvious_good") >= 2
    assert sum(1 for c in cases if c["kind"] == "ambiguous") >= 2
