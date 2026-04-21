"""Tests for hermes/autoresearch/commit.py.

Covers diff classification (MAJOR vs MINOR) and the kill-switch state machine.
The actual `git push` / `gh pr create` subprocess calls are intentionally NOT
exercised here; those are wired in loop.py and covered by the loop test.
"""

from __future__ import annotations

from pathlib import Path

from hermes.autoresearch.commit import (
    CommitKind,
    KillSwitchState,
    REGRESSION_LIMIT,
    classify_diff,
    load_killswitch,
    record_outcome,
    save_killswitch,
)


FULL_PLAYBOOK = """---
schema_version: "0.1"
substation_id: SUB-001
substation_name: Test
archetype:
  topology: urban_radial
  load_mix: mixed
  climate: temperate
  criticality: standard
version: 0.1.0
---

# HERMES.md

## Identity

You are Hermes. Short identity for testing.

## Playbooks

### event_one

Description.

```
Trigger: {source} reports {value}.

Respond.
```

### event_two

Another.

```
Trigger: {source} reports {value}.

Respond.
```

## Memory

Memory posture.
"""


def _with(old: str, find: str, repl: str) -> str:
    assert find in old, f"fixture drift: {find!r} not in playbook"
    return old.replace(find, repl, 1)


# --- classify_diff --------------------------------------------------------


def test_identical_text_is_minor() -> None:
    assert classify_diff(FULL_PLAYBOOK, FULL_PLAYBOOK) == CommitKind.MINOR_AUTO_COMMIT


def test_single_word_change_is_minor() -> None:
    new = _with(FULL_PLAYBOOK, "Description.", "Short description.")
    assert classify_diff(FULL_PLAYBOOK, new) == CommitKind.MINOR_AUTO_COMMIT


def test_identity_change_is_always_major() -> None:
    new = _with(
        FULL_PLAYBOOK,
        "You are Hermes. Short identity for testing.",
        "You are Hermes. Slightly different identity.",
    )
    assert classify_diff(FULL_PLAYBOOK, new) == CommitKind.MAJOR_PR


def test_added_playbook_is_major() -> None:
    new = FULL_PLAYBOOK.replace(
        "## Memory",
        "### event_three\n\nNew.\n\n```\nT\n```\n\n## Memory",
    )
    assert classify_diff(FULL_PLAYBOOK, new) == CommitKind.MAJOR_PR


def test_removed_playbook_is_major() -> None:
    new = FULL_PLAYBOOK.replace(
        "### event_two\n\nAnother.\n\n```\nTrigger: {source} reports {value}.\n\nRespond.\n```\n\n",
        "",
    )
    assert classify_diff(FULL_PLAYBOOK, new) == CommitKind.MAJOR_PR


def test_many_line_change_is_major() -> None:
    """Add a 40-line comment block to the Memory section."""
    bulk = "\n".join(f"- bullet point {i}" for i in range(40))
    new = _with(FULL_PLAYBOOK, "Memory posture.", f"Memory posture.\n\n{bulk}")
    assert classify_diff(FULL_PLAYBOOK, new) == CommitKind.MAJOR_PR


# --- kill-switch state ----------------------------------------------------


def test_empty_state_on_missing_file(tmp_path: Path) -> None:
    state = load_killswitch(tmp_path / "ks.json")
    assert state == KillSwitchState()
    assert state.halted is False


def test_save_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "ks.json"
    save_killswitch(
        KillSwitchState(consecutive_regressions=2, halted=False, last_run_ts="2026-04-21T00:00:00Z"),
        path,
    )
    loaded = load_killswitch(path)
    assert loaded.consecutive_regressions == 2
    assert loaded.halted is False
    assert loaded.last_run_ts == "2026-04-21T00:00:00Z"


def test_acceptance_resets_regression_counter() -> None:
    s = KillSwitchState(consecutive_regressions=2, halted=False, last_run_ts=None)
    new = record_outcome(s, accepted=True, ts="2026-04-21T00:00:00Z")
    assert new.consecutive_regressions == 0
    assert new.halted is False
    assert new.last_run_ts == "2026-04-21T00:00:00Z"


def test_rejection_increments_counter() -> None:
    s = KillSwitchState()
    new = record_outcome(s, accepted=False, ts="t")
    assert new.consecutive_regressions == 1
    assert new.halted is False


def test_hits_limit_halts_loop() -> None:
    s = KillSwitchState(consecutive_regressions=REGRESSION_LIMIT - 1, halted=False)
    new = record_outcome(s, accepted=False, ts="t")
    assert new.consecutive_regressions == REGRESSION_LIMIT
    assert new.halted is True


def test_halted_state_only_clears_on_accept() -> None:
    """Once halted, an acceptance clears it. This encodes the recovery flow:
    after human inspects and un-halts via a successful eval run, the state
    resets."""
    s = KillSwitchState(consecutive_regressions=REGRESSION_LIMIT, halted=True)
    new = record_outcome(s, accepted=True, ts="t")
    assert new.halted is False
    assert new.consecutive_regressions == 0


def test_corrupted_state_file_is_treated_as_empty(tmp_path: Path) -> None:
    path = tmp_path / "ks.json"
    path.write_text("{not json")
    assert load_killswitch(path) == KillSwitchState()
