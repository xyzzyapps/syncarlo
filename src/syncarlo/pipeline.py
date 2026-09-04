from __future__ import annotations

from pathlib import Path

from syncarlo.catalog import build_catalog
from syncarlo.codegen import emit_module, spec_symbols
from syncarlo.nlu import NLU, load_rasa_yaml
from syncarlo.parse_md import parse_markdown
from syncarlo.smc import SearchTrace, smc_module


def synthesize_markdown(
    text: str,
    nlu_yaml: str | Path | None = None,
    extra_modules: list[str] | None = None,
    *,
    particles: int = 0,
    topk: int = 4,
    seed: int = 0,
    as_lisp: bool = False,
) -> str:
    spec = parse_markdown(text)
    nlu = NLU(build_catalog(extra_modules))
    extra = load_rasa_yaml(nlu_yaml) if nlu_yaml else []
    nlu.fit(extra or None)
    nlu.symbols = spec_symbols(spec)
    if particles and particles > 0:
        src, _ = smc_module(spec, nlu, particles=particles, topk=topk, seed=seed)
        if as_lisp:
            return emit_module(spec, nlu, as_lisp=True)
        return src
    return emit_module(spec, nlu, as_lisp=as_lisp)


def synthesize_with_trace(
    text: str,
    nlu_yaml: str | Path | None = None,
    extra_modules: list[str] | None = None,
    *,
    particles: int = 16,
    topk: int = 4,
    seed: int = 0,
) -> tuple[str, list[SearchTrace]]:
    spec = parse_markdown(text)
    nlu = NLU(build_catalog(extra_modules))
    extra = load_rasa_yaml(nlu_yaml) if nlu_yaml else []
    nlu.fit(extra or None)
    nlu.symbols = spec_symbols(spec)
    return smc_module(spec, nlu, particles=particles, topk=topk, seed=seed)


def synthesize_file(
    path: str | Path,
    nlu_yaml: str | Path | None = None,
    extra_modules: list[str] | None = None,
    **kwargs,
) -> str:
    return synthesize_markdown(Path(path).read_text(encoding="utf-8"), nlu_yaml, extra_modules, **kwargs)
