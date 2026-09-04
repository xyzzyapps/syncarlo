"""Tiny English morphology + function-word inventory. Not an example list."""

from __future__ import annotations

import re

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")

# Closed-class English. Used to ignore noise, not to pick APIs.
FUNCTION_WORDS = {
    "the", "a", "an", "and", "or", "but", "nor",
    "to", "from", "into", "of", "in", "on", "at", "by", "with", "for",
    "as", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "they", "them",
    "if", "then", "when", "while", "each", "every", "all", "any",
    "do", "does", "did", "not", "no",
    "file", "files", "filename",
}

# English constructions that map to Python *syntax*, not to a library function.
CONTROL_PREFIXES = (
    (r"^\s*(set|let|store)\s+\w+\s+(to|be|as)\b", "ctrl.assign"),
    (r"^\s*(for\s+each|for\s+every|loop\s+over|iterate)\b", "ctrl.for"),
    (r"^\s*(if|when|unless)\b", "ctrl.if"),
    (r"^\s*return\b", "ctrl.return"),
    (r"^\s*(print|display|show)\b", "builtins.print"),
)

PREP_ROLE = {
    "from": "source",
    "to": "goal",
    "into": "goal",
    "onto": "goal",
    "as": "bind",
    "with": "comitative",
    "using": "comitative",
    "on": "theme",
    "by": "instrument",
    "in": "locative",
    "of": "theme",
    "for": "purpose",
    "over": "theme",
}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


def stem(word: str) -> str:
    w = word.lower()
    if w.endswith("ing") and len(w) > 5:
        base = w[:-3]
        # writing -> write, loading -> load
        if len(base) <= 4:
            return base + "e"
        return base
    if w.endswith("ied") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ed") and len(w) > 4:
        if w[-3] == w[-4]:
            return w[:-3]
        return w[:-2] if not w.endswith("eed") else w
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    return w


def stems(text: str) -> list[str]:
    out = []
    for t in tokenize(text):
        out.append(t)
        s = stem(t)
        if s != t:
            out.append(s)
    return out
