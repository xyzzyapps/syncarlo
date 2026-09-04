"""Python-aware English NLU.

Intent comes from the *catalog* (function name, module, signature, docstring),
not from a hand-written example per sentence.

English contributes: stemming, prepositional roles, a few control constructions
(if / for / return / set) that are syntax, not libraries.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from syncarlo.catalog import ApiEntry, build_catalog
from syncarlo.english import CONTROL_PREFIXES, FUNCTION_WORDS, stem, stems, tokenize
from syncarlo.extract import PATHISH, QUOTED, Entity, extract_entities


ENTITY_MARK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def catalog_tokens(entry: ApiEntry) -> list[str]:
    """Retrieval document: how the object is named in Python + its docstring.

    Parameter names are *not* indexed here. They are used later for slot filling
    so that the word 'handle' does not retrieve os.get_handle_inheritable.
    """
    bits = [entry.name.replace("_", " "), entry.module or "", entry.docstring or ""]
    bits.extend(entry.synonyms)
    text = " ".join(bits).replace(".", " ")
    return stems(text)


@dataclass
class Example:
    text: str
    intent: str
    entities: list[Entity] = field(default_factory=list)


@dataclass
class ParseResult:
    intent: str
    confidence: float
    ranking: list[tuple[str, float]]
    entities: list[Entity]
    entry: ApiEntry | None


class IntentClassifier:
    def __init__(self) -> None:
        self.priors: dict[str, float] = {}
        self.cond: dict[str, dict[str, float]] = {}
        self.vocab: set[str] = set()
        self.intents: list[str] = []
        self.smoothing = 1.0

    def fit(self, examples: list[Example]) -> None:
        by_intent: dict[str, list[Example]] = defaultdict(list)
        for ex in examples:
            by_intent[ex.intent].append(ex)
        self.intents = sorted(by_intent)
        n = max(1, len(examples))
        counts: dict[str, Counter[str]] = {}
        for intent, exs in by_intent.items():
            self.priors[intent] = math.log(len(exs) / n)
            c: Counter[str] = Counter()
            for ex in exs:
                c.update(stems(strip_entity_markup(ex.text)))
            counts[intent] = c
            self.vocab.update(c)
        v = max(1, len(self.vocab))
        self.cond = {}
        for intent, c in counts.items():
            total = sum(c.values()) + self.smoothing * v
            self.cond[intent] = {t: math.log((c[t] + self.smoothing) / total) for t in self.vocab}

    def predict_proba(self, text: str, k: int = 8) -> list[tuple[str, float]]:
        f = Counter(stems(text))
        scores: list[tuple[str, float]] = []
        unk = math.log(self.smoothing / (self.smoothing * max(1, len(self.vocab))))
        for intent in self.intents:
            s = self.priors.get(intent, -20.0)
            table = self.cond.get(intent, {})
            for tok, cnt in f.items():
                s += cnt * table.get(tok, unk)
            scores.append((intent, s))
        scores.sort(key=lambda x: x[1], reverse=True)
        mx = scores[0][1] if scores else 0.0
        exps = [(i, math.exp(sc - mx)) for i, sc in scores]
        z = sum(e for _, e in exps) or 1.0
        return [(i, e / z) for i, e in exps[:k]]


def strip_entity_markup(text: str) -> str:
    return ENTITY_MARK.sub(r"\1", text)


def parse_rasa_example(line: str, intent: str) -> Example:
    entities: list[Entity] = []
    out = []
    i = 0
    for m in ENTITY_MARK.finditer(line):
        out.append(line[i : m.start()])
        start = sum(len(p) for p in out)
        val = m.group(1)
        out.append(val)
        entities.append(Entity(m.group(2), val, start, start + len(val), source="train"))
        i = m.end()
    out.append(line[i:])
    return Example("".join(out), intent, entities)


def load_rasa_yaml(path: str | Path) -> list[Example]:
    """Optional extra data. The system must work with none of this."""
    text = Path(path).read_text(encoding="utf-8")
    examples: list[Example] = []
    intent: str | None = None
    in_examples = False
    for raw in text.splitlines():
        line = raw.rstrip()
        m = re.match(r"^\s*-\s*intent:\s*(\S+)\s*$", line)
        if m:
            intent = m.group(1)
            in_examples = False
            continue
        if re.match(r"^\s*examples:\s*\|?\s*$", line):
            in_examples = True
            continue
        if in_examples and intent:
            em = re.match(r"^\s*-\s+(.+)$", line)
            if em:
                examples.append(parse_rasa_example(em.group(1).strip(), intent))
            elif line.strip() and not line.strip().startswith("-"):
                in_examples = False
    return examples


def synthesize_examples(catalog: list[ApiEntry]) -> list[Example]:
    """Distant supervision from Python itself: name + docstring, no user sentences."""
    out: list[Example] = []
    for e in catalog:
        first = (e.docstring or "").split(".")[0].strip()
        if first:
            out.append(Example(first, e.qname))
        out.append(Example(e.name.replace("_", " "), e.qname))
        out.append(Example(e.qname.replace(".", " ").replace("_", " "), e.qname))
    return out


class NLU:
    def __init__(self, catalog: list[ApiEntry] | None = None) -> None:
        self.catalog = catalog or build_catalog()
        self.by_qname = {e.qname: e for e in self.catalog}
        self.clf = IntentClassifier()
        self._docs: list[tuple[ApiEntry, Counter[str], int]] = []
        self._name_stems: dict[str, set[str]] = {}
        self._modules: set[str] = set()
        self._build_index()
        self.symbols: dict[str, list[str]] = {}

    def _build_index(self) -> None:
        docs = []
        df: Counter[str] = Counter()
        for e in self.catalog:
            toks = catalog_tokens(e)
            c = Counter(toks)
            docs.append((e, c, sum(c.values()) or 1))
            df.update(c.keys())
            self._name_stems[e.qname] = set(stems(e.name.replace("_", " ")))
            if e.module:
                self._modules.add(e.module.split(".")[0].lower())
        self._docs = docs
        self._df = df
        self._n = len(docs)
        self._avgdl = sum(dl for _, _, dl in docs) / max(1, self._n)
        self._k1, self._b = 1.6, 0.75

    def bm25(self, query: str, k: int = 8) -> list[tuple[ApiEntry, float]]:
        stripped = PATHISH.sub(" ", QUOTED.sub(" ", query))
        q = stems(stripped)
        qset = set(q)
        scored = []
        for e, c, dl in self._docs:
            s = 0.0
            for t in q:
                if t not in c:
                    continue
                idf = math.log((self._n - self._df[t] + 0.5) / (self._df[t] + 0.5) + 1)
                tf = c[t]
                s += idf * (tf * (self._k1 + 1)) / (tf + self._k1 * (1 - self._b + self._b * dl / self._avgdl))
            # Python: exact function/module token in the sentence is strong evidence
            verb = next((t for t in q if t not in FUNCTION_WORDS), "")
            if verb and (stem(e.name) == verb or e.name.lower() == verb):
                s += 3.5
            # English "open a file" is builtins.open, not POSIX os.open
            if verb == "open" and "file" in qset:
                if e.qname == "builtins.open":
                    s += 2.0
                elif e.qname == "os.open":
                    s -= 1.5
            extra = [stem(p) for p in e.name.split("_") if p]
            unused = [p for p in extra if p not in qset and p != verb]
            s -= 1.2 * len(unused)
            name_hit = self._name_stems.get(e.qname, set()) & qset
            if name_hit:
                s += 2.5 * len(name_hit)
            mod = (e.module or "").split(".")[0].lower()
            if mod and mod in qset:
                s += 1.8
            if s > 0:
                scored.append((e, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def fit(self, extra: list[Example] | None = None) -> None:
        data = synthesize_examples(self.catalog)
        if extra:
            data.extend(extra)
        self.clf.fit(data)

    def parse(self, text: str) -> ParseResult:
        grammar_hit = None
        low = text.lower()
        for pat, intent in CONTROL_PREFIXES:
            if re.match(pat, low):
                grammar_hit = intent
                break

        ranking = self.clf.predict_proba(text)
        bm = self.bm25(text)
        fused: dict[str, float] = {}
        for i, (intent, p) in enumerate(ranking):
            fused[intent] = fused.get(intent, 0) + p * 0.35 + 0.02 / (i + 1)
        mx = bm[0][1] if bm else 1.0
        for i, (e, s) in enumerate(bm):
            fused[e.qname] = fused.get(e.qname, 0) + 0.65 * (s / mx) + 0.04 / (i + 1)

        if grammar_hit:
            fused[grammar_hit] = fused.get(grammar_hit, 0) + 4.0

        # User-defined Python names in the spec beat random stdlib hits
        for tok in tokenize(text):
            if tok in self.symbols and tok not in {"if", "for", "return"}:
                fused[f"sym.{tok}"] = fused.get(f"sym.{tok}", 0) + 1.2

        ents = extract_entities(text)
        fileish = any(
            e.label == "path"
            or (e.role in {"source", "goal"} and e.value.lower() in {"handle", "file", "fp", "path"})
            for e in ents
        )
        if fileish:
            for qn, sc in list(fused.items()):
                e = self.by_qname.get(qn)
                if not e:
                    continue
                pnames = [p.name.lower() for p in e.params]
                if "fp" in pnames or "file" in pnames:
                    fused[qn] = sc + 0.6
                if e.name.endswith("s") and e.name[:-1] in {x.name for x in self.catalog}:
                    fused[qn] = sc - 0.5

        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)
        intent = ranked[0][0] if ranked else "unknown"
        z = sum(v for _, v in ranked) or 1.0
        conf = (ranked[0][1] / z) if ranked else 0.0
        entry = self.by_qname.get(intent)
        return ParseResult(
            intent=intent,
            confidence=conf,
            ranking=[(i, s / z) for i, s in ranked[:8]],
            entities=extract_entities(text),
            entry=entry,
        )
