from syncarlo.pipeline import synthesize_markdown


def test_heading_becomes_function():
    src = synthesize_markdown(
        """
## greet

1. Print "hello"
2. Return 0
"""
    )
    assert "def greet():" in src
    assert "print(" in src
    assert "return " in src
