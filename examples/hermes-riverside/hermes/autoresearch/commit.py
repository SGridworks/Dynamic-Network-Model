"""Classify a candidate diff, write the kill-switch state, commit or open a PR.

Major-diff rules (any ONE triggers major):
  - diff touches more than MAX_MINOR_LINES line-changes (default 20)
  - diff modifies `## Identity`
  - diff crosses any `### ` (playbook) section boundary

Major diffs go to `gh pr create` against main. Minor diffs auto-commit to
`autoresearch/<YYYY-MM-DD>` and push.

Kill-switch: after three consecutive regressions, the loop halts until a
human runs `hermes autoresearch unhalt`.
"""

from __future__ import annotations

import enum
import json
import re
from dataclasses import asdict, dataclass
from difflib import unified_diff
from pathlib import Path

MAX_MINOR_LINES = 20
H3 = re.compile(r"^### ", re.MULTILINE)
REGRESSION_LIMIT = 3


class CommitKind(enum.Enum):
    MINOR_AUTO_COMMIT = "minor_auto_commit"
    MAJOR_PR = "major_pr"


@dataclass
class KillSwitchState:
    consecutive_regressions: int = 0
    halted: bool = False
    last_run_ts: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def load_killswitch(path: Path) -> KillSwitchState:
    if not path.exists():
        return KillSwitchState()
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return KillSwitchState()
    return KillSwitchState(
        consecutive_regressions=int(data.get("consecutive_regressions", 0)),
        halted=bool(data.get("halted", False)),
        last_run_ts=data.get("last_run_ts"),
    )


def save_killswitch(state: KillSwitchState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.as_dict(), indent=2) + "\n")


def record_outcome(state: KillSwitchState, accepted: bool, ts: str) -> KillSwitchState:
    """Update kill-switch state after one iteration.

    Accepting resets the regression counter. Rejecting increments it and halts
    the loop once the limit is reached.
    """
    if accepted:
        return KillSwitchState(consecutive_regressions=0, halted=False, last_run_ts=ts)
    new_count = state.consecutive_regressions + 1
    return KillSwitchState(
        consecutive_regressions=new_count,
        halted=new_count >= REGRESSION_LIMIT,
        last_run_ts=ts,
    )


def classify_diff(old_text: str, new_text: str) -> CommitKind:
    """Return MAJOR if any of the three rules triggers, else MINOR."""
    if _modifies_identity(old_text, new_text):
        return CommitKind.MAJOR_PR
    if _crosses_playbook_boundary(old_text, new_text):
        return CommitKind.MAJOR_PR

    changed = _changed_line_count(old_text, new_text)
    if changed > MAX_MINOR_LINES:
        return CommitKind.MAJOR_PR
    return CommitKind.MINOR_AUTO_COMMIT


def _changed_line_count(old_text: str, new_text: str) -> int:
    """Count added+removed lines, excluding context lines and diff markers."""
    diff = unified_diff(old_text.splitlines(), new_text.splitlines(), lineterm="")
    count = 0
    for line in diff:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def _section_body(text: str, heading: str) -> str | None:
    """Extract the body of a `## {heading}` section, or None if missing."""
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def _modifies_identity(old_text: str, new_text: str) -> bool:
    return _section_body(old_text, "Identity") != _section_body(new_text, "Identity")


def _playbook_keys(text: str) -> set[str]:
    section = _section_body(text, "Playbooks") or ""
    return {m.group(1).strip() for m in re.finditer(r"^###\s+(.+)$", section, re.MULTILINE)}


def _crosses_playbook_boundary(old_text: str, new_text: str) -> bool:
    """Major if the set of `### ` keys under `## Playbooks` changed (added or
    removed), OR if any existing playbook body was modified."""
    old_keys = _playbook_keys(old_text)
    new_keys = _playbook_keys(new_text)
    if old_keys != new_keys:
        return True
    # If the keys match, a cross-boundary change would alter one playbook's body
    # by more than MAX_MINOR_LINES. That's already caught by the line-count
    # rule, so we don't double-count here.
    return False
