"""Parse headings + nested numbered lists into a Spec IR."""

from __future__ import annotations

import re
from pathlib import Path

from syncarlo.ir import Section, Spec, Step

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# 1.  1.2.  2)  (3)  1.2.3)
NUMBERED_RE = re.compile(
    r"^(\s*)(?:\(?(\d+(?:\.\d+)*)\)?[.)]\s+)(.+?)\s*$"
)


def parse_file(path: str | Path) -> Spec:
    return parse_markdown(Path(path).read_text(encoding="utf-8"))


def parse_markdown(text: str) -> Spec:
    sections: list[Section] = []
    current: Section | None = None
    # stack of (indent, step) for nesting
    stack: list[tuple[int, Step]] = []
    doc_title: str | None = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("```"):
            continue

        h = HEADING_RE.match(raw_line)
        if h:
            level = len(h.group(1))
            title = h.group(2).strip()
            if level == 1 and doc_title is None:
                doc_title = title
            current = Section(title=title, level=level, raw_heading=raw_line)
            sections.append(current)
            stack = []
            continue

        n = NUMBERED_RE.match(raw_line)
        if n:
            indent = len(n.group(1).replace("\t", "    "))
            number = n.group(2)
            body = n.group(3).strip()
            step = Step(number=number, text=body, depth=0)
            if current is None:
                current = Section(title="main", level=1)
                sections.append(current)
            while stack and stack[-1][0] >= indent:
                stack.pop()
            if stack:
                parent = stack[-1][1]
                step.depth = parent.depth + 1
                parent.children.append(step)
            else:
                step.depth = 0
                current.steps.append(step)
            stack.append((indent, step))
            continue

        # Continuation line: append to last step
        if current and (current.steps or stack) and raw_line.startswith((" ", "\t")):
            target = stack[-1][1] if stack else _last_leaf(current.steps)
            if target:
                target.text = f"{target.text} {raw_line.strip()}"

    return Spec(title=doc_title, sections=sections)


def _last_leaf(steps: list[Step]) -> Step | None:
    if not steps:
        return None
    s = steps[-1]
    while s.children:
        s = s.children[-1]
    return s
