from syncarlo.parse_md import parse_markdown


def test_heading_and_nested_lists():
    spec = parse_markdown(
        """
# Doc

## load_rows

1. Open the file "data.csv"
   1. Read all lines
   2. Skip the header
2. Return lines
"""
    )
    assert spec.title == "Doc"
    sec = spec.sections[1]
    assert sec.title == "load_rows"
    assert len(sec.steps) == 2
    assert sec.steps[0].text.startswith("Open")
    assert len(sec.steps[0].children) == 2
    assert sec.steps[1].text.startswith("Return")
