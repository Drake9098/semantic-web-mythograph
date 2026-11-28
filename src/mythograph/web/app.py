"""API web di MythoGraph (uvicorn mythograph.web.app:app)."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rdflib import BNode, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from ..namespaces import DBR, EXTERNAL_NS, GEO, GRAPH, MYTH, OUTPUT_FILE, RES, WD
from ..store import Store

STATIC = Path(__file__).parent / "static"
LEVELS = ("rules", "owlrl")
LEVEL_LABELS = {
    "asserted": "asserita dalla fonte",
    "shared": "entità condivisa",
    "rules": "dedotta da regola CONSTRUCT (RDFS/OWL)",
    "owlrl": "dedotta da OWL 2 RL (owlrl)",
}

# archi disegnati (le inverse no, sarebbero doppi)
EDGE_PROPS = {
    MYTH.hasFather: "family", MYTH.hasMother: "family", MYTH.hasParent: "family",
    MYTH.hasChild: "family", MYTH.hasSpouse: "spouse", MYTH.killed: "killed",
    MYTH.hasAgent: "event", MYTH.hasPatient: "event", MYTH.hasParticipant: "event",
    MYTH.setIn: "place", MYTH.bornIn: "place", MYTH.diedIn: "place", MYTH.rulesOver: "place",
}
SYMMETRIC = {MYTH.hasSpouse}

# categoria (colore) del nodo, in ordine di priorità
CATEGORIES = [
    (MYTH.Demigod, "demigod"), (MYTH.Primordial, "primordial"), (MYTH.Titan, "titan"),
    (MYTH.Olympian, "olympian"), (MYTH.MinorDeity, "minor"), (MYTH.Deity, "deity"),
    (MYTH.Hero, "hero"), (MYTH.Human, "human"), (MYTH.Cyclops, "monster"),
    (MYTH.Monster, "monster"), (MYTH.Creature, "creature"), (MYTH.Event, "event"),
    (MYTH.RealPlace, "place"), (MYTH.MythicalPlace, "mythplace"),
]

store = Store(OUTPUT_FILE)
app = FastAPI(title="MythoGraph")


def _covered_by_inverse() -> set[URIRef]:
    """Proprietà già visibili dall'altro lato grazie a inversa o simmetria."""
    tbox = store.graph("ontology")
    base = set(tbox.subjects(RDF.type, OWL.SymmetricProperty))
    for a, b in tbox.subject_objects(OWL.inverseOf):
        base |= {a, b}
    covered = set(base)
    for p in base:
        covered |= set(tbox.transitive_subjects(RDFS.subPropertyOf, p))
    return covered


COVERED_BY_INVERSE = _covered_by_inverse()

# nel grafo i nomi romani diventano greci (Venere -> Afrodite)
ROMAN_TO_GREEK = {s: o for s, o in store.graph("shared").subject_objects(MYTH.romanCounterpart)}


def canonical(node):
    return ROMAN_TO_GREEK.get(node, node)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ----------------------------------------------------------------- helpers
def local(node) -> str:
    return re.split(r"[#/]", str(node))[-1]


def node_json(node) -> dict:
    if isinstance(node, Literal):
        return {"literal": str(node), "lang": node.language, "datatype": local(node.datatype) if node.datatype else None}
    if isinstance(node, BNode):
        return {"bnode": str(node), "label": "(restrizione anonima)"}
    return {"iri": str(node), "id": local(node), "label": store.label(node),
            "internal": str(node).startswith(str(RES))}


def ancient_sources() -> list[str]:
    meta = store.graph("meta")
    return [s for s in store.sources if meta.value(GRAPH[s], MYTH.constrained) != Literal(False)]


def check_source(source: str) -> list[str]:
    if source == "all":                     # tutte le fonti antiche (Wikidata a parte)
        return ancient_sources()
    if source not in store.sources:
        raise HTTPException(404, f"Fonte sconosciuta: {source}")
    return [source]


def types_of(node, sources: list[str], inferred: bool = True) -> dict[URIRef, str]:
    """Tipi di un nodo con il livello che li ha prodotti (il più "basso")."""
    found: dict[URIRef, str] = {}
    for t in store.graph("shared").objects(node, RDF.type):
        found.setdefault(t, "shared")
    for src in sources:
        for t in store.graph(src).objects(node, RDF.type):
            found.setdefault(t, "asserted")
        for lvl in LEVELS if inferred else ():
            for t in store.graph(f"inferred/{src}/{lvl}").objects(node, RDF.type):
                found.setdefault(t, lvl)
    return {t: lvl for t, lvl in found.items()
            if isinstance(t, URIRef) and str(t).startswith((str(MYTH), *EXTERNAL_NS))}


def category(types) -> str:
    for cls, cat in CATEGORIES:
        if cls in types:
            return cat
    return "other"


@lru_cache(maxsize=1)
def conflicts() -> list[dict]:
    _, rows = store.run_cq(2)
    out = []
    for r in rows:
        out.append({
            "character": node_json(r[0]), "property": node_json(r[1]),
            "value1": node_json(r[2]), "source1": local(r[3]),
            "value2": node_json(r[4]), "source2": local(r[5]), "kind": str(r[6]),
        })
    return out


# --------------------------------------------------------------------- API
@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/sources")
def sources():
    meta = store.graph("meta")
    out = []
    for name in [*store.sources, "merged-naive"]:
        gid = GRAPH[name]
        works = sorted(store.label(w) for w in store.graph("shared").subjects(MYTH.inSourceGraph, gid))
        def val(p):
            v = meta.value(gid, p)
            return v.toPython() if v is not None else None
        out.append({
            "name": name,
            "label": str(meta.value(gid, RDFS.label) or name),
            "constrained": val(MYTH.constrained),
            "internalConflicts": len(list(meta.subjects(MYTH.inGraph, gid))),
            "works": works,
            "asserted": val(MYTH.assertedTriples),
            "inferred": {lvl: val(MYTH[f"inferredBy_{lvl}"]) for lvl in LEVELS},
            "consistentOWLRL": val(MYTH.consistentOWLRL),
            "errors": [str(e) for e in meta.objects(gid, MYTH.owlrlError)],
        })
    return out


@app.get("/api/graph")
def graph(source: str = "all", inferred: bool = True, events: bool = False, places: bool = False):
    srcs = check_source(source)
    edges: dict[tuple, dict] = {}
    nodes: set[URIRef] = set()

    def add(s, p, o, src, level):
        kind = EDGE_PROPS.get(p)
        if kind is None or not isinstance(o, URIRef):
            return
        if kind == "event" and not events:
            return
        if kind == "place" and not places:
            return
        s, o = canonical(s), canonical(o)
        if p == MYTH.hasChild:              # disegnato come genitore, nel verso del figlio
            s, o, p = o, s, MYTH.hasParent
        if s == o:
            return
        if p in SYMMETRIC and str(o) < str(s):
            s, o = o, s
        key = (s, p, o, src)
        if key in edges:
            return
        edges[key] = {"source": local(s), "target": local(o), "prop": local(p),
                      "label": store.label(p), "kind": kind, "graph": src, "level": level}
        nodes.update((s, o))

    for src in srcs:
        for s, p, o in store.graph(src):
            add(s, p, o, src, "asserted")
        if inferred:
            for lvl in LEVELS:
                for s, p, o in store.graph(f"inferred/{src}/{lvl}"):
                    add(s, p, o, src, lvl)

    # Archi genitore: se esiste hasFather/hasMother non disegnare anche hasParent.
    specific = {(e["source"], e["target"], e["graph"]) for e in edges.values() if e["prop"] in ("hasFather", "hasMother")}
    edge_list = [e for e in edges.values()
                 if not (e["prop"] == "hasParent" and (e["source"], e["target"], e["graph"]) in specific)]

    contested = {(c["character"]["id"], c["property"]["id"]) for c in conflicts()}
    for e in edge_list:
        e["contested"] = (e["source"], e["prop"]) in contested
        e["id"] = f'{e["source"]}|{e["prop"]}|{e["target"]}|{e["graph"]}'

    node_list = []
    for n in nodes:
        ts = types_of(n, srcs, inferred)
        node_list.append({"id": local(n), "label": store.label(n), "category": category(ts),
                          "inferredCategory": ts.get(next((c for c, _ in CATEGORIES if c in ts), None)) in LEVELS})
    return {"nodes": node_list, "edges": edge_list}


@app.get("/api/entity/{ident}")
def entity(ident: str, source: str = "all"):
    node = RES[ident]
    srcs = check_source(source)
    labels = store.all_labels(node)
    if not labels:
        raise HTTPException(404, f"Entità sconosciuta: {ident}")
    ts = types_of(node, srcs)
    types = [{"class": node_json(t), "level": lvl, "levelLabel": LEVEL_LABELS[lvl]}
             for t, lvl in sorted(ts.items(), key=lambda kv: store.label(kv[0]))]

    def facts(gname, level, src):
        g = store.graph(gname)
        out = []
        for p, o in g.predicate_objects(node):
            if p == RDF.type or not str(p).startswith(str(MYTH)) or canonical(o) == canonical(node):
                continue
            out.append({"dir": "out", "prop": node_json(p), "value": node_json(o), "source": src, "level": level})
        for s, p in g.subject_predicates(node):
            if not str(p).startswith(str(MYTH)) or isinstance(s, BNode) or p in COVERED_BY_INVERSE:
                continue
            out.append({"dir": "in", "prop": node_json(p), "value": node_json(s), "source": src, "level": level})
        return out

    all_facts = facts("shared", "shared", "shared")
    for src in srcs:
        all_facts += facts(src, "asserted", src)
        for lvl in LEVELS:
            all_facts += facts(f"inferred/{src}/{lvl}", lvl, src)

    # Attestazioni reificate che riguardano l'entità.
    attest = []
    for src in srcs:
        g = store.graph(src)
        for st in g.subjects(RDF.type, RDF.Statement):
            if node not in (g.value(st, RDF.subject), g.value(st, RDF.object)):
                continue
            passage = g.value(st, MYTH.attestedIn)
            attest.append({
                "source": src,
                "subject": node_json(g.value(st, RDF.subject)),
                "predicate": node_json(g.value(st, RDF.predicate)),
                "object": node_json(g.value(st, RDF.object)),
                "passage": store.label(passage) if passage else None,
                "note": str(g.value(st, MYTH.versionNote) or "") or None,
            })
    links_g = store.graph("links")
    external = {
        "wikidata": next((str(o) for o in links_g.objects(node, OWL.sameAs) if str(o).startswith(str(WD))), None),
        "dbpedia": next((str(o) for o in links_g.objects(node, OWL.sameAs) if str(o).startswith(str(DBR))), None),
        "wikipedia": next((str(o) for o in links_g.objects(node, RDFS.seeAlso)), None),
        "lat": (v.toPython() if (v := store.graph("shared").value(node, GEO.lat)) is not None else None),
        "long": (v.toPython() if (v := store.graph("shared").value(node, GEO.long)) is not None else None),
    }
    roman = [node_json(r) for r, g in ROMAN_TO_GREEK.items() if g == node]
    greek = node_json(ROMAN_TO_GREEK[node]) if node in ROMAN_TO_GREEK else None
    comments = [str(o) for gname in ("shared", *srcs) for o in store.graph(gname).objects(node, RDFS.comment)]
    notes = [str(o) for gname in ("shared", *srcs) for o in store.graph(gname).objects(node, MYTH.versionNote)]
    return {"id": ident, "iri": str(node), "labels": labels, "label": store.label(node),
            "types": types, "category": category(ts), "facts": all_facts,
            "attestations": attest, "comments": comments + notes,
            "external": external, "romanNames": roman, "greekName": greek,
            "conflicts": [c for c in conflicts() if c["character"]["id"] == ident]}


@app.get("/api/search")
def search(q: str = Query(min_length=1)):
    ql = q.lower()
    hits = []
    for node, labels in store._labels.items():
        if not str(node).startswith(str(RES)):
            continue
        if any(ql in v.lower() for v in labels.values()):
            hits.append({"id": local(node), "label": store.label(node), "category": category(types_of(node, store.sources))})
    hits.sort(key=lambda h: (not h["label"].lower().startswith(ql), h["label"]))
    return hits[:20]


@app.get("/api/conflicts")
def api_conflicts():
    return conflicts()


@app.get("/api/cq")
def cq_list():
    return [{"number": cq.number, "title": cq.title, "comment": cq.comment, "query": cq.query,
             "target": node_json(cq.default_target) if cq.default_target else None}
            for cq in store.cqs.values()]


@lru_cache(maxsize=128)
def _run_cq(n: int, target: str | None):
    cols, rows = store.run_cq(n, RES[target] if target else None)
    return {"columns": cols, "rows": [[node_json(c) if c is not None else None for c in r] for r in rows]}


@app.get("/api/cq/{n}")
def cq_run(n: int, target: str | None = None):
    if n not in store.cqs:
        raise HTTPException(404, "CQ inesistente")
    return _run_cq(n, target)


class SparqlRequest(BaseModel):
    query: str


_FORBIDDEN = re.compile(r"\b(INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD)\b", re.I)


@app.post("/api/sparql")
def sparql(req: SparqlRequest):
    """Editor SPARQL in sola lettura (SELECT / ASK / CONSTRUCT / DESCRIBE)."""
    if _FORBIDDEN.search(re.sub(r"<[^>]*>|\"[^\"]*\"|#[^\n]*", "", req.query)):
        raise HTTPException(400, "Sono ammesse solo query di lettura.")
    try:
        res = store.query(req.query)
    except Exception as exc:  # errore di sintassi o di valutazione
        raise HTTPException(400, f"Errore nella query: {exc}") from exc
    if res.type == "ASK":
        return {"type": "ASK", "boolean": bool(res.askAnswer)}
    if res.type in ("CONSTRUCT", "DESCRIBE"):
        triples = [[node_json(x) for x in t] for t in list(res)[:1000]]
        return {"type": res.type, "columns": ["s", "p", "o"], "rows": triples}
    rows = [[node_json(c) if c is not None else None for c in r] for r in list(res)[:1000]]
    return {"type": "SELECT", "columns": [str(v) for v in res.vars], "rows": rows}


def _coords(place, seen=None):
    """Coordinate del luogo, o del luogo che lo contiene / con cui è identificato."""
    seen = seen or set()
    shared = store.graph("shared")
    lat, lon = shared.value(place, GEO.lat), shared.value(place, GEO.long)
    if lat is not None and lon is not None:
        return float(lat), float(lon), place
    seen.add(place)
    for nxt in [*shared.objects(place, MYTH.identifiedWith), *shared.objects(place, MYTH.locatedIn)]:
        if nxt not in seen and (found := _coords(nxt, seen)):
            return found
    return None


@app.get("/api/places")
def places(source: str = "all"):
    """Luoghi con coordinate (da Wikidata) e i personaggi nati, morti o regnanti lì."""
    srcs = check_source(source)
    out: dict[str, dict] = {}
    for src in srcs:
        view = store.graph(f"view/{src}")
        pairs = [(c, pl) for p in (MYTH.bornIn, MYTH.diedIn, MYTH.residesIn, MYTH.rulesOver)
                 for c, pl in view.subject_objects(p)]
        for event, place in pairs:
            if canonical(event) != event:
                continue
            found = _coords(place)
            if not found:
                continue
            lat, lon, anchor = found
            entry = out.setdefault(local(anchor), {"id": local(anchor), "label": store.label(anchor),
                                                   "lat": lat, "long": lon, "events": []})
            entry["events"].append({"id": local(event), "label": store.label(event), "source": src,
                                    "place": store.label(place), "approx": anchor != place})
    # anche i luoghi reali senza eventi, per mostrare la geografia del dataset
    for place in set(store.graph("shared").subjects(GEO.lat, None)):
        found = _coords(place)
        if found and found[2] == place and local(place) not in out:
            out[local(place)] = {"id": local(place), "label": store.label(place),
                                 "lat": found[0], "long": found[1], "events": []}
    return sorted(out.values(), key=lambda p: -len(p["events"]))
