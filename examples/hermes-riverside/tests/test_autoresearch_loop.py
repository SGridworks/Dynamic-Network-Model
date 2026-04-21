"""Integration tests for hermes/autoresearch/loop.py using fake GitClient/GhClient.

Covers:
  - minor accept → commits to autoresearch/YYYY-MM-DD, pushes when auto_push
  - major accept (identity change) → opens PR, returns to default branch
  - invalid proposal → rejected_proposal outcome, no git action
  - regression → reject_regression outcome, no git action
  - three consecutive regressions → kill-switch halts loop, remaining targets skipped
  - ledger rotates at 100 entries
  - replay JSON written with full text + axes
  - auto_push=False skips remote operations
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from evals.scoring import AxisScores, Score
from hermes.autoresearch.apply import ApplyDecision
from hermes.autoresearch.commit import (
    KillSwitchState,
    load_killswitch,
    save_killswitch,
)
from hermes.autoresearch.loop import (
    LEDGER_MAX_ITERATIONS,
    LoopConfig,
    run_loop,
)


VALID_PLAYBOOK = """---
schema_version: "0.1"
substation_id: SUB-777
substation_name: Testville
archetype:
  topology: urban_radial
  load_mix: mixed
  climate: temperate
  criticality: standard
version: 0.1.0
---

# HERMES.md

## Identity

You are Hermes at Testville. Original identity for the loop test.

## Playbooks

### event_one

Description.

```
Trigger: {source} on {feeder_id}.

Respond.
```

## Memory

Memory posture.
"""


# --- Fakes ---------------------------------------------------------------


class FakeGit:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.current_branch = "main"
        self.sha_counter = 0

    def head_sha(self, repo: Path) -> str:
        self.sha_counter += 1
        return f"sha{self.sha_counter:04d}"

    def commit_file(self, repo: Path, path: Path, message: str) -> str:
        self.calls.append(("commit", str(path.relative_to(repo)), message, self.current_branch))
        return self.head_sha(repo)

    def push(self, repo: Path, branch: str) -> None:
        self.calls.append(("push", branch))

    def checkout_branch(self, repo: Path, branch: str) -> None:
        self.calls.append(("checkout", branch))
        self.current_branch = branch


class FakeGh:
    def __init__(self, returns_url: str = "https://example/pr/1") -> None:
        self.returns_url = returns_url
        self.calls: list[dict] = []

    def create_pr(self, repo: Path, title: str, body: str, base: str, head: str) -> str:
        self.calls.append({"title": title, "body": body, "base": base, "head": head})
        return self.returns_url


def _mk_config(tmp_path: Path, playbook_text: str = VALID_PLAYBOOK) -> tuple[LoopConfig, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()  # placeholder so relative_to works
    target = repo / "HERMES.md"
    target.write_text(playbook_text)
    cfg = LoopConfig(
        repo_root=repo,
        targets=[target],
        qa_pairs=[{"id": "x"}],
        killswitch_path=tmp_path / "ks.json",
        runs_dir=tmp_path / "runs",
        ledger_path=tmp_path / "ledger.json",
        default_branch="main",
        auto_push=True,
    )
    return cfg, target


def _scorer(baseline: AxisScores, candidate: AxisScores | None = None):
    """Return an evaluate() that returns candidate scores when evaluating a
    scratch file under a temp dir, else baseline. This stays correct across
    multiple targets."""
    import tempfile

    tmp_root = tempfile.gettempdir()

    def fake_evaluate(path: Path, qa_pairs: list[dict]) -> list[Score]:
        use_candidate = candidate is not None and str(path).startswith(tmp_root)
        target_scores = candidate if use_candidate else baseline
        return [Score(qid="x", axes=target_scores, tools_called=[], answer="")]

    return fake_evaluate


def _llm_returns(text: str):
    return lambda _msgs: text


def _fixed_now():
    def _n():
        return datetime(2026, 4, 21, 10, 30, 0, tzinfo=timezone.utc)
    return _n


# --- Tests --------------------------------------------------------------


def test_minor_accept_commits_and_pushes(tmp_path: Path) -> None:
    cfg, target = _mk_config(tmp_path)
    # Change Memory-section text only — minor diff (< 20 lines, no Identity touch,
    # no playbook add/remove).
    improved = VALID_PLAYBOOK.replace("Memory posture.", "Memory posture. Tightened.")
    # Improved only on brevity: scores candidate > baseline on brevity, equal elsewhere.
    baseline = AxisScores(0.7, 0.9, 0.9, 0.5)
    candidate = AxisScores(0.7, 0.9, 0.9, 0.7)
    git = FakeGit()
    gh = FakeGh()

    outcomes = run_loop(
        cfg,
        llm=_llm_returns(improved),
        evaluate=_scorer(baseline, candidate),
        git=git,
        gh=gh,
        now=_fixed_now(),
    )

    assert len(outcomes) == 1
    o = outcomes[0]
    assert o.decision == ApplyDecision.ACCEPT.value
    assert o.commit_kind == "minor_auto_commit"
    assert o.pr_url is None

    # Git interactions: checkout autoresearch/YYYY-MM-DD, commit, push, checkout main
    kinds = [c[0] for c in git.calls]
    assert kinds == ["checkout", "commit", "push", "checkout"]
    assert git.calls[0][1] == "autoresearch/2026-04-21"
    assert git.calls[-1][1] == "main"

    # No PR for minor
    assert gh.calls == []

    # Target file is now the improved text
    assert "Tightened" in target.read_text()


def test_major_accept_opens_pr_and_returns_to_main(tmp_path: Path) -> None:
    cfg, target = _mk_config(tmp_path)
    # Modifying Identity section → MAJOR diff
    improved = VALID_PLAYBOOK.replace(
        "Original identity for the loop test.",
        "A different identity with meaningful rewording that changes intent.",
    )
    baseline = AxisScores(0.5, 0.9, 0.9, 0.9)
    candidate = AxisScores(0.8, 0.9, 0.9, 0.9)
    git = FakeGit()
    gh = FakeGh()

    outcomes = run_loop(
        cfg,
        llm=_llm_returns(improved),
        evaluate=_scorer(baseline, candidate),
        git=git,
        gh=gh,
        now=_fixed_now(),
    )

    o = outcomes[0]
    assert o.decision == ApplyDecision.ACCEPT.value
    assert o.commit_kind == "major_pr"
    assert o.pr_url == "https://example/pr/1"

    # A PR was opened
    assert len(gh.calls) == 1
    pr = gh.calls[0]
    assert pr["base"] == "main"
    assert pr["head"].startswith("autoresearch/")
    assert "axis table" in pr["body"].lower() or "axis" in pr["body"].lower()

    # Checkout order: PR branch, commit, push, checkout main
    kinds = [c[0] for c in git.calls]
    assert kinds == ["checkout", "commit", "push", "checkout"]
    assert git.calls[-1][1] == "main"


def test_invalid_proposal_records_outcome_and_no_git(tmp_path: Path) -> None:
    cfg, _ = _mk_config(tmp_path)
    baseline = AxisScores(0.7, 0.9, 0.9, 0.5)
    git = FakeGit()
    gh = FakeGh()

    outcomes = run_loop(
        cfg,
        llm=_llm_returns("not a playbook"),
        evaluate=_scorer(baseline),
        git=git,
        gh=gh,
        now=_fixed_now(),
    )

    o = outcomes[0]
    assert o.decision == "rejected_proposal"
    assert "frontmatter" in (o.error or "").lower()
    assert git.calls == []
    assert gh.calls == []


def test_regression_rejection_no_git(tmp_path: Path) -> None:
    cfg, _ = _mk_config(tmp_path)
    # candidate regresses on correctness
    baseline = AxisScores(0.8, 0.9, 0.9, 0.7)
    candidate = AxisScores(0.75, 0.9, 0.9, 0.7)
    git = FakeGit()
    gh = FakeGh()

    improved = VALID_PLAYBOOK.replace("Description.", "Slightly-different description.")
    outcomes = run_loop(
        cfg,
        llm=_llm_returns(improved),
        evaluate=_scorer(baseline, candidate),
        git=git,
        gh=gh,
        now=_fixed_now(),
    )

    o = outcomes[0]
    assert o.decision == ApplyDecision.REJECT_REGRESSION.value
    assert o.delta is not None
    assert o.delta["correctness"] < 0
    assert git.calls == []
    assert gh.calls == []


def test_killswitch_halts_after_three_consecutive_regressions(tmp_path: Path) -> None:
    cfg, target = _mk_config(tmp_path)
    # Four targets; three in a row regress so the loop halts before the 4th.
    t2 = cfg.repo_root / "HERMES-b.md"
    t3 = cfg.repo_root / "HERMES-c.md"
    t4 = cfg.repo_root / "HERMES-d.md"
    for p, sid in [(t2, "SUB-100"), (t3, "SUB-101"), (t4, "SUB-102")]:
        txt = VALID_PLAYBOOK.replace("SUB-777", sid).replace("Testville", sid)
        p.write_text(txt)
    cfg.targets = [target, t2, t3, t4]

    baseline = AxisScores(0.8, 0.9, 0.9, 0.7)
    candidate = AxisScores(0.75, 0.9, 0.9, 0.7)  # regresses
    git = FakeGit()

    outcomes = run_loop(
        cfg,
        llm=_llm_returns(VALID_PLAYBOOK.replace("Description.", "Other description.")),
        evaluate=_scorer(baseline, candidate),
        git=git,
        gh=FakeGh(),
        now=_fixed_now(),
    )
    # 3 iterations ran, the 4th was skipped by the kill-switch.
    assert len(outcomes) == 3
    state = load_killswitch(cfg.killswitch_path)
    assert state.halted is True
    assert state.consecutive_regressions == 3


def test_auto_push_false_skips_push_and_pr(tmp_path: Path) -> None:
    cfg, _ = _mk_config(tmp_path)
    cfg.auto_push = False
    improved = VALID_PLAYBOOK.replace("Description.", "Tightened description.")
    baseline = AxisScores(0.7, 0.9, 0.9, 0.5)
    candidate = AxisScores(0.7, 0.9, 0.9, 0.7)
    git = FakeGit()
    gh = FakeGh()

    outcomes = run_loop(
        cfg,
        llm=_llm_returns(improved),
        evaluate=_scorer(baseline, candidate),
        git=git,
        gh=gh,
        now=_fixed_now(),
    )
    assert outcomes[0].decision == ApplyDecision.ACCEPT.value
    # No push, no PR, but commit + checkout happen locally.
    assert all(c[0] != "push" for c in git.calls), git.calls
    assert gh.calls == []


def test_replay_json_has_full_text_and_axes(tmp_path: Path) -> None:
    cfg, target = _mk_config(tmp_path)
    improved = VALID_PLAYBOOK.replace("Description.", "Sharper description.")
    baseline = AxisScores(0.7, 0.9, 0.9, 0.5)
    candidate = AxisScores(0.7, 0.9, 0.9, 0.7)

    run_loop(
        cfg,
        llm=_llm_returns(improved),
        evaluate=_scorer(baseline, candidate),
        git=FakeGit(),
        gh=FakeGh(),
        now=_fixed_now(),
    )

    json_files = list(cfg.runs_dir.rglob("*.json"))
    assert len(json_files) == 1
    payload = json.loads(json_files[0].read_text())
    assert payload["substation_id"] == "SUB-777"
    assert "Sharper" in payload["new_text"]
    assert "Sharper" not in payload["old_text"]
    assert payload["baseline_axes"]["brevity"] == 0.5
    assert payload["candidate_axes"]["brevity"] == 0.7


def test_ledger_rotates_at_max_iterations(tmp_path: Path) -> None:
    """Pre-seed the ledger at the limit, run one more iteration, verify oldest dropped."""
    cfg, _ = _mk_config(tmp_path)
    pre = [{"iteration_id": f"old-{i}", "timestamp": "old"} for i in range(LEDGER_MAX_ITERATIONS)]
    cfg.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.ledger_path.write_text(json.dumps(pre))

    baseline = AxisScores(0.7, 0.9, 0.9, 0.5)
    run_loop(
        cfg,
        llm=_llm_returns("garbage"),  # rejected_proposal; still appends to ledger
        evaluate=_scorer(baseline),
        git=FakeGit(),
        gh=FakeGh(),
        now=_fixed_now(),
    )

    after = json.loads(cfg.ledger_path.read_text())
    assert len(after) == LEDGER_MAX_ITERATIONS
    # Newest is at position 0; oldest ("old-99") is dropped.
    assert after[0]["iteration_id"] != "old-0"
    ids = {e["iteration_id"] for e in after}
    assert "old-99" not in ids  # oldest dropped
    assert "old-0" in ids       # second-oldest survives


def test_acceptance_resets_killswitch(tmp_path: Path) -> None:
    cfg, _ = _mk_config(tmp_path)
    # Pre-seed: 2 regressions already logged
    save_killswitch(KillSwitchState(consecutive_regressions=2, halted=False), cfg.killswitch_path)

    improved = VALID_PLAYBOOK.replace("Description.", "Tighter description.")
    baseline = AxisScores(0.7, 0.9, 0.9, 0.5)
    candidate = AxisScores(0.7, 0.9, 0.9, 0.7)

    run_loop(
        cfg,
        llm=_llm_returns(improved),
        evaluate=_scorer(baseline, candidate),
        git=FakeGit(),
        gh=FakeGh(),
        now=_fixed_now(),
    )
    state = load_killswitch(cfg.killswitch_path)
    assert state.consecutive_regressions == 0
    assert state.halted is False


def test_baseline_eval_crash_reports_without_git(tmp_path: Path) -> None:
    cfg, _ = _mk_config(tmp_path)
    git = FakeGit()

    def boom(path: Path, pairs: list[dict]) -> list[Score]:
        raise RuntimeError("ollama down")

    outcomes = run_loop(
        cfg,
        llm=_llm_returns(VALID_PLAYBOOK),
        evaluate=boom,
        git=git,
        gh=FakeGh(),
        now=_fixed_now(),
    )
    assert outcomes[0].decision == ApplyDecision.REJECT_CRASH.value
    assert "ollama down" in (outcomes[0].error or "")
    assert git.calls == []
