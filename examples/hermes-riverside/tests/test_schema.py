"""Validate every shipped HERMES-*.md against the schema + section contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes.schema import SchemaViolation, load_frontmatter, validate_playbook_file

AGENT_DIR = Path(__file__).resolve().parent.parent / "hermes" / "agent"


def _shipped_playbooks() -> list[Path]:
    return sorted(AGENT_DIR.glob("HERMES*.md"))


def test_discovers_shipped_playbooks() -> None:
    paths = _shipped_playbooks()
    assert paths, f"no HERMES*.md files found under {AGENT_DIR}"


@pytest.mark.parametrize("path", _shipped_playbooks(), ids=lambda p: p.name)
def test_shipped_playbook_validates(path: Path) -> None:
    parsed = validate_playbook_file(path)
    assert parsed.frontmatter["schema_version"] == "0.1"
    assert parsed.playbook_keys, f"{path.name}: no playbook keys parsed"


def test_missing_frontmatter_raises() -> None:
    with pytest.raises(SchemaViolation, match="missing YAML frontmatter"):
        load_frontmatter("# Just markdown, no frontmatter\n\n## Identity\n\nhi\n")


def test_invalid_topology_raises() -> None:
    bad = """---
schema_version: "0.1"
substation_id: SUB-999
substation_name: Bad Example
archetype:
  topology: made_up_topology
  load_mix: mixed
  climate: temperate
  criticality: standard
version: 0.1.0
---
"""
    with pytest.raises(SchemaViolation, match="archetype/topology"):
        load_frontmatter(bad)


def test_bad_substation_id_pattern_raises() -> None:
    bad = """---
schema_version: "0.1"
substation_id: not-a-sub-id
substation_name: Bad
archetype:
  topology: urban_radial
  load_mix: mixed
  climate: temperate
  criticality: standard
version: 0.1.0
---
"""
    with pytest.raises(SchemaViolation, match="substation_id"):
        load_frontmatter(bad)


def test_missing_identity_section_raises(tmp_path: Path) -> None:
    p = tmp_path / "HERMES-bad.md"
    p.write_text(
        """---
schema_version: "0.1"
substation_id: SUB-999
substation_name: NoIdentity
archetype:
  topology: urban_radial
  load_mix: mixed
  climate: temperate
  criticality: standard
version: 0.1.0
---

# HERMES.md

## Playbooks

### event_one

```
trigger
```

## Memory

stuff
"""
    )
    with pytest.raises(SchemaViolation, match="missing required.*Identity"):
        validate_playbook_file(p)


def test_empty_playbooks_section_raises(tmp_path: Path) -> None:
    p = tmp_path / "HERMES-empty.md"
    p.write_text(
        """---
schema_version: "0.1"
substation_id: SUB-999
substation_name: EmptyPlaybooks
archetype:
  topology: urban_radial
  load_mix: mixed
  climate: temperate
  criticality: standard
version: 0.1.0
---

# HERMES.md

## Identity

identity text

## Playbooks

## Memory

mem text
"""
    )
    with pytest.raises(SchemaViolation, match="Playbooks"):
        validate_playbook_file(p)
