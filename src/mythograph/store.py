"""Accesso al grafo generato: caricamento, competency question, etichette."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDFS

from .namespaces import GRAPH, MYTH, OUTPUT_FILE, QUERIES_DIR, RES, SKOS

CQ_DEFAULTS = {
    1: RES.Aphrodite, 3: RES.Heracles, 5: RES.Heracles, 6: RES.Sicily,
}


@dataclass
class CompetencyQuestion:
    number: int
    file: str
    title: str
    comment: str
    query: str
    default_target: URIRef | None


def load_cqs() -> dict[int, CompetencyQuestion]:
    out = {}
    for f in sorted(QUERIES_DIR.glob("cq*.rq")):
        n = int(re.match(r"cq(\d+)", f.stem).group(1))
        text = f.read_text(encoding="utf-8")
        comments = [l[1:].strip() for l in text.splitlines() if l.startswith("#")]
        title = re.sub(r"^CQ\d+\s*[—-]\s*", "", comments[0]) if comments else f.stem
        out[n] = CompetencyQuestion(n, f.name, title, "\n".join(comments[1:]), text, CQ_DEFAULTS.get(n))
    return out


class Store:
    def __init__(self, path=OUTPUT_FILE):
        self.ds = Dataset()
        self.ds.parse(path, format="trig")
        self.cqs = load_cqs()

    # ------------------------------------------------------------------ fonti
    @cached_property
    def sources(self) -> list[str]:
        meta = self.ds.graph(GRAPH["meta"])
        names = [str(s).removeprefix(str(GRAPH)) for s in meta.subjects(None, MYTH.SourceGraph)]
        return sorted(names)

    def graph(self, name: str):
        return self.ds.graph(GRAPH[name])

    # -------------------------------------------------------------- etichette
    @cached_property
    def _labels(self) -> dict[URIRef, dict[str, str]]:
        labels: dict[URIRef, dict[str, str]] = {}
        for gname in ("ontology", "alignments", "shared", *self.sources):
            g = self.graph(gname)
            for prop in (RDFS.label, SKOS.prefLabel):
                for s, o in g.subject_objects(prop):
                    if isinstance(o, Literal):
                        labels.setdefault(s, {}).setdefault(o.language or "", str(o))
        return labels

    def label(self, node, lang: str = "it") -> str:
        if not isinstance(node, URIRef):
            return str(node)
        d = self._labels.get(node, {})
        for l in (lang, "en", "", "grc", "la"):
            if l in d:
                return d[l]
        s = str(node)
        return re.split(r"[#/]", s)[-1]

    def all_labels(self, node) -> dict[str, str]:
        return dict(self._labels.get(node, {}))

    # ------------------------------------------------------------------ query
    def query(self, sparql: str, bindings: dict | None = None):
        return self.ds.query(sparql, initBindings=bindings or {})

    def run_cq(self, n: int, target: URIRef | None = None) -> tuple[list[str], list[list]]:
        cq = self.cqs[n]
        bindings = {}
        tgt = target or cq.default_target
        if tgt is not None and "?target" in cq.query:
            bindings["target"] = tgt
        res = self.query(cq.query, bindings)
        cols = [str(v) for v in res.vars]
        return cols, [list(row) for row in res]
