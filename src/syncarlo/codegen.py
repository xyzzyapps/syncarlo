"""Turn a heading (function) + numbered steps into Python source."""

from __future__ import annotations

import keyword
import re

from syncarlo.catalog import ApiEntry
from syncarlo.english import stem, tokenize
from syncarlo.extract import Entity, python_literal
from syncarlo.ir import Section, Spec, Step
from syncarlo.nlu import NLU, ParseResult

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

HEADING_SIG_RE = re.compile(
    r"^(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\((?P<args>[^)]*)\)\s*$"
)

FILEISH = {"file", "fp", "path", "handle", "stream", "f", "source", "filename"}
MODEISH = {"mode"}


def parse_heading(title: str) -> tuple[str, list[str]]:
    m = HEADING_SIG_RE.match(title.strip())
    if m:
        name = m.group("name")
        args = [a.strip() for a in m.group("args").split(",") if a.strip() and IDENT_RE.match(a.strip())]
        return heading_to_func_name(name), args
    return heading_to_func_name(title), []


def heading_to_func_name(title: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9]+", "_", title.strip()).strip("_").lower()
    if not raw:
        raw = "untitled"
    if raw[0].isdigit() or keyword.iskeyword(raw):
        raw = f"fn_{raw}"
    return raw


def spec_symbols(spec: Spec) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for sec in spec.sections:
        name, args = parse_heading(sec.title)
        out[name] = args
    return out


def _bind_name(entities: list[Entity]) -> str | None:
    return next((e.value for e in entities if e.role == "bind" or e.label == "name"), None)


def _param_score(param_name: str, ent: Entity) -> float:
    pn = param_name.lower()
    ev = ent.value.lower()
    s = 0.0
    if pn == ev or stem(pn) == stem(ev):
        s += 3.0
    if ent.role in {"source", "goal"} and pn in FILEISH:
        s += 2.0
    if ent.label in {"path", "quoted"} and pn in FILEISH:
        s += 2.5
    if ent.role == "purpose" and pn in MODEISH:
        s += 2.0
    if ent.role == "theme" and pn not in FILEISH | MODEISH:
        s += 0.8
    if ent.label == "number" and pn in {"n", "i", "k", "count", "size"}:
        s += 1.5
    return s


def bind_signature(entry: ApiEntry, entities: list[Entity], sentence: str) -> list[str]:
    params = [p for p in entry.params if p.name not in {"self", "cls"}]
    args: list[str | None] = [None] * len(params)
    used: set[int] = set()
    modules = {"json", "csv", "os", "re", "math", "random", "pathlib", "sys", "io"}
    pool = [
        e
        for e in entities
        if e.role not in {"bind", "verb"}
        and e.label != "name"
        and e.value.lower() not in modules
        and not (e.role == "purpose" and stem(e.value) in {"write", "read", "append"})
    ]

    for pi, p in enumerate(params):
        best_i, best_s = -1, 0.4
        for ei, e in enumerate(pool):
            if ei in used:
                continue
            sc = _param_score(p.name, e)
            if sc > best_s:
                best_s, best_i = sc, ei
        if best_i >= 0:
            args[pi] = python_literal(pool[best_i])
            used.add(best_i)

    # leftover literals fill leftover params left-to-right
    leftovers = [e for i, e in enumerate(pool) if i not in used]
    for pi, slot in enumerate(args):
        if slot is None and leftovers:
            args[pi] = python_literal(leftovers.pop(0))

    # mode from English "write"/"read" if the signature has mode
    sent_stems = {stem(t) for t in tokenize(sentence)}
    for pi, p in enumerate(params):
        if p.name.lower() in MODEISH and args[pi] is None:
            if "write" in sent_stems or "save" in sent_stems:
                args[pi] = "'w'"
            elif "read" in sent_stems:
                args[pi] = "'r'"
        # os.open flags are an int, never a mode string
        if p.name.lower() in {"flags", "flag"} and args[pi] and args[pi].startswith("'"):
            args[pi] = None

    return [a for a in args if a is not None]


def fill_call(
    entry: ApiEntry,
    entities: list[Entity],
    sentence: str,
    symbols: dict[str, list[str]] | None = None,
) -> str:
    from syncarlo.lisp2py import stmt_lines
    from syncarlo.lisp_fill import fill_form

    form = fill_form(entry, entities, sentence, symbols)
    return "\n".join(stmt_lines(form, 0))


def _form_for_step(step: Step, nlu: NLU) -> list:
    from syncarlo.catalog import ApiEntry as AE
    from syncarlo.lisp_fill import fill_form

    parsed: ParseResult = nlu.parse(step.text)
    if parsed.intent.startswith("sym."):
        fake = AE(parsed.intent, parsed.intent.split(".", 1)[1], "sym", "()", "", [])
        inner = fill_form(fake, parsed.entities, step.text, nlu.symbols)
    elif parsed.entry is None or parsed.confidence < 0.05:
        inner = ["pass"]
    else:
        inner = fill_form(parsed.entry, parsed.entities, step.text, nlu.symbols)
    return ["note", f"{step.number}. {step.text}", inner]


def section_lisp(section: Section, nlu: NLU) -> list:
    from syncarlo.lisp import nest_by_depth
    from syncarlo.lisp2py import function_form

    fname, args = parse_heading(section.title)
    items: list[tuple[int, list]] = []

    def walk(steps: list[Step], depth: int) -> None:
        for st in steps:
            items.append((depth, _form_for_step(st, nlu)))
            if st.children:
                walk(st.children, depth + 1)

    walk(section.steps, 0)
    body = nest_by_depth(items) if items else [["pass"]]
    return function_form(fname, args, body, title=section.title)


def emit_section(section: Section, nlu: NLU) -> str:
    from syncarlo.lisp2py import stmt_lines

    return "\n".join(stmt_lines(section_lisp(section, nlu), 0))


def emit_module(spec: Spec, nlu: NLU, *, as_lisp: bool = False) -> str:
    from syncarlo.lisp2py import lisp_module_text, module_python

    nlu.symbols = spec_symbols(spec)
    defs = []
    names = []
    for sec in spec.sections:
        if sec.level == 1 and spec.title and sec.title == spec.title and not sec.steps:
            continue
        defs.append(section_lisp(sec, nlu))
        names.append(parse_heading(sec.title)[0])
    if as_lisp:
        return lisp_module_text(defs)
    return module_python(defs, names[0] if names else None)
