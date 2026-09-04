"""Intermediate representation for a structured markdown spec."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    """One numbered sentence, optionally with nested child steps."""

    number: str
    text: str
    children: list[Step] = field(default_factory=list)
    depth: int = 0


@dataclass
class Section:
    """A heading and its numbered procedure."""

    title: str
    level: int
    steps: list[Step] = field(default_factory=list)
    raw_heading: str = ""


@dataclass
class Spec:
    title: str | None
    sections: list[Section]
