"""Library of callable Python APIs: name, signature, docstring, synonyms."""

from __future__ import annotations

import builtins
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Param:
    name: str
    kind: str
    annotation: str
    default: Any = inspect.Parameter.empty


@dataclass
class ApiEntry:
    qname: str
    name: str
    module: str
    signature: str
    docstring: str
    params: list[Param]
    synonyms: list[str] = field(default_factory=list)
    template: str | None = None  # how to emit a call, e.g. "{name}({args})"
    control: str | None = None  # if/for/return/assign/print

    def search_text(self) -> str:
        parts = [self.name, self.qname, self.docstring or "", " ".join(self.synonyms)]
        parts.extend(p.name for p in self.params)
        return " ".join(parts).lower()


def _params_of(fn: Callable) -> list[Param]:
    try:
        sig = inspect.signature(fn)
    except (ValueError, TypeError):
        return []
    out = []
    for p in sig.parameters.values():
        ann = "" if p.annotation is inspect.Parameter.empty else getattr(p.annotation, "__name__", str(p.annotation))
        out.append(Param(p.name, str(p.kind), ann, p.default))
    return out


def _entry(fn: Callable, qname: str, synonyms: list[str] | None = None, template: str | None = None) -> ApiEntry:
    doc = inspect.getdoc(fn) or ""
    return ApiEntry(
        qname=qname,
        name=fn.__name__,
        module=getattr(fn, "__module__", ""),
        signature=str(inspect.signature(fn)) if _safe_sig(fn) else "()",
        docstring=doc.split("\n\n")[0][:400],
        params=_params_of(fn),
        synonyms=synonyms or [],
        template=template,
    )


def _safe_sig(fn: Callable) -> bool:
    try:
        inspect.signature(fn)
        return True
    except (ValueError, TypeError):
        return False


CONTROL_ENTRIES = [
    ApiEntry(
        qname="ctrl.if",
        name="if",
        module="ctrl",
        signature="(condition)",
        docstring="branch if a condition holds",
        params=[Param("condition", "POSITIONAL_OR_KEYWORD", "bool")],
        synonyms=["if", "when", "unless", "only if", "in case"],
        control="if",
    ),
    ApiEntry(
        qname="ctrl.for",
        name="for",
        module="ctrl",
        signature="(item, iterable)",
        docstring="iterate over each item in a collection",
        params=[Param("item", "POSITIONAL_OR_KEYWORD", "Any"), Param("iterable", "POSITIONAL_OR_KEYWORD", "Any")],
        synonyms=["for each", "for every", "loop over", "iterate", "over each"],
        control="for",
    ),
    ApiEntry(
        qname="ctrl.return",
        name="return",
        module="ctrl",
        signature="(value)",
        docstring="return a value from the function",
        params=[Param("value", "POSITIONAL_OR_KEYWORD", "Any")],
        synonyms=["return", "yield the result", "give back"],
        control="return",
    ),
    ApiEntry(
        qname="ctrl.assign",
        name="assign",
        module="ctrl",
        signature="(name, value)",
        docstring="bind a name to a value",
        params=[Param("name", "POSITIONAL_OR_KEYWORD", "str"), Param("value", "POSITIONAL_OR_KEYWORD", "Any")],
        synonyms=["set", "let", "assign", "store", "put into", "save as"],
        control="assign",
    ),
    ApiEntry(
        qname="builtins.print",
        name="print",
        module="builtins",
        signature="(*values)",
        docstring="print values to stdout",
        params=[Param("values", "VAR_POSITIONAL", "Any")],
        synonyms=["print", "display", "show", "log", "write to console"],
        control="print",
    ),
]


SYNONYMS: dict[str, list[str]] = {
    "open": ["open file", "read file", "open the file", "load file"],
    "len": ["length of", "number of", "count of", "size of", "how many"],
    "sum": ["sum of", "total of", "add up"],
    "min": ["minimum", "smallest", "least"],
    "max": ["maximum", "largest", "greatest"],
    "sorted": ["sort", "order", "arrange"],
    "reversed": ["reverse", "backwards"],
    "enumerate": ["index and item", "with index"],
    "zip": ["pair", "combine sequences"],
    "range": ["from to", "integers from"],
    "abs": ["absolute value"],
    "round": ["round to"],
    "int": ["convert to integer", "as int"],
    "str": ["convert to string", "as string"],
    "float": ["convert to float"],
    "list": ["as list", "make a list"],
    "dict": ["as dict", "make a dictionary"],
    "set": ["as set", "unique"],
    "any": ["any of", "exists"],
    "all": ["all of", "every"],
    "map": ["apply to each", "transform"],
    "filter": ["keep where", "select where", "filter"],
    "join": ["join with", "concatenate with"],
    "split": ["split by", "split on"],
    "strip": ["trim", "strip whitespace"],
    "replace": ["replace", "substitute"],
    "startswith": ["starts with", "begins with"],
    "endswith": ["ends with"],
    "lower": ["lowercase", "to lower case"],
    "upper": ["uppercase", "to upper case"],
    "append": ["append", "add to list", "push"],
    "extend": ["extend list", "add all"],
    "pop": ["pop", "remove last"],
    "get": ["get key", "lookup"],
    "items": ["key value pairs"],
    "keys": ["dictionary keys"],
    "values": ["dictionary values"],
    "read": ["read contents", "read text"],
    "readlines": ["read lines"],
    "write": ["write to file", "save to file"],
    "close": ["close file"],
    "json.loads": ["parse json", "load json string"],
    "json.dumps": ["dump json", "serialize json"],
    "json.load": ["load json file"],
    "json.dump": ["write json file"],
    "os.path.join": ["join path", "path join"],
    "os.path.exists": ["file exists", "path exists"],
    "os.listdir": ["list directory", "list files"],
    "pathlib.Path": ["path object"],
    "csv.reader": ["read csv", "csv rows"],
    "csv.writer": ["write csv"],
    "re.search": ["regex search", "match pattern"],
    "re.sub": ["regex replace"],
    "math.sqrt": ["square root"],
    "math.floor": ["floor"],
    "math.ceil": ["ceiling"],
    "random.choice": ["pick random", "random element"],
    "datetime.datetime.now": ["current time", "now"],
}


def _try_import(mod: str):
    import importlib

    try:
        return importlib.import_module(mod)
    except Exception:
        return None


def build_catalog(extra_modules: list[str] | None = None) -> list[ApiEntry]:
    entries: list[ApiEntry] = list(CONTROL_ENTRIES)

    builtin_names = [
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "int", "len", "list", "max", "min", "open", "print", "range", "reversed",
        "round", "set", "sorted", "str", "sum", "tuple", "zip", "map", "isinstance",
        "hasattr", "getattr", "setattr", "type", "repr", "hex", "bin", "ord", "chr",
        "pow", "divmod", "input", "iter", "next", "slice", "format",
    ]
    for name in builtin_names:
        fn = getattr(builtins, name)
        if callable(fn):
            entries.append(_entry(fn, f"builtins.{name}", SYNONYMS.get(name, [])))

    # string methods as templates on an object
    str_methods = ["split", "join", "strip", "replace", "startswith", "endswith", "lower", "upper", "find", "format"]
    for m in str_methods:
        fn = getattr(str, m)
        e = _entry(fn, f"str.{m}", SYNONYMS.get(m, []), template=f"{{receiver}}.{m}({{args}})")
        entries.append(e)

    list_methods = ["append", "extend", "pop", "index", "count", "sort", "reverse"]
    for m in list_methods:
        fn = getattr(list, m)
        entries.append(_entry(fn, f"list.{m}", SYNONYMS.get(m, []), template=f"{{receiver}}.{m}({{args}})"))

    dict_methods = ["get", "items", "keys", "values", "update", "pop"]
    for m in dict_methods:
        fn = getattr(dict, m)
        entries.append(_entry(fn, f"dict.{m}", SYNONYMS.get(m, []), template=f"{{receiver}}.{m}({{args}})"))

    modules = ["os", "os.path", "json", "csv", "re", "math", "random", "datetime", "pathlib", "collections", "itertools"]
    if extra_modules:
        modules.extend(extra_modules)
    for modname in modules:
        mod = _try_import(modname)
        if mod is None:
            continue
        for name, obj in vars(mod).items():
            if name.startswith("_"):
                continue
            if not callable(obj):
                continue
            if inspect.isclass(obj) and modname not in {"pathlib", "collections"}:
                continue
            qname = f"{modname}.{name}"
            syn = SYNONYMS.get(qname, SYNONYMS.get(name, []))
            try:
                entries.append(_entry(obj, qname, syn))
            except Exception:
                continue

    # de-dupe by qname
    seen: dict[str, ApiEntry] = {}
    for e in entries:
        seen.setdefault(e.qname, e)
    return list(seen.values())
