"""Parse and validate HERMES.md playbook files.

A valid HERMES.md has:
  1. YAML frontmatter between `---` fences conforming to HERMES.md.schema.json
  2. An `## Identity` section (non-empty)
  3. An `## Playbooks` section with at least one `### <event_kind>` subsection
  4. A `## Memory` section (non-empty)

Frontmatter is validated with jsonschema. Sections are checked with regex.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

HERMES_MD_SCHEMA_PATH = Path(__file__).parent / "HERMES.md.schema.json"

REQUIRED_H2_SECTIONS = ("Identity", "Playbooks", "Memory")

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_H2 = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_H3 = re.compile(r"^###\s+(.+)$", re.MULTILINE)


class SchemaViolation(ValueError):
    """Raised when a HERMES.md file fails schema or structure checks."""


@dataclass(frozen=True)
class ParsedPlaybook:
    frontmatter: dict
    body: str
    sections: dict[str, str]
    playbook_keys: tuple[str, ...]


@lru_cache(maxsize=1)
def _schema() -> dict:
    return json.loads(HERMES_MD_SCHEMA_PATH.read_text())


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(_schema())


def load_frontmatter(text: str) -> dict:
    m = _FRONTMATTER.match(text)
    if not m:
        raise SchemaViolation(
            "HERMES.md is missing YAML frontmatter (expected leading `---` block)"
        )
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        raise SchemaViolation(f"frontmatter YAML parse error: {e}") from e
    if not isinstance(data, dict):
        raise SchemaViolation("frontmatter must be a YAML mapping")
    errors = sorted(_validator().iter_errors(data), key=lambda e: e.absolute_path)
    if errors:
        msg = "; ".join(
            f"{'/'.join(str(p) for p in e.absolute_path) or '(root)'}: {e.message}"
            for e in errors
        )
        raise SchemaViolation(f"frontmatter validation failed: {msg}")
    return data


def _strip_frontmatter(text: str) -> str:
    m = _FRONTMATTER.match(text)
    return text[m.end():] if m else text


def _extract_sections(body: str) -> dict[str, str]:
    matches = list(_H2.finditer(body))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[name] = body[start:end].strip()
    return sections


def _extract_playbook_keys(playbooks_section: str) -> tuple[str, ...]:
    return tuple(m.group(1).strip() for m in _H3.finditer(playbooks_section))


def validate_playbook_file(path: Path) -> ParsedPlaybook:
    text = path.read_text()
    frontmatter = load_frontmatter(text)
    body = _strip_frontmatter(text)
    sections = _extract_sections(body)

    missing = [s for s in REQUIRED_H2_SECTIONS if s not in sections]
    if missing:
        raise SchemaViolation(
            f"{path.name}: missing required `##` sections: {', '.join(missing)}"
        )

    empty = [s for s in REQUIRED_H2_SECTIONS if not sections[s].strip()]
    if empty:
        raise SchemaViolation(
            f"{path.name}: required sections are empty: {', '.join(empty)}"
        )

    playbook_keys = _extract_playbook_keys(sections["Playbooks"])
    if not playbook_keys:
        raise SchemaViolation(
            f"{path.name}: `## Playbooks` has no `### <event_kind>` subsections"
        )

    return ParsedPlaybook(
        frontmatter=frontmatter,
        body=body,
        sections=sections,
        playbook_keys=playbook_keys,
    )
