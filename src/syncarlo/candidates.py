"""Top-k statement candidates for one numbered sentence."""

from __future__ import annotations

from dataclasses import dataclass

from syncarlo.catalog import ApiEntry
from syncarlo.lisp import dumps, is_block
from syncarlo.lisp2py import stmt_lines
from syncarlo.lisp_fill import fill_form
from syncarlo.extract import Entity
from syncarlo.nlu import NLU, ParseResult


@dataclass
class StmtCandidate:
    form: list
    source: str
    intent: str
    prior: float
    entry: ApiEntry | None
    entities: list[Entity]
    opens_block: bool


def candidates_for(text: str, nlu: NLU, k: int = 5) -> list[StmtCandidate]:
    parsed: ParseResult = nlu.parse(text)
    out: list[StmtCandidate] = []
    seen: set[str] = set()
    for intent, p in parsed.ranking[:k]:
        entry = nlu.by_qname.get(intent)
        if entry is None and intent.startswith("sym."):
            fn = intent.split(".", 1)[1]
            entry = ApiEntry(intent, fn, "sym", "()", "", [])
        if entry is None:
            continue
        try:
            form = fill_form(entry, parsed.entities, text, nlu.symbols)
            src = "\n".join(stmt_lines(form, 0))
        except Exception:
            continue
        key = dumps(form)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(
            StmtCandidate(
                form=form if isinstance(form, list) else ["quote", form],
                source=src,
                intent=intent,
                prior=float(p),
                entry=entry,
                entities=parsed.entities,
                opens_block=is_block(form),
            )
        )
    if not out:
        out.append(
            StmtCandidate(
                form=["pass"],
                source="pass",
                intent="unknown",
                prior=1e-6,
                entry=None,
                entities=parsed.entities,
                opens_block=False,
            )
        )
    return out
