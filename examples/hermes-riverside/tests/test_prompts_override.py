"""prompts.system_message(hermes_md_path=...) reads alternate playbooks."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes.agent.prompts import (
    action_message,
    identity,
    playbook,
    playbook_keys,
    system_message,
)

SCRATCH_PLAYBOOK = """---
schema_version: "0.1"
substation_id: SUB-999
substation_name: Scratch
archetype:
  topology: rural_loop
  load_mix: mixed
  climate: temperate
  criticality: standard
version: 0.1.0
---

# HERMES-scratch.md

## Identity

You are a scratch Hermes used by the autoresearch test harness.

## Playbooks

### scratch_event

Scratch description.

```
Trigger: {source} reports scratch value {value} on {feeder_id}.

Respond with a scratch advisory.
```

## Memory

Scratch memory.
"""


@pytest.fixture
def scratch_file(tmp_path: Path) -> Path:
    p = tmp_path / "HERMES-scratch.md"
    p.write_text(SCRATCH_PLAYBOOK)
    return p


def test_default_system_message_uses_shipped_identity() -> None:
    msg = system_message()
    assert msg["role"] == "system"
    assert "Hermes" in msg["content"]
    assert "SUB-001" in msg["content"]


def test_override_system_message_uses_scratch_identity(scratch_file: Path) -> None:
    msg = system_message(hermes_md_path=scratch_file)
    assert "scratch Hermes" in msg["content"]
    assert "SUB-001" not in msg["content"]


def test_override_does_not_poison_default_cache(scratch_file: Path) -> None:
    _ = system_message(hermes_md_path=scratch_file)
    default_msg = system_message()
    assert "scratch Hermes" not in default_msg["content"]
    assert "SUB-001" in default_msg["content"]


def test_override_identity_function_matches(scratch_file: Path) -> None:
    assert "scratch Hermes" in identity(path=scratch_file)


def test_override_playbook_keys(scratch_file: Path) -> None:
    assert playbook_keys(path=scratch_file) == ["scratch_event"]


def test_override_playbook_renders(scratch_file: Path) -> None:
    pb = playbook("scratch_event", path=scratch_file)
    rendered = pb.render(source="historian", value=0.97, feeder_id="FDR-0099")
    assert "historian" in rendered
    assert "0.97" in rendered
    assert "FDR-0099" in rendered


def test_override_action_message_uses_scratch_playbook(scratch_file: Path) -> None:
    msg = action_message(
        "scratch_event",
        hermes_md_path=scratch_file,
        source="historian",
        value=0.97,
        feeder_id="FDR-0099",
    )
    assert msg["role"] == "user"
    assert "scratch advisory" in msg["content"]
