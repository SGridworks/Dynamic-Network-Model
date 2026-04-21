"""Every shipped HERMES-*.md must declare a unique (topology, load_mix, climate, criticality) 4-tuple.

The atlas is an archetypal taxonomy. Two playbooks with the same 4-tuple are
either duplicates that should be merged, or they mean the taxonomy is too
coarse to distinguish them. Either way: CI breaks.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from hermes.schema import validate_playbook_file

AGENT_DIR = Path(__file__).resolve().parent.parent / "hermes" / "agent"


def _tuple_of(frontmatter: dict) -> tuple[str, str, str, str]:
    a = frontmatter["archetype"]
    return (a["topology"], a["load_mix"], a["climate"], a["criticality"])


def test_archetype_tuples_are_unique() -> None:
    by_tuple: dict[tuple[str, str, str, str], list[str]] = defaultdict(list)
    for path in sorted(AGENT_DIR.glob("HERMES*.md")):
        parsed = validate_playbook_file(path)
        by_tuple[_tuple_of(parsed.frontmatter)].append(path.name)

    duplicates = {t: files for t, files in by_tuple.items() if len(files) > 1}
    assert not duplicates, (
        "archetype 4-tuple collisions:\n"
        + "\n".join(f"  {t}: {', '.join(files)}" for t, files in duplicates.items())
    )
