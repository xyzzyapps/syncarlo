"""Sequential Monte Carlo over candidate statements.

Same pattern as agent-harness Best-of-N / particle search over a trace:
  particles = partial programs
  each numbered step = a generation
  expand top-k API matches, score with the verifier, resample.

This is SMC (particle filter), not MCTS: the spec order is already a chain,
so we filter along the list instead of branching a game tree.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from syncarlo.candidates import StmtCandidate, candidates_for
from syncarlo.codegen import parse_heading
from syncarlo.evaluator import EvalResult, evaluate_program
from syncarlo.ir import Section, Spec, Step
from syncarlo.lisp import Form, nest_by_depth
from syncarlo.lisp2py import function_form, module_python, stmt_lines
from syncarlo.nlu import NLU


@dataclass
class Particle:
    items: list  # list[tuple[int, Form]]
    log_prior: float
    weight: float = 1.0
    last_eval: EvalResult | None = None
    indent: int = 0
    lines: list[str] = field(default_factory=list)  # python cache for traces


def _softmax_sample(weights: list[float], rng: random.Random) -> int:
    m = max(weights) if weights else 0.0
    exps = [math.exp(w - m) if w > -1e8 else 0.0 for w in weights]
    z = sum(exps) or 1.0
    r = rng.random() * z
    acc = 0.0
    for i, e in enumerate(exps):
        acc += e
        if acc >= r:
            return i
    return len(exps) - 1


def _resample(particles: list[Particle], n: int, rng: random.Random) -> list[Particle]:
    if not particles:
        return []
    logs = [math.log(max(p.weight, 1e-18)) for p in particles]
    out: list[Particle] = []
    for _ in range(n):
        i = _softmax_sample(logs, rng)
        src = particles[i]
        out.append(
            Particle(
                items=list(src.items),
                log_prior=src.log_prior,
                weight=1.0,
                last_eval=src.last_eval,
                indent=src.indent,
                lines=list(src.lines),
            )
        )
    return out


def _ess(particles: list[Particle]) -> float:
    w = [max(p.weight, 0.0) for p in particles]
    s = sum(w) or 1.0
    norm = [x / s for x in w]
    return 1.0 / sum(x * x for x in norm)


def _lisp_fn(name: str, title: str, items: list, args: list[str] | None = None) -> Form:
    body = nest_by_depth(items)
    return function_form(name, args or [], body, title=title)


def _wrap_fn(name: str, title: str, items: list, args: list[str] | None = None) -> str:
    form = _lisp_fn(name, title, items, args)
    return "\n".join(stmt_lines(form, 0))


def _expand_step(
    particles: list[Particle],
    step: Step,
    nlu: NLU,
    fname: str,
    title: str,
    topk: int,
    rng: random.Random,
    fn_args: list[str] | None = None,
) -> list[Particle]:
    cands = candidates_for(step.text, nlu, k=topk)
    nxt: list[Particle] = []
    for p in particles:
        comment = f"{step.number}. {step.text}"
        for c in cands:
            child = _apply_candidate(p, c, comment)
            body = _wrap_fn(fname, title, child.items, fn_args)
            prior = math.exp(child.log_prior)
            ev = evaluate_program(body, prior=prior)
            child.weight = ev.score
            child.last_eval = ev
            nxt.append(child)
    nxt.sort(key=lambda x: x.weight, reverse=True)
    return nxt


def _apply_candidate(p: Particle, c: StmtCandidate, comment: str) -> Particle:
    form = ["note", comment, c.form]
    indent = p.indent + 1 if c.opens_block else p.indent
    items = list(p.items) + [(p.indent, form)]
    return Particle(
        items=items,
        log_prior=p.log_prior + math.log(max(c.prior, 1e-12)),
        indent=indent,
    )


def _close_blocks(p: Particle, target_indent: int) -> Particle:
    return Particle(
        items=list(p.items),
        log_prior=p.log_prior,
        weight=p.weight,
        last_eval=p.last_eval,
        indent=target_indent,
        lines=list(p.lines),
    )


def smc_section(
    section: Section,
    nlu: NLU,
    *,
    particles: int = 16,
    topk: int = 4,
    seed: int = 0,
) -> tuple[str, list[Particle]]:
    rng = random.Random(seed)
    fname, fn_args = parse_heading(section.title)
    n = max(1, particles)
    beam = [Particle(items=[], log_prior=0.0, indent=0) for _ in range(n)]

    def walk(steps: list[Step], indent: int) -> None:
        nonlocal beam
        beam = [_close_blocks(p, indent) for p in beam]
        for step in steps:
            expanded = _expand_step(beam, step, nlu, fname, section.title, topk, rng, fn_args)
            # keep a pool then resample to n particles (harness Best-of-N + filter)
            pool = expanded[: max(n * 4, n)]
            if _ess(pool) < n / 2:
                beam = _resample(pool, n, rng)
            else:
                beam = pool[:n]
            if step.children:
                opened = [p for p in beam if p.indent > indent]
                closed = [p for p in beam if p.indent == indent]
                saved = list(beam)
                if opened:
                    beam = opened
                    walk(step.children, indent + 1)
                    opened_done = [_close_blocks(p, indent) for p in beam]
                else:
                    opened_done = []
                if closed:
                    beam = closed
                    walk(step.children, indent)
                    closed_done = [_close_blocks(p, indent) for p in beam]
                else:
                    closed_done = []
                beam = (opened_done + closed_done) or [_close_blocks(p, indent) for p in saved]
            else:
                fixed = []
                for p in beam:
                    if p.indent > indent:
                        extra = list(p.items) + [(p.indent, ["pass"])]
                        fixed.append(
                            _close_blocks(
                                Particle(extra, p.log_prior, p.weight, p.last_eval, p.indent),
                                indent,
                            )
                        )
                    else:
                        fixed.append(_close_blocks(p, indent))
                beam = fixed

    walk(section.steps, 0)
    beam.sort(key=lambda p: p.weight, reverse=True)
    best = beam[0] if beam else Particle(items=[(0, ["pass"])], log_prior=0.0)
    for p in beam:
        p.lines = _wrap_fn(fname, section.title, p.items, fn_args).splitlines()
    return _wrap_fn(fname, section.title, best.items, fn_args), beam


MODULE_HEAD = '''\
"""Synthesized from markdown spec. Search-based, no LLM."""
from __future__ import annotations

import csv
import json
import math
import os
import random
import re
from datetime import datetime
from pathlib import Path
'''


@dataclass
class SearchTrace:
    function: str
    particles: int
    winner_score: float
    winner_notes: list[str]
    runner_up: str | None = None


def smc_module(
    spec: Spec,
    nlu: NLU,
    *,
    particles: int = 16,
    topk: int = 4,
    seed: int = 0,
) -> tuple[str, list[SearchTrace]]:
    funcs: list[str] = []
    names: list[str] = []
    traces: list[SearchTrace] = []
    for i, sec in enumerate(spec.sections):
        if sec.level == 1 and spec.title and sec.title == spec.title and not sec.steps:
            continue
        src, beam = smc_section(sec, nlu, particles=particles, topk=topk, seed=seed + i)
        funcs.append(src)
        names.append(parse_heading(sec.title)[0])
        best = beam[0] if beam else None
        ru = None
        if len(beam) > 1 and beam[1].items != (best.items if best else []):
            ru = "\n".join(beam[1].lines[:6])
        traces.append(
            SearchTrace(
                function=names[-1],
                particles=len(beam),
                winner_score=best.weight if best else 0.0,
                winner_notes=list(best.last_eval.notes) if best and best.last_eval else [],
                runner_up=ru,
            )
        )
    body = "\n\n".join(funcs)
    prelude = module_python([], None).rstrip() + "\n\n"
    tail = f'\n\n\nif __name__ == "__main__":\n    {names[0]}()\n' if names else ""
    return prelude + body + tail, traces
