from syncarlo.nlu import NLU


def test_open_intent():
    nlu = NLU()
    nlu.fit()
    p = nlu.parse('open the file "data.csv" as handle')
    assert p.entry is not None
    labels = {e.label for e in p.entities}
    assert "quoted" in labels or "path" in labels


def test_for_each():
    nlu = NLU()
    nlu.fit()
    p = nlu.parse("for each row in rows")
    assert p.entry is not None
    assert p.entry.control in {"for", None} or "for" in p.intent
