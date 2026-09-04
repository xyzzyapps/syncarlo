"""Compile SynCarlo Lisp IR to Python."""

from __future__ import annotations

from typing import Any

from syncarlo.lisp import Form, Sym, dumps


def py_atom(form: Form) -> str:
    if form is None:
        return "None"
    if form is True:
        return "True"
    if form is False:
        return "False"
    if isinstance(form, bool):
        return "True" if form else "False"
    if isinstance(form, Sym):
        return str(form)
    if isinstance(form, str):
        if form in {"none", "None"}:
            return "None"
        return repr(form)
    if isinstance(form, (int, float)):
        return str(form)
    if isinstance(form, dict):
        return repr(form)
    if isinstance(form, list) and not form:
        return "[]"
    return expr(form)


_MODULES = {"json", "csv", "os", "re", "math", "random", "pathlib", "sys", "io", "builtins"}
_EXTS = {"json", "csv", "txt", "py", "md", "yml", "yaml", "html", "xml"}


def _is_ident(s: str) -> bool:
    return bool(s) and (s[0].isalpha() or s[0] == "_") and all(c.isalnum() or c == "_" for c in s)


def _is_symbol(s: str) -> bool:
    parts = s.split(".")
    if not all(_is_ident(p) for p in parts):
        return False
    if len(parts) == 1:
        return True
    if parts[0] in _MODULES:
        return True
    if parts[-1].lower() in _EXTS:
        return False
    return True


def expr(form: Form) -> str:
    if not isinstance(form, list):
        return py_atom(form)
    if not form:
        return "None"
    op = form[0]
    if op == "call":
        fn = str(form[1])
        args = ", ".join(expr(a) for a in form[2:])
        return f"{fn}({args})"
    if op == "method":
        recv, name = form[1], form[2]
        args = ", ".join(expr(a) for a in form[3:])
        return f"{expr(recv)}.{name}({args})"
    if op == "==":
        return f"{expr(form[1])} == {expr(form[2])}"
    if op == "quote":
        return repr(form[1]) if len(form) > 1 else "None"
    if op == "let":
        return f"{py_atom(form[1])} = {expr(form[2])}"
    return dumps(form)


def stmt_lines(form: Form, indent: int = 0) -> list[str]:
    pad = "    " * indent
    if not isinstance(form, list) or not form:
        return [pad + py_atom(form)]
    op = form[0]
    if op == "note":
        comment, inner = form[1], form[2]
        return [f"{pad}# {comment}"] + stmt_lines(inner, indent)
    if op == "comment":
        return [f"{pad}# {form[1]}"]
    if op == "do":
        out: list[str] = []
        for child in form[1:]:
            out.extend(stmt_lines(child, indent))
        return out
    if op == "let":
        return [f"{pad}{py_atom(form[1])} = {expr(form[2])}"]
    if op == "return":
        val = expr(form[1]) if len(form) > 1 else "None"
        return [f"{pad}return {val}"]
    if op == "print":
        args = ", ".join(expr(a) for a in form[1:])
        return [f"{pad}print({args})"]
    if op == "pass":
        return [f"{pad}pass"]
    if op == "if":
        cond = expr(form[1])
        body = form[2:]
        lines = [f"{pad}if {cond}:"]
        if not body:
            lines.append(pad + "    pass")
        for b in body:
            lines.extend(stmt_lines(b, indent + 1))
        return lines
    if op == "for":
        var, it = form[1], form[2]
        body = form[3:]
        lines = [f"{pad}for {expr(var)} in {expr(it)}:"]
        if not body:
            lines.append(pad + "    pass")
        for b in body:
            lines.extend(stmt_lines(b, indent + 1))
        return lines
    if op == "def":
        name = form[1]
        args = form[2] if len(form) > 2 else []
        body = form[3:]
        sig = " ".join(str(a) for a in args) if isinstance(args, list) else str(args)
        # args is (x y) stored as list
        if isinstance(args, list):
            sig = ", ".join(str(a) for a in args)
        lines = [f"{pad}def {name}({sig}):"]
        if not body:
            lines.append(pad + "    pass")
        for b in body:
            lines.extend(stmt_lines(b, indent + 1))
        return lines
    # expression used as statement
    return [pad + expr(form)]


def function_form(name: str, args: list[str], body: list[Form], title: str | None = None) -> Form:
    forms: list[Form] = [
        "def",
        Sym(name),
        [Sym(str(a)) for a in args],
    ]
    if title:
        forms.append(["comment", title])
    forms.extend(body)
    return forms


def module_python(defs: list[Form], main: str | None = None) -> str:
    parts = [
        '"""Synthesized by SynCarlo: Lisp IR → Python."""',
        "from __future__ import annotations",
        "",
        "import csv",
        "import json",
        "import math",
        "import os",
        "import random",
        "import re",
        "from datetime import datetime",
        "from pathlib import Path",
        "",
    ]
    blocks = ["\n".join(stmt_lines(d, 0)) for d in defs]
    parts.append("\n\n".join(blocks))
    if main:
        parts.append("")
        parts.append("")
        parts.append('if __name__ == "__main__":')
        parts.append(f"    {main}()")
        parts.append("")
    return "\n".join(parts)


def lisp_module_text(defs: list[Form]) -> str:
    return "\n\n".join(dumps(d) for d in defs) + "\n"
