"""Load the Hermes identity and playbook templates from HERMES.md.

HERMES.md is the single source of truth for:
  - the system prompt (stitched into every agent turn)
  - per-event-kind action prompts (rendered with trigger context)

Keep behavior-changing prose in HERMES.md. This module is only a parser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

IDENTITY_MD = Path(__file__).parent / "HERMES.md"


@dataclass(frozen=True)
class Playbook:
    key: str
    template: str

    def render(self, **ctx: object) -> str:
        """Format the template with event-context keyword args.

        Missing keys fall back to '<unset>' so a partial trigger still renders.
        """
        class _DefaultDict(dict):
            def __missing__(self, key):  # type: ignore[override]
                return "<unset>"

        return self.template.format_map(_DefaultDict(**{k: v for k, v in ctx.items()}))


# --- Parsing ----------------------------------------------------------------

_H2 = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_H3 = re.compile(r"^###\s+(.+)$", re.MULTILINE)
_CODE_BLOCK = re.compile(r"^```\s*\n(.+?)\n```", re.MULTILINE | re.DOTALL)


@lru_cache(maxsize=1)
def _default_md_text() -> str:
    return IDENTITY_MD.read_text()


def _md_text(path: Path | None = None) -> str:
    if path is None:
        return _default_md_text()
    return Path(path).read_text()


def _section(heading: str, level: int = 2, path: Path | None = None) -> str:
    """Return the body under '## {heading}' or '### {heading}' up to the next
    heading at the same or shallower level."""
    text = _md_text(path)
    pattern = _H2 if level == 2 else _H3
    for m in pattern.finditer(text):
        if m.group(1).strip() == heading:
            start = m.end()
            terminators = re.compile(rf"^#{{1,{level}}}\s+.+$", re.MULTILINE)
            tail = text[start:]
            term = terminators.search(tail)
            end = start + term.start() if term else len(text)
            return text[start:end].strip()
    raise KeyError(f"section not found at level {level}: {heading}")


@lru_cache(maxsize=1)
def _default_identity() -> str:
    return _section("Identity", level=2)


def identity(path: Path | None = None) -> str:
    """The system-prompt body, verbatim from `## Identity`.

    When path is None the default HERMES.md next to this module is used and the
    result is cached. When path is given the cache is bypassed (autoresearch's
    scratch-playbook evaluation needs a fresh read each call).
    """
    if path is None:
        return _default_identity()
    return _section("Identity", level=2, path=path)


def _build_playbooks_map(path: Path | None = None) -> dict[str, Playbook]:
    section = _section("Playbooks", level=2, path=path)
    out: dict[str, Playbook] = {}
    h3s = list(_H3.finditer(section))
    for i, m in enumerate(h3s):
        key = m.group(1).strip()
        body_start = m.end()
        body_end = h3s[i + 1].start() if i + 1 < len(h3s) else len(section)
        body = section[body_start:body_end]
        code = _CODE_BLOCK.search(body)
        if not code:
            continue
        out[key] = Playbook(key=key, template=code.group(1).strip())
    return out


@lru_cache(maxsize=1)
def _default_playbooks_map() -> dict[str, Playbook]:
    return _build_playbooks_map(path=None)


def playbook(key: str, path: Path | None = None) -> Playbook:
    pbs = _default_playbooks_map() if path is None else _build_playbooks_map(path=path)
    try:
        return pbs[key]
    except KeyError as e:
        keys = ", ".join(sorted(pbs))
        raise KeyError(f"unknown playbook '{key}'. known: {keys}") from e


def playbook_keys(path: Path | None = None) -> list[str]:
    pbs = _default_playbooks_map() if path is None else _build_playbooks_map(path=path)
    return sorted(pbs)


# --- Agent-loop adapters ----------------------------------------------------


def system_message(hermes_md_path: Path | None = None) -> dict[str, str]:
    """System message shape expected by the agent loop.

    Pass `hermes_md_path` to evaluate a scratch playbook without touching the
    default HERMES.md. Autoresearch uses this to score a proposed edit before
    deciding to commit.
    """
    return {"role": "system", "content": identity(path=hermes_md_path)}


def action_message(
    playbook_key: str, hermes_md_path: Path | None = None, **context: object
) -> dict[str, str]:
    """Render a playbook into the first user-turn message for the agent loop."""
    return {
        "role": "user",
        "content": playbook(playbook_key, path=hermes_md_path).render(**context),
    }


# Back-compat shim for any caller still importing SYSTEM_PROMPT by name.
# Computed lazily via a module __getattr__ so the file read doesn't happen at
# import time if the caller never touches it.
def __getattr__(name: str) -> str:
    if name == "SYSTEM_PROMPT":
        return identity()
    raise AttributeError(name)
