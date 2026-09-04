from syncarlo.lisp import Sym, dumps, nest_by_depth
from syncarlo.lisp2py import stmt_lines


def test_lisp_to_python_let_and_call():
    form = ["let", Sym("handle"), ["call", Sym("open"), "todos.json"]]
    py = "\n".join(stmt_lines(form, 0))
    assert py == "handle = open('todos.json')"


def test_lisp_to_python_for_if():
    form = [
        "for",
        Sym("item"),
        Sym("todos"),
        ["if", ["==", Sym("item"), Sym("title")], ["print", "done"]],
    ]
    py = "\n".join(stmt_lines(form, 0))
    assert "for item in todos:" in py
    assert "if item == title:" in py
    assert "print('done')" in py


def test_nest_if_children():
    items = [
        (0, ["for", "item", "todos"]),
        (1, ["if", ["==", "item", "title"]]),
        (2, ["print", "done"]),
    ]
    body = nest_by_depth(items)
    assert body[0][0] == "for"
    assert body[0][3][0] == "if"
    dumped = dumps(body[0])
    assert dumped.startswith("(for ")
    assert "if" in dumped
