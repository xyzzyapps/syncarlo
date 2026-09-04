from syncarlo.evaluator import evaluate_program
from syncarlo.pipeline import synthesize_markdown, synthesize_with_trace


SPEC = """
## greet

1. Print "hello"
2. Return 0
"""


def test_evaluator_prefers_valid_python():
    good = evaluate_program('def greet():\n    print("hello")\n    return 0\n', prior=0.5)
    bad = evaluate_program("def greet():\n    print(no_such_name)\n", prior=0.9)
    assert good.compile_ok
    assert good.score > bad.score


def test_smc_picks_a_function():
    src, traces = synthesize_with_trace(SPEC, particles=8, topk=3, seed=1)
    assert "def greet():" in src
    assert traces[0].winner_score > 0


def test_greedy_still_works():
    src = synthesize_markdown(SPEC, particles=0)
    assert "def greet():" in src
