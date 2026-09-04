# SynCarlo

**Search the docs. Read the English. Roll for the program.**

SynCarlo is search-based program synthesis with Monte Carlo reasoning.

You write a markdown spec. Each heading is a function. Each numbered sentence
is a statement. SynCarlo retrieves Python APIs from names and docstrings
(NLU, no LLM), fills arguments from English prepositions, then **rolls** a
particle filter over the top-k matches and keeps the program that actually
parses and dry-runs.

```
  markdown spec          catalog (Python)
        │                        │
        ▼                        ▼
   numbered English  ←→  BM25 + stems + signatures
        │
        ▼
   top-k sketches per step
        │
        ▼
   sequential Monte Carlo (rollouts)
        │
        ▼
   Python source
```

## Install

```powershell
pip install -e .
```

MIT licensed. See `LICENSE`.

## Spec format

```markdown
## load_todos

1. Open the file "todos.json" as handle
2. Load json from handle as todos
3. Return todos
```

Headings may declare parameters: `## save_todos(todos)`.

## Run

```powershell
python -m syncarlo examples/todo.spec.md --particles 8 --topk 4 -o out.py
python -m syncarlo examples/todo.spec.md --particles 0
```

`--particles` is the Monte Carlo beam (0 = greedy). `--trace` prints verifier notes.

## How it thinks

1. **Search** — BM25 over the stdlib catalog (function name, module, docstring).
2. **NLU** — English stemming and roles (`from` / `to` / `as` / `for`). Control
   syntax (`if`, `for each`, `return`, `set X to`) is grammar, not a cheat sheet
   of demo sentences. There is no required training YAML.
3. **Lisp IR** — candidates are S-expressions (`(let handle (call open "todos.json"))`), then a translator emits Python. `--lisp` prints the IR.
4. **Monte Carlo reasoning** — each step expands k Lisp forms; particles are
   nested trees; a sandbox scores the **Python** translation; the MAP particle is emitted.

Same pattern as an agent harness Best-of-N / rollout, without an LLM.

## Layout

| Path | Role |
| --- | --- |
| `src/syncarlo/nlu.py` | catalog retrieval + English roles |
| `src/syncarlo/smc.py` | sequential Monte Carlo |
| `src/syncarlo/evaluator.py` | compile / execute reward |
| `examples/todo.spec.md` | JSON todo manager spec |

## Not magic

SynCarlo cannot invent semantics that are not in the sentence or the catalog.
It will not wrap `"buy milk"` in a dict unless you say so. It will sometimes
tie-break the wrong `open`. Train nothing; write a clearer sentence, or add
an API to the catalog.
