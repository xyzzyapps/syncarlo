"""Harness-style verifier: compile + sandboxed execute + static reasonableness.

Same split many agent harnesses use for Best-of-N / SMC:
  reward = prior * P(valid | program) estimated by cheap checks and a dry-run.
"""

from __future__ import annotations

import ast
import builtins as py_builtins
import io
import traceback
from dataclasses import dataclass, field



PRELUDE = """\
from __future__ import annotations
import csv, json, math, os, random, re
from datetime import datetime
from pathlib import Path
"""


@dataclass
class EvalResult:
    score: float
    compile_ok: bool
    ran: bool
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def _defined_and_used(tree: ast.AST) -> tuple[set[str], set[str]]:
    defined: set[str] = {
        "csv", "json", "math", "os", "random", "re", "datetime", "Path",
        "True", "False", "None",
    }
    used: set[str] = set()

    class V(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            defined.add(node.name)
            for a in node.args.args:
                defined.add(a.arg)
            self.generic_visit(node)

        def visit_Assign(self, node: ast.Assign) -> None:
            self.visit(node.value)
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defined.add(t.id)
                else:
                    self.visit(t)

        def visit_For(self, node: ast.For) -> None:
            self.visit(node.iter)
            if isinstance(node.target, ast.Name):
                defined.add(node.target.id)
            for b in node.body:
                self.visit(b)

        def visit_Name(self, node: ast.Name) -> None:
            if isinstance(node.ctx, ast.Load):
                used.add(node.id)
            elif isinstance(node.ctx, ast.Store):
                defined.add(node.id)

    V().visit(tree)
    return defined, used


def static_score(source: str) -> tuple[float, list[str], ast.AST | None]:
    notes: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return 0.0, [f"syntax: {e}"], None
    s = 1.0
    defined, used = _defined_and_used(tree)
    builtins_names = set(dir(py_builtins))
    unbound = sorted(
        n for n in used
        if n not in defined and n not in builtins_names and not n.startswith("__")
    )
    if unbound:
        s *= 0.25 ** min(3, len(unbound))
        notes.append("unbound: " + ", ".join(unbound[:8]))
    else:
        s *= 1.4
        notes.append("names-ok")
    # empty/pass-only bodies are weak
    if source.count("pass") and "return" not in source:
        s *= 0.7
        notes.append("has-pass")
    return s, notes, tree


_SAFE_BUILTINS = {
    "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
    "int", "len", "list", "max", "min", "print", "range", "reversed",
    "round", "set", "sorted", "str", "sum", "tuple", "zip", "map",
    "isinstance", "hasattr", "getattr", "type", "repr", "ord", "chr",
    "pow", "divmod", "iter", "next", "slice", "format", "True", "False",
    "None", "object", "Exception", "ValueError", "TypeError", "KeyError",
    "IndexError", "StopIteration", "enumerate",
}


class _FakeFile(io.StringIO):
    def __init__(self, initial: str = "", name: str = "mem") -> None:
        super().__init__(initial)
        self.name = name

    def __enter__(self) -> "_FakeFile":
        return self

    def __exit__(self, *args) -> None:
        return None


def _fake_open(path, mode="r", *args, **kwargs):
    p = str(path)
    if "w" in mode or "a" in mode or "x" in mode:
        return _FakeFile("", p)
    # seed a tiny csv/json so readers do not immediately fail
    if p.endswith(".json"):
        return _FakeFile('{"status": "active", "n": 1}', p)
    return _FakeFile("id,status\n1,active\n2,inactive\n", p)


def _allowed_import(name, globals=None, locals=None, fromlist=(), level=0):
    allow = {
        "__future__", "csv", "json", "math", "os", "random", "re", "datetime", "pathlib",
        "collections", "itertools", "io", "functools", "operator",
    }
    root = name.split(".")[0]
    if root not in allow:
        raise ImportError(f"blocked import {name}")
    return py_builtins.__import__(name, globals, locals, fromlist, level)


def execute_score(source: str, timeout_s: float = 0.5) -> tuple[float, str | None]:
    """Dry-run in a restricted namespace. No real filesystem, no imports of user code."""
    ns: dict = {"__name__": "synth"}
    safe = {k: getattr(py_builtins, k) for k in _SAFE_BUILTINS if hasattr(py_builtins, k)}
    safe["open"] = _fake_open
    safe["__import__"] = _allowed_import
    ns["__builtins__"] = safe
    try:
        compiled = compile(source, "<synth>", "exec")
        exec(compiled, ns, ns)
    except Exception as e:
        return 0.15, f"{type(e).__name__}: {e}"

    # call top-level functions with no args
    ran_any = False
    last_err = None
    for name, obj in list(ns.items()):
        if name.startswith("_") or not callable(obj):
            continue
        if type(obj).__name__ != "function":
            continue
        try:
            obj()
            ran_any = True
        except TypeError as e:
            # likely needs args — not fatal
            last_err = str(e)
            ran_any = True
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            return 0.35, last_err
    if ran_any:
        return 1.0, None
    return 0.5, last_err


def evaluate_program(body: str, prior: float = 1.0) -> EvalResult:
    source = PRELUDE + "\n" + body
    st, notes, tree = static_score(source)
    if tree is None:
        return EvalResult(score=1e-8 * prior, compile_ok=False, ran=False, error=notes[0], notes=notes)
    dyn, err = execute_score(source)
    score = max(1e-12, prior) * st * (0.4 + 0.6 * dyn)
    notes.append(f"static={st:.3f}")
    notes.append(f"dyn={dyn:.3f}")
    notes.append(f"prior={prior:.3f}")
    return EvalResult(
        score=score,
        compile_ok=True,
        ran=err is None,
        error=err,
        notes=notes,
    )
