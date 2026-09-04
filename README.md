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

## Research

SynCarlo follows **Neural Program Search** (Polosukhin & Skidanov, 2018):

> Illia Polosukhin and Alex Skidanov. *Neural Program Search: Solving Programming Tasks from Description and Examples.* arXiv:1802.04335, 2018.  
> https://arxiv.org/abs/1802.04335

That paper synthesizes programs in a **typed Lisp DSL** from a short English description plus I/O examples. A Seq2Tree model scores AST symbols; **tree beam search** fills holes; the first complete tree that **passes the tests** wins.

SynCarlo uses the same split — **language ranks candidates, search enumerates, execution picks** — with different pieces:

| | Neural Program Search | SynCarlo |
| --- | --- | --- |
| Spec | One paragraph + I/O pairs | Markdown heading + numbered sentences |
| Search space | Their Lisp DSL (`map` / `filter` / `reduce`) | A small Lisp IR (`let` / `call` / `if` / `for`) over a Python catalog |
| Language | Trained Seq2Tree | BM25 + English roles (no neural net) |
| Search | Tree beam over AST nodes | Sequential Monte Carlo over top-k fills |
| Checker | Run I/O tests | Compile + sandboxed dry-run of the **Python** translation |
| Output | Lisp in their DSL | Lisp IR → Python |

Also related: DeepCoder (Balog et al., 2016) and FlashFill / PROSE.

### Related repositories

Nothing public matched “heading = function, numbered English → retrieve docstring/API → Lisp → Python” as a non-LLM pipeline. Closest public code:

| Repo | What it does | vs SynCarlo |
| --- | --- | --- |
| [nearai/program_synthesis](https://github.com/nearai/program_synthesis) | AlgoLISP / Karel / NAPS — neural synthesis; implements Neural Program Search | Same Lisp+search idea; they train Seq2Tree, we retrieve Python |
| [ayushnoori/program-synthesis](https://github.com/ayushnoori/program-synthesis) | Bottom-up enumerative synthesis (BUSTLE-style) from **I/O examples** | Search without English/markdown |
| [shuyanzhou/docprompting](https://github.com/shuyanzhou/docprompting) | Retrieve docs, then generate code (ICLR 2023) | Doc retrieval like our catalog; **neural** decoder |
| [uilicious/english-compiler](https://github.com/uilicious/english-compiler) | Markdown spec → code | Same spec-as-source instinct; **LLM** compiler |
| [flxsosa/ProgramSearch](https://github.com/flxsosa/ProgramSearch) | Write–Execute–Assess (NeurIPS 2019) — REPL-guided search | Execute-to-score like our sandbox; neural policy |
| [namin/holey](https://github.com/namin/holey) | Fill holes in Python with SMT + optional LLM | Sketch filling; not markdown NLU |
| [RasaHQ/rasa](https://github.com/RasaHQ/rasa) | Intent + entity NLU for chatbots | Slot filling analogue; not codegen (we do not use Rasa) |

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
