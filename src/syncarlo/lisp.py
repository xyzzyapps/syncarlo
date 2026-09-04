"""Tiny Lisp IR: nested lists. Atoms are str | int | float | bool | None."""

from __future__ import annotations

from typing import Any

Form = Any


class Sym(str):
    """Lisp symbol (Python identifier / qname), not a string literal."""

    def __repr__(self) -> str:
        return str(self)


_OPS = {
    "def", "let", "call", "method", "if", "for", "return", "print",
    "note", "comment", "quote", "pass", "do", "==", "none", "true", "false",
}


def dumps(form: Form) -> str:
    if form is None:
        return "none"
    if form is True:
        return "true"
    if form is False:
        return "false"
    if isinstance(form, Sym):
        return str(form)
    if isinstance(form, str):
        if form in _OPS or (isinstance(form, str) and _bare_symbol(form) and form in _OPS):
            return form
        return '"' + form.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(form, (int, float)):
        return str(form)
    if isinstance(form, dict):
        return dumps(["quote", form])
    if isinstance(form, (list, tuple)):
        return "(" + " ".join(dumps(x) for x in form) + ")"
    return str(form)


def _bare_symbol(s: str) -> bool:
    if not s:
        return False
    return all(c.isalnum() or c in "._+-*/=<>?!" for c in s) and s[0] not in "0123456789"


def unwrap(form: Form) -> Form:
    if isinstance(form, list) and form and form[0] == "note":
        return form[2]
    return form


def is_block(form: Form) -> bool:
    inner = unwrap(form)
    return isinstance(inner, list) and inner and inner[0] in {"if", "for"}


def nest_by_depth(items: list[tuple[int, Form]]) -> list[Form]:
    """Flat (depth, form) stream → nested if/for bodies (children appended on the form)."""
    root: list[Form] = []
    stack: list[tuple[int, list]] = [(-1, root)]
    for depth, form in items:
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1].append(form)
        inner = unwrap(form)
        if isinstance(inner, list) and inner and inner[0] in {"if", "for"}:
            stack.append((depth, inner))
    return root
