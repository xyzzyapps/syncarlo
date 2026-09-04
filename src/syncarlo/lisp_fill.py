"""Fill a Lisp form from an API match + English roles."""

from __future__ import annotations

import re

from syncarlo.catalog import ApiEntry
from syncarlo.extract import Entity
from syncarlo.lisp import Sym

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_NUM = re.compile(r"^-?\d+(?:\.\d+)?$")


def S(x: object) -> object:
    if isinstance(x, (Sym, int, float, bool, list)) or x is None:
        return x
    return Sym(str(x))


def _lit(ent: Entity) -> object:
    if ent.label in {"quoted", "path"}:
        return ent.value
    if ent.label == "number":
        raw = ent.value
        return float(raw) if "." in raw else int(raw)
    return S(ent.value)


def _sym_or_lit(token: str) -> object:
    if _NUM.match(token):
        return float(token) if "." in token else int(token)
    if (token.startswith('"') and token.endswith('"')) or (token.startswith("'") and token.endswith("'")):
        return token[1:-1]
    return S(token)


def fill_form(
    entry: ApiEntry,
    entities: list[Entity],
    sentence: str,
    symbols: dict[str, list[str]] | None = None,
) -> list:
    from syncarlo.codegen import _bind_name, bind_signature

    symbols = symbols or {}
    names = [e.value for e in entities if e.label in {"name", "ident"} and e.role != "verb"]
    bind = _bind_name(entities)

    def maybe_let(form: list) -> list:
        return ["let", S(bind), form] if bind else form

    if entry.qname.startswith("sym."):
        fn = entry.qname.split(".", 1)[1]
        formals = symbols.get(fn, [])
        actual = [n for n in names if n != fn and n != bind]
        if not actual and formals:
            actual = [a for a in formals if a in names]
        return maybe_let(["call", S(fn), *[S(a) for a in actual]])

    if entry.template and "{receiver}" in entry.template:
        goal = next((e.value for e in entities if e.role == "goal"), None)
        theme = next((e.value for e in entities if e.role in {"theme", None} and e.label == "ident"), None)
        receiver = goal or (names[-1] if names else "_obj")
        arg: object | None = theme
        if arg == receiver:
            arg = None
        q = next((e for e in entities if e.label == "quoted"), None)
        if q and entry.name in {"split", "replace", "join"}:
            arg = _lit(q)
        parts: list = ["method", S(receiver), S(entry.name)]
        if arg is not None and arg != "":
            parts.append(S(arg) if isinstance(arg, str) else arg)
        return maybe_let(parts)

    if entry.control == "if":
        m = re.search(r"(?:if|when|unless)\s+(\w+)\s+is\s+(.+)$", sentence, re.I)
        if m:
            lhs, rhs = m.group(1), m.group(2).strip().rstrip(".")
            quoted = next((e for e in entities if e.label == "quoted"), None)
            right: object
            if quoted:
                right = _lit(quoted)
            elif IDENT_RE.match(rhs):
                right = rhs
            else:
                right = _sym_or_lit(rhs)
            return ["if", ["==", S(lhs), S(right) if isinstance(right, str) and IDENT_RE.match(str(right)) else right]]
        return ["if", S(names[0]) if names else True]

    if entry.control == "for":
        m = re.search(r"(?:each|every)\s+(\w+)\s+(?:in|of)\s+(\w+)", sentence, re.I)
        if m:
            return ["for", S(m.group(1)), S(m.group(2))]
        if len(names) >= 2:
            return ["for", S(names[0]), S(names[1])]
        return ["for", S("item"), S(names[0] if names else "items")]

    if entry.control == "return":
        m = re.search(r"return\s+(\S+)", sentence, re.I)
        if m:
            return ["return", _sym_or_lit(m.group(1).strip(".,"))]
        val: object = names[-1] if names else (_lit(entities[0]) if entities else None)
        return ["return", val]

    if entry.control == "assign":
        m = re.search(r"\b(?:set|let|store)\s+(\w+)\s+(?:to|be|as)\s+(.+)$", sentence, re.I)
        name = m.group(1) if m else (bind or names[0] if names else "value")
        rhs_raw = m.group(2).strip().rstrip(".") if m else "none"
        ctor = {"list": ["call", "list"], "dict": ["call", "dict"], "set": ["call", "set"], "none": None, "true": True, "false": False}
        first = rhs_raw.split()[0]
        if first.lower() in ctor:
            rhs: object = ctor[first.lower()]
            if first.lower() == "list":
                rhs = ["quote", []]
            elif first.lower() == "dict":
                rhs = ["quote", {}]
        elif first in symbols:
            rest = [t for t in rhs_raw.split()[1:] if IDENT_RE.match(t)]
            formals = symbols[first]
            args = rest or [n for n in names if n != name and n != first]
            if not args and formals:
                args = [a for a in formals if a != name]
            rhs = ["call", S(first), *[S(a) for a in args]]
        elif IDENT_RE.match(rhs_raw):
            rhs = ["call", S(rhs_raw)] if rhs_raw in symbols else S(rhs_raw)
        else:
            rhs = first if IDENT_RE.match(first) else rhs_raw
        return ["let", S(name), S(rhs) if isinstance(rhs, str) else rhs]

    if entry.control == "print":
        bits = [
            _lit(e)
            for e in entities
            if e.role != "verb" and e.label in {"quoted", "path", "number", "ident"}
        ]
        return ["print", *(bits or [None])]

    args = bind_signature(entry, entities, sentence)
    parsed_args: list = []
    for a in args:
        if a.startswith("'") or a.startswith('"'):
            parsed_args.append(a.strip("'\""))
        elif _NUM.match(a):
            parsed_args.append(float(a) if "." in a else int(a))
        else:
            parsed_args.append(S(a) if IDENT_RE.match(str(a)) else a)
    if entry.qname.startswith("builtins."):
        call = ["call", S(entry.name), *parsed_args]
    else:
        call = ["call", S(entry.qname), *parsed_args]
    return maybe_let(call)
