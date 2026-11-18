"""Costruisce data/generated/mythograph.trig (python -m mythograph.build).

Ragiona su ogni fonte separatamente (TBox + shared + fonte) e una volta sulla
fusione di tutte le fonti, che deve risultare inconsistente.
"""
from __future__ import annotations

import sys
import time

from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

from .namespaces import (ALIGNMENTS_FILE, GRAPH, LINKS_FILE, MYTH, ONTOLOGY_FILE,
                         OUTPUT_FILE, PREFIXES, RES, SHARED_FILE, SOURCES_DIR)
from .reasoning import reason

LEVELS = ("rules", "owlrl", "hermit")


def load(path) -> Graph:
    return Graph().parse(path, format="turtle")


def unique_names(shared: Graph, tbox: Graph) -> Graph:
    """owl:AllDifferent sui personaggi (niente unique name assumption).

    Senza, nella fusione il reasoner dedurrebbe solo Zeus sameAs Urano.
    """
    g = Graph()
    full = tbox + shared
    char_classes = {c for c in full.transitive_subjects(RDFS.subClassOf, MYTH.Character)}
    # esclusi i nomi romani, che in Ovidio sono sameAs dei greci
    roman = set(shared.subjects(MYTH.romanCounterpart, None))
    chars = sorted({s for c in char_classes for s in shared.subjects(RDF.type, c)
                    if isinstance(s, URIRef) and s not in roman})
    node = BNode("allDifferentCharacters")
    lst = BNode("allDifferentList")
    g.add((node, RDF.type, OWL.AllDifferent))
    g.add((node, OWL.distinctMembers, lst))
    Collection(g, lst, chars)
    return g


def build(verbose: bool = True) -> Dataset:
    t0 = time.time()
    log = print if verbose else (lambda *a, **k: None)

    tbox = load(ONTOLOGY_FILE)
    alignments = load(ALIGNMENTS_FILE)
    # link a Wikidata/DBpedia: fuori dal ragionamento (copierebbe solo triple)
    links = load(LINKS_FILE) if LINKS_FILE.exists() else Graph()
    shared = load(SHARED_FILE)
    shared += unique_names(shared, tbox)
    sources = {f.stem: load(f) for f in sorted(SOURCES_DIR.glob("*.ttl"))}
    log(f"TBox: {len(tbox)} triple, shared: {len(shared)}, fonti: {', '.join(sources)}")

    ds = Dataset()
    for prefix, ns in PREFIXES.items():
        ds.bind(prefix, ns)
    ds.bind("owl", OWL)

    def put(name: str, g: Graph):
        target = ds.graph(GRAPH[name])
        target += g
        return target

    put("ontology", tbox)
    put("alignments", alignments)
    put("shared", shared)
    put("links", links)
    tbox = tbox + alignments        # da qui in poi la TBox include l'allineamento
    meta = ds.graph(GRAPH["meta"])

    def record(name: str, r, label: str):
        gid = GRAPH[name]
        meta.add((gid, RDFS.label, Literal(label, lang="it")))
        meta.add((gid, MYTH.consistentOWLRL, Literal(r.owlrl.consistent)))
        for e in r.owlrl.errors[:20]:
            meta.add((gid, MYTH.owlrlError, Literal(e)))
        if r.hermit.available:
            meta.add((gid, MYTH.consistentHermiT, Literal(bool(r.hermit.consistent))))
        meta.add((gid, MYTH.reasonerNote, Literal(r.hermit.message, lang="it")))

    for name, src in sources.items():
        put(name, src)
        base = tbox + shared + src
        r = reason(base)
        view = shared + src
        for level, g in zip(LEVELS, (r.rules, r.owlrl.inferred, r.hermit.inferred)):
            put(f"inferred/{name}/{level}", g)
            meta.add((GRAPH[name], MYTH[f"inferredBy_{level}"], Literal(len(g), datatype=XSD.integer)))
            meta.add((GRAPH[f"inferred/{name}/{level}"], MYTH.inferredFor, GRAPH[name]))
            meta.add((GRAPH[f"inferred/{name}/{level}"], MYTH.level, Literal(level)))
            view += g
        # vista completa della fonte, comoda per le query
        put(f"view/{name}", view)
        meta.add((GRAPH[f"view/{name}"], MYTH.viewOf, GRAPH[name]))
        meta.add((GRAPH[name], RDF.type, MYTH.SourceGraph))
        meta.add((GRAPH[name], MYTH.assertedTriples, Literal(len(src), datatype=XSD.integer)))
        record(name, r, f"Fonte: {name}")
        log(f"[{name}] asserite {len(src)} | rules +{len(r.rules)} | owlrl +{len(r.owlrl.inferred)} "
            f"(consistente={r.owlrl.consistent}) | {r.hermit.message} +{len(r.hermit.inferred)}")

    # fusione ingenua di tutte le fonti
    merged = tbox + shared
    for src in sources.values():
        merged += src
    r = reason(merged)
    meta.add((GRAPH["merged-naive"], RDF.type, MYTH.NaiveMerge))
    record("merged-naive", r, "Fusione ingenua di tutte le fonti")
    log(f"[merged-naive] owlrl consistente={r.owlrl.consistent} errori={len(r.owlrl.errors)} | {r.hermit.message}")
    for e in r.owlrl.errors[:5]:
        log("   -", e)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ds.serialize(OUTPUT_FILE, format="trig")
    log(f"Scritto {OUTPUT_FILE} ({len(ds)} quad) in {time.time() - t0:.1f}s")
    return ds


if __name__ == "__main__":
    build()
    sys.exit(0)
