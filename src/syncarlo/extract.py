"""English role labeling: quotes, numbers, prepositional objects, binders."""

from __future__ import annotations

import re
from dataclasses import dataclass

from syncarlo.english import FUNCTION_WORDS, PREP_ROLE

QUOTED = re.compile(r"""(['"])(?P<val>.*?)\1""")
NUMBER = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)(?![\w.])")
IDENT = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\b")
PATHISH = re.compile(r"\b[\w./\\-]+\.(?:csv|json|txt|py|md|yml|yaml|xml|html)\b", re.I)
PREP = re.compile(
    r"\b(from|to|into|onto|as|with|using|on|by|in|of|for|over)\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.I,
)


@dataclass
class Entity:
    label: str
    value: str
    start: int
    end: int
    source: str = "regex"
    role: str | None = None


def extract_entities(text: str) -> list[Entity]:
    found: list[Entity] = []
    occupied: list[tuple[int, int]] = []

    def take(span: tuple[int, int]) -> bool:
        s, e = span
        for a, b in occupied:
            if not (e <= a or s >= b):
                return False
        occupied.append((s, e))
        return True

    for m in QUOTED.finditer(text):
        if take(m.span()):
            found.append(Entity("quoted", m.group("val"), m.start(), m.end()))

    for m in PATHISH.finditer(text):
        if take(m.span()):
            found.append(Entity("path", m.group(0), m.start(), m.end(), role="source"))

    for m in NUMBER.finditer(text):
        if take(m.span()):
            found.append(Entity("number", m.group(1), m.start(), m.end()))

    for m in PREP.finditer(text):
        prep = m.group(1).lower()
        val = m.group(2)
        lab = "name" if prep == "as" else "ident"
        span = (m.start(2), m.end(2))
        if take(span):
            found.append(Entity(lab, val, span[0], span[1], role=PREP_ROLE.get(prep)))

    first_verb = True
    for m in IDENT.finditer(text):
        tok = m.group(1)
        if tok.lower() in FUNCTION_WORDS:
            continue
        if take(m.span()):
            role = "verb" if first_verb else "theme"
            first_verb = False
            found.append(Entity("ident", tok, m.start(), m.end(), role=role))

    found.sort(key=lambda e: e.start)
    return found


def python_literal(ent: Entity) -> str:
    if ent.label in {"quoted", "path"}:
        return repr(ent.value)
    if ent.label == "number":
        return ent.value
    return ent.value
