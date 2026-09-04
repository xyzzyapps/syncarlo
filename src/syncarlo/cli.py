from __future__ import annotations

import argparse
from pathlib import Path

from syncarlo.pipeline import synthesize_file


def main() -> None:
    p = argparse.ArgumentParser(
        description="SynCarlo: Monte Carlo search from English markdown to Python"
    )
    p.add_argument("spec", help="Markdown spec (headings = functions, numbered lists = body)")
    p.add_argument("-o", "--out", help="Write Python to this path (default stdout)")
    p.add_argument("--nlu", help="Optional Rasa-format nlu.yml with extra intent examples")
    p.add_argument("--module", action="append", default=[], help="Extra Python module to index")
    p.add_argument(
        "--particles",
        type=int,
        default=16,
        help="SMC particles (0 = greedy top-1, no Monte Carlo). Default 16.",
    )
    p.add_argument("--topk", type=int, default=4, help="API candidates per step")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--trace", action="store_true", help="Print particle scores on stderr")
    p.add_argument(
        "--lisp",
        action="store_true",
        help="Emit Lisp IR instead of Python (greedy path; SMC still scores Python)",
    )
    args = p.parse_args()
    if args.particles:
        from syncarlo.pipeline import synthesize_with_trace

        src, traces = synthesize_with_trace(
            Path(args.spec).read_text(encoding="utf-8"),
            nlu_yaml=args.nlu,
            extra_modules=args.module or None,
            particles=args.particles,
            topk=args.topk,
            seed=args.seed,
        )
        if args.lisp:
            src = synthesize_file(
                args.spec,
                nlu_yaml=args.nlu,
                extra_modules=args.module or None,
                particles=0,
                as_lisp=True,
            )
        if args.trace:
            import sys

            for t in traces:
                print(
                    f"# {t.function} score={t.winner_score:.4g} notes={t.winner_notes}",
                    file=sys.stderr,
                )
    else:
        src = synthesize_file(
            args.spec,
            nlu_yaml=args.nlu,
            extra_modules=args.module or None,
            particles=0,
            as_lisp=args.lisp,
        )
    if args.out:
        Path(args.out).write_text(src, encoding="utf-8")
    else:
        print(src)


if __name__ == "__main__":
    main()
