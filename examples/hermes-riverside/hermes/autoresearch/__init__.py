"""Autoresearch loop: propose, apply, commit playbook edits.

The loop lives in `loop.py` and is the entry point a nightly cron runs. The
supporting modules are:

  - propose.py  : ask an LLM to draft a targeted HERMES.md edit
  - apply.py    : score the candidate against a baseline via the eval harness
  - commit.py   : decide to commit-or-PR, update the kill-switch + ledger
  - diff.py     : render a PR-body markdown summary of the edit

Every committed iteration is auditable: the PR-style markdown, the eval
delta JSON, and the full LLM conversation that produced it all live under
git history or under `runs/`.
"""

from hermes.autoresearch.diff import render_pr_body
from hermes.autoresearch.propose import (
    InvalidProposal,
    ProposalContext,
    propose_edit,
)
from hermes.autoresearch.apply import (
    ApplyDecision,
    ApplyResult,
    apply_and_score,
)
from hermes.autoresearch.commit import (
    CommitKind,
    KillSwitchState,
    classify_diff,
    load_killswitch,
    save_killswitch,
)

__all__ = [
    "ApplyDecision",
    "ApplyResult",
    "CommitKind",
    "InvalidProposal",
    "KillSwitchState",
    "ProposalContext",
    "apply_and_score",
    "classify_diff",
    "load_killswitch",
    "propose_edit",
    "render_pr_body",
    "save_killswitch",
]
