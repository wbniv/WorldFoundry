"""Actor references in exported level scripts, resolved at export time.

Level scripts address other actors by index (`value mailbox ACTOR write-actor-mailbox`,
`INDEXOF_CAMSHOT`). The engine numbers actors 1-based in `.lev` order, which only the
exporter knows for certain, so a generator writes `{{actor:NAME}}` (see `actor_ref`) and
the exporter replaces it with NAME's index in the order it writes. Inserting or reordering
objects then cannot leave a script pointing at the wrong actor.

No `bpy` here, so the rules are testable outside Blender (tests/test_wf_blender_actor_refs.py).
"""
from __future__ import annotations

import re
from typing import Iterable, Mapping

ACTOR_REF = re.compile(r"\{\{actor:([^{}]+)\}\}")


def actor_ref(name: str) -> str:
    """The token a generator writes where a script needs NAME's actor index."""
    if not name or "{" in name or "}" in name:
        raise ValueError(f"not a usable object name for an actor reference: {name!r}")
    return "{{actor:%s}}" % name


def index_map(names: Iterable[str]) -> dict[str, int]:
    """{name: 1-based actor index} for objects in `.lev` write order (levcomp's numbering)."""
    out: dict[str, int] = {}
    for i, name in enumerate(names, start=1):
        if name in out:
            raise ValueError(f"duplicate object name {name!r} (indices {out[name]} and {i})")
        out[name] = i
    return out


def resolve_actor_refs(text: str, indices: Mapping[str, int], where: str = "") -> str:
    """Replace every `{{actor:NAME}}` in TEXT with NAME's index; unknown names raise ValueError."""
    missing = sorted({m.group(1) for m in ACTOR_REF.finditer(text) if m.group(1) not in indices})
    if missing:
        raise ValueError(f"{where}: actor reference to {', '.join(map(repr, missing))}, "
                         "which is not an exported object")
    return ACTOR_REF.sub(lambda m: str(indices[m.group(1)]), text)


def dangling_reference(value: str, names: Iterable[str] | Mapping[str, int]) -> bool:
    """True when an object-reference field names an object that is not exported.

    levcomp writes 0 (or -1 inside a common block) for a name it cannot resolve, exactly as
    for an empty field, so a dangling name silently becomes "no object".
    """
    return bool(value) and value not in names
