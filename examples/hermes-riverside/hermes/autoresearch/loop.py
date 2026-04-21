"""Cron entry point for the autoresearch loop.

Wires propose → apply → commit end-to-end. Subprocess interaction with git
and gh is hidden behind the GitClient protocol so tests can run with a fake.

One invocation performs one iteration per target playbook:

    for playbook_path in targets:
        if killswitch.halted: stop
        baseline_scores = evaluate(playbook_path)
        candidate = propose(current, baseline_scores)     # may raise
        result = apply_and_score(candidate, baseline)     # may REJECT_CRASH
        if result.decision == ACCEPT:
            classify major/minor, write, commit, (push OR open PR)
            write per-recommendation JSON under runs/
            append to public/autoresearch-ledger.json
        else:
            log rejection
        update killswitch state
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from evals.scoring import AxisScores, Score
from hermes.autoresearch.apply import ApplyDecision, ApplyResult, apply_and_score
from hermes.autoresearch.commit import (
    CommitKind,
    KillSwitchState,
    classify_diff,
    load_killswitch,
    record_outcome,
    save_killswitch,
)
from hermes.autoresearch.diff import DiffContext, render_pr_body
from hermes.autoresearch.propose import (
    InvalidProposal,
    ProposalContext,
    propose_edit,
)

logger = logging.getLogger(__name__)

LEDGER_MAX_ITERATIONS = 100


# --- Protocols: injected for tests --------------------------------------


class GitClient(Protocol):
    def head_sha(self, repo: Path) -> str: ...
    def commit_file(self, repo: Path, path: Path, message: str) -> str: ...
    def push(self, repo: Path, branch: str) -> None: ...
    def checkout_branch(self, repo: Path, branch: str) -> None: ...


class GhClient(Protocol):
    def create_pr(self, repo: Path, title: str, body: str, base: str, head: str) -> str: ...


LLMCallable = Callable[[list[dict]], str]
EvaluateCallable = Callable[[Path, list[dict]], list[Score]]


# --- Subprocess-backed production impls ---------------------------------


class SubprocessGit:
    def head_sha(self, repo: Path) -> str:
        return _run(["git", "rev-parse", "--short", "HEAD"], cwd=repo).strip()

    def commit_file(self, repo: Path, path: Path, message: str) -> str:
        _run(["git", "add", str(path.relative_to(repo))], cwd=repo)
        _run(["git", "commit", "-m", message], cwd=repo)
        return self.head_sha(repo)

    def push(self, repo: Path, branch: str) -> None:
        _run(["git", "push", "-u", "origin", branch], cwd=repo)

    def checkout_branch(self, repo: Path, branch: str) -> None:
        # Create if missing, otherwise switch.
        existing = _run(["git", "branch", "--list", branch], cwd=repo).strip()
        if existing:
            _run(["git", "checkout", branch], cwd=repo)
        else:
            _run(["git", "checkout", "-b", branch], cwd=repo)


class SubprocessGh:
    def create_pr(self, repo: Path, title: str, body: str, base: str, head: str) -> str:
        return _run(
            ["gh", "pr", "create", "--title", title, "--body", body, "--base", base, "--head", head],
            cwd=repo,
        ).strip()


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)
    return result.stdout


# --- Outcome + artifacts ------------------------------------------------


@dataclass
class IterationOutcome:
    substation_id: str
    iteration_id: str
    decision: str              # ApplyDecision value OR "rejected_proposal"
    target_axis: str | None
    commit_kind: str | None    # CommitKind value, if committed
    baseline: AxisScores | None
    candidate: AxisScores | None
    delta: dict[str, float] | None
    error: str | None
    timestamp: str
    commit_sha: str | None = None
    pr_url: str | None = None


@dataclass
class LoopConfig:
    repo_root: Path
    targets: list[Path]                 # paths to HERMES-*.md under repo
    qa_pairs: list[dict]
    killswitch_path: Path
    runs_dir: Path                       # where per-recommendation JSONs land
    ledger_path: Path                    # public/autoresearch-ledger.json
    default_branch: str = "main"
    auto_push: bool = True               # if False, commits stay local (review mode)


def run_loop(
    cfg: LoopConfig,
    llm: LLMCallable,
    evaluate: EvaluateCallable,
    git: GitClient | None = None,
    gh: GhClient | None = None,
    now: Callable[[], datetime] | None = None,
) -> list[IterationOutcome]:
    git = git or SubprocessGit()
    gh = gh or SubprocessGh()
    now = now or (lambda: datetime.now(timezone.utc))

    state = load_killswitch(cfg.killswitch_path)
    outcomes: list[IterationOutcome] = []

    for target in cfg.targets:
        if state.halted:
            logger.warning("kill-switch halted; skipping %s", target.name)
            break
        outcome = _one_iteration(
            target=target,
            cfg=cfg,
            llm=llm,
            evaluate=evaluate,
            git=git,
            gh=gh,
            now=now,
        )
        outcomes.append(outcome)

        accepted = outcome.decision == ApplyDecision.ACCEPT.value
        state = record_outcome(state, accepted=accepted, ts=outcome.timestamp)
        save_killswitch(state, cfg.killswitch_path)

        _append_to_ledger(cfg.ledger_path, outcome)

    return outcomes


def _one_iteration(
    target: Path,
    cfg: LoopConfig,
    llm: LLMCallable,
    evaluate: EvaluateCallable,
    git: GitClient,
    gh: GhClient,
    now: Callable[[], datetime],
) -> IterationOutcome:
    ts = now().isoformat()
    iteration_id = f"{now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    current_text = target.read_text()

    # Baseline evaluation on the target itself (needed both for proposal context
    # and as the comparison point for the apply gate).
    try:
        baseline_scores = evaluate(target, cfg.qa_pairs)
    except Exception as e:  # noqa: BLE001
        logger.exception("baseline eval failed for %s", target.name)
        return _failure_outcome(target, iteration_id, ts, f"baseline eval failed: {e}")

    from evals.scoring import aggregate  # local import avoids circular noise

    baseline_agg = aggregate(baseline_scores)

    # Propose
    try:
        ctx = ProposalContext.from_scores(current_text=current_text, baseline=baseline_agg)
        candidate_text = propose_edit(ctx, llm)
    except InvalidProposal as e:
        return IterationOutcome(
            substation_id=_substation_id_of(target),
            iteration_id=iteration_id,
            decision="rejected_proposal",
            target_axis=None,
            commit_kind=None,
            baseline=baseline_agg,
            candidate=None,
            delta=None,
            error=str(e),
            timestamp=ts,
        )

    # Apply + Pareto gate (uses a scratch file under a temp dir)
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / target.name
        scratch.write_text(candidate_text)
        result = apply_and_score(
            candidate_path=scratch,
            baseline_path=target,
            qa_pairs=cfg.qa_pairs,
            evaluate=evaluate,
        )

    if result.decision != ApplyDecision.ACCEPT:
        return IterationOutcome(
            substation_id=_substation_id_of(target),
            iteration_id=iteration_id,
            decision=result.decision.value,
            target_axis=ctx.target_axis,
            commit_kind=None,
            baseline=result.baseline,
            candidate=result.candidate,
            delta=result.delta.as_dict() if result.delta else None,
            error=result.error,
            timestamp=ts,
        )

    # Accepted: classify, write, commit, maybe push / open PR
    from_sha = git.head_sha(cfg.repo_root)
    kind = classify_diff(current_text, candidate_text)

    _write_replay_json(
        cfg.runs_dir,
        iteration_id,
        target,
        current_text,
        candidate_text,
        result,
        ctx,
        ts,
    )

    if kind == CommitKind.MAJOR_PR:
        # Write candidate to a side branch, commit, open PR against default.
        branch = f"autoresearch/{iteration_id}"
        git.checkout_branch(cfg.repo_root, branch)
        target.write_text(candidate_text)
        commit_sha = git.commit_file(
            cfg.repo_root,
            target,
            f"autoresearch(major): {target.name} — iteration {iteration_id}",
        )
        pr_url = None
        if cfg.auto_push:
            git.push(cfg.repo_root, branch)
            pr_body = render_pr_body(
                DiffContext(
                    substation_id=_substation_id_of(target),
                    from_sha=from_sha,
                    to_sha=commit_sha,
                    iteration_label=iteration_id,
                    target_axis=ctx.target_axis,
                ),
                current_text,
                candidate_text,
                result,
            )
            pr_url = gh.create_pr(
                cfg.repo_root,
                title=f"autoresearch: {target.name} iteration {iteration_id}",
                body=pr_body,
                base=cfg.default_branch,
                head=branch,
            )
        # Return to default branch so subsequent iterations don't land on the PR branch.
        git.checkout_branch(cfg.repo_root, cfg.default_branch)
        return IterationOutcome(
            substation_id=_substation_id_of(target),
            iteration_id=iteration_id,
            decision=result.decision.value,
            target_axis=ctx.target_axis,
            commit_kind=kind.value,
            baseline=result.baseline,
            candidate=result.candidate,
            delta=result.delta.as_dict() if result.delta else None,
            error=None,
            timestamp=ts,
            commit_sha=commit_sha,
            pr_url=pr_url,
        )

    # Minor: commit to a dated autoresearch branch, push if enabled.
    branch = f"autoresearch/{now().strftime('%Y-%m-%d')}"
    git.checkout_branch(cfg.repo_root, branch)
    target.write_text(candidate_text)
    commit_sha = git.commit_file(
        cfg.repo_root,
        target,
        f"autoresearch(minor): {target.name} — iteration {iteration_id}",
    )
    if cfg.auto_push:
        git.push(cfg.repo_root, branch)
    git.checkout_branch(cfg.repo_root, cfg.default_branch)
    return IterationOutcome(
        substation_id=_substation_id_of(target),
        iteration_id=iteration_id,
        decision=result.decision.value,
        target_axis=ctx.target_axis,
        commit_kind=kind.value,
        baseline=result.baseline,
        candidate=result.candidate,
        delta=result.delta.as_dict() if result.delta else None,
        error=None,
        timestamp=ts,
        commit_sha=commit_sha,
    )


def _substation_id_of(playbook_path: Path) -> str:
    """Best-effort: read frontmatter and return substation_id."""
    from hermes.schema import load_frontmatter

    try:
        fm = load_frontmatter(playbook_path.read_text())
        return str(fm.get("substation_id", playbook_path.stem))
    except Exception:  # noqa: BLE001
        return playbook_path.stem


def _failure_outcome(target: Path, iteration_id: str, ts: str, err: str) -> IterationOutcome:
    return IterationOutcome(
        substation_id=_substation_id_of(target),
        iteration_id=iteration_id,
        decision=ApplyDecision.REJECT_CRASH.value,
        target_axis=None,
        commit_kind=None,
        baseline=None,
        candidate=None,
        delta=None,
        error=err,
        timestamp=ts,
    )


def _write_replay_json(
    runs_dir: Path,
    iteration_id: str,
    target: Path,
    old_text: str,
    new_text: str,
    result: ApplyResult,
    ctx: ProposalContext,
    ts: str,
) -> None:
    out_dir = runs_dir / iteration_id[:8]  # YYYYMMDD
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "iteration_id": iteration_id,
        "timestamp": ts,
        "substation_id": _substation_id_of(target),
        "target_axis": ctx.target_axis,
        "playbook_filename": target.name,
        "baseline_axes": result.baseline.as_dict() if result.baseline else None,
        "candidate_axes": result.candidate.as_dict() if result.candidate else None,
        "delta": result.delta.as_dict() if result.delta else None,
        "old_text": old_text,
        "new_text": new_text,
    }
    (out_dir / f"{iteration_id}.json").write_text(json.dumps(payload, indent=2))


@dataclass
class LedgerEntry:
    iteration_id: str
    substation_id: str
    timestamp: str
    decision: str
    commit_kind: str | None
    target_axis: str | None
    delta: dict[str, float] | None
    commit_sha: str | None
    pr_url: str | None
    error: str | None


def _append_to_ledger(ledger_path: Path, outcome: IterationOutcome) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict] = []
    if ledger_path.exists():
        try:
            existing = json.loads(ledger_path.read_text())
            if not isinstance(existing, list):
                existing = []
        except (OSError, json.JSONDecodeError):
            existing = []
    entry = {
        "iteration_id": outcome.iteration_id,
        "substation_id": outcome.substation_id,
        "timestamp": outcome.timestamp,
        "decision": outcome.decision,
        "commit_kind": outcome.commit_kind,
        "target_axis": outcome.target_axis,
        "delta": outcome.delta,
        "commit_sha": outcome.commit_sha,
        "pr_url": outcome.pr_url,
        "error": outcome.error,
    }
    existing.insert(0, entry)  # most-recent-first
    existing = existing[:LEDGER_MAX_ITERATIONS]
    ledger_path.write_text(json.dumps(existing, indent=2))
