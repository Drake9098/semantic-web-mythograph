"""Pipeline, passo 4: ragionamento e output (python -m mythograph.build).

Per ogni named graph prodotto dal mapping:
  - fonti antiche (g:hesiod, g:homer...): core + regole + vincoli per fonte + AllDifferent;
  - g:wikidata (tutte le versioni insieme): core + regole, senza i vincoli per fonte.
Poi la "fusione ingenua": Wikidata con i vincoli di una fonte sola, che deve risultare
inconsistente. Scrive data/generated/mythograph.trig e i file per Protégé in exports/.
"""
from __future__ import annotations

import re
import sys
import time

from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.collection import Collection
from rdflib.namespace import OWL, RDF, RDFS, XSD

from .namespaces import (ALIGNMENTS_FILE, CONSTRAINTS_FILE, EXPORTS_DIR, GRAPH, LINKS_FILE, MYTH,
                         ONTOLOGY_FILE, OUTPUT_FILE, PREFIXES, RES, SHARED_FILE, SOURCES_DIR, SWRL_FILE)
from .reasoning import apply_hermit, apply_owlrl, apply_rules, reason

LEVELS = ("rules", "owlrl", "hermit")
LABELS = {"hesiod": "Esiodo", "homer": "Omero", "apollodorus": "Apollodoro", "pausanias": "Pausania",
          "diodorus": "Diodoro Siculo", "herodotus": "Erodoto", "hyginus": "Igino",
          "apollonius": "Apollonio Rodio", "wikidata": "Wikidata (tutte le versioni)"}
ALL_VERSIONS = "wikidata"


def local(node) -> str:
    return str(node).rsplit("/", 1)[-1].rsplit("#", 1)[-1]


def load(path) -> Graph:
    return Graph().parse(path, format="turtle")


def characters_in(src: Graph, shared: Graph) -> list[URIRef]:
    nodes = set(src.subjects()) | set(src.objects())
    return sorted(n for n in nodes if (n, RDF.type, MYTH.Character) in shared)


def all_different(chars: list[URIRef]) -> Graph:
    """owl:AllDifferent: in OWL due nomi diversi possono indicare lo stesso individuo."""
    g = Graph()
    node, lst = BNode("allDifferent"), BNode("allDifferentList")
    g.add((node, RDF.type, OWL.AllDifferent))
    g.add((node, OWL.distinctMembers, lst))
    Collection(g, lst, chars)
    return g


def shared_for(src: Graph, shared: Graph) -> Graph:
    """La parte di shared che riguarda le entità nominate dalla fonte (più un passo)."""
    nodes = set(src.subjects()) | set(src.objects())
    nodes |= {o for n in list(nodes) for o in shared.objects(n, None) if isinstance(o, URIRef)}
    out = Graph()
    for n in nodes:
        for p, o in shared.predicate_objects(n):
            out.add((n, p, o))
    return out


CONFLICTS_QUERY = """
PREFIX myth: <https://example.org/mythograph/ontology#>
SELECT DISTINCT ?x ?p ?a ?b WHERE {
  VALUES ?p { myth:hasFather myth:hasMother }
  ?x ?p ?a , ?b .
  FILTER(STR(?a) < STR(?b))
}"""
KINSHIP = {MYTH.hasFather, MYTH.hasMother, MYTH.hasParent, MYTH.hasChild}


def internal_conflicts(src: Graph, base: Graph):
    """Una fonte che dà due padri (o due madri) allo stesso personaggio si contraddice da sola.

    Le affermazioni coinvolte vanno nel grafo conflicts/<fonte>: si segnalano ma non si
    usano per ragionare, altrimenti la fonte intera sarebbe inconsistente.
    """
    closure = base + apply_rules(base)
    rows = list(closure.query(CONFLICTS_QUERY))
    bad = {(x, v) for x, _p, a, b in rows for v in (a, b)}
    conflicts = Graph()
    for s, p, o in src:
        if p in KINSHIP and ((s, o) in bad or (o, s) in bad):
            conflicts.add((s, p, o))
    return conflicts, rows


def export_protege(name: str, label: str, graph: Graph) -> None:
    """Un file unico per fonte, da aprire in Protégé: TBox, regole, individui, senza inferenze.

    Le inferenze le calcola HermiT dentro Protégé (Reasoner > Start reasoner).
    """
    g = Graph()
    for prefix, ns in PREFIXES.items():
        g.bind(prefix, ns)
    g.bind("swrl", "http://www.w3.org/2003/11/swrl#")
    for t in graph:
        if t[1] == OWL.imports or (t[1] == RDF.type and t[2] == OWL.Ontology):
            continue
        g.add(t)
    onto = URIRef(f"https://example.org/mythograph/data/{name}")
    g.add((onto, RDF.type, OWL.Ontology))
    g.add((onto, RDFS.label, Literal(f"MythoGraph - {label}", lang="it")))
    g.add((onto, RDFS.comment, Literal(
        "Generato dalla build: ontologia (core, regole SWRL, allineamenti) più gli individui "
        "di questo grafo. Avviare HermiT per vedere le deduzioni.", lang="it")))
    EXPORTS_DIR.mkdir(exist_ok=True)
    (EXPORTS_DIR / f"mythograph-{name}.ttl").write_text(
        "# Generato da `python -m mythograph.build`. Da aprire in Protégé.\n"
        + g.serialize(format="turtle"), encoding="utf-8")


def build(verbose: bool = True) -> Dataset:
    t0 = time.time()
    log = print if verbose else (lambda *a, **k: None)

    core, swrl, alignments = load(ONTOLOGY_FILE), load(SWRL_FILE), load(ALIGNMENTS_FILE)
    constraints = load(CONSTRAINTS_FILE)
    links = load(LINKS_FILE) if LINKS_FILE.exists() else Graph()
    shared = load(SHARED_FILE)
    sources = {f.stem: load(f) for f in sorted(SOURCES_DIR.glob("*.ttl"))}
    log(f"TBox: {len(core)} triple + {len(swrl)} SWRL + {len(constraints)} vincoli | "
        f"shared: {len(shared)} | grafi: {', '.join(f'{k} {len(v)}' for k, v in sources.items())}")

    ds = Dataset()
    for prefix, ns in PREFIXES.items():
        ds.bind(prefix, ns)
    ds.bind("owl", OWL)

    def put(name: str, g: Graph):
        target = ds.graph(GRAPH[name])
        target += g
        return target

    put("ontology", core)
    put("rules", swrl)
    put("constraints", constraints)
    put("alignments", alignments)
    put("shared", shared)
    put("links", links)
    tbox = core + swrl + alignments
    meta = ds.graph(GRAPH["meta"])

    def record(name: str, r, label: str):
        gid = GRAPH[name]
        meta.add((gid, RDFS.label, Literal(label, lang="it")))
        if r.owlrl.consistent is not None:
            meta.add((gid, MYTH.consistentOWLRL, Literal(r.owlrl.consistent)))
        for e in r.owlrl.errors[:20]:
            meta.add((gid, MYTH.owlrlError, Literal(e)))
        if r.hermit.available:
            meta.add((gid, MYTH.consistentHermiT, Literal(bool(r.hermit.consistent))))
        meta.add((gid, MYTH.reasonerNote, Literal(r.hermit.message, lang="it")))

    # le fonti antiche prima, g:wikidata per ultimo (è il più grande)
    order = sorted(sources, key=lambda n: (n == ALL_VERSIONS, n))
    cleaned = dict(sources)

    def conflict(name, x, text, prop=None, values=()):
        c = BNode()
        meta.add((c, RDF.type, MYTH.InternalConflict))
        meta.add((c, MYTH.inGraph, GRAPH[name]))
        meta.add((c, MYTH.about, x))
        meta.add((c, MYTH.reason, Literal(text)))
        if prop is not None:
            meta.add((c, MYTH.onProperty, prop))
        for v in values:
            meta.add((c, MYTH.conflictingValue, v))
    for name in order:
        src = sources[name]
        put(name, src)
        constrained = name != ALL_VERSIONS

        def make_base(src):
            if not constrained:
                return shared, tbox + shared + src
            common = shared_for(src, shared)
            return common, tbox + constraints + common + all_different(characters_in(src, shared)) + src

        quarantine = Graph()
        if constrained:
            common, base = make_base(src)
            quarantine, rows = internal_conflicts(src, base)
            for x, p, a, b in rows:
                conflict(name, x, f"{local(p)}: {local(a)} / {local(b)}", p, (a, b))
            if rows:
                log(f"[{name}] si contraddice da sola: " + "; ".join(
                    f"{local(x)} {local(p)} {local(a)} / {local(b)}" for x, p, a, b in rows))
            src = src - quarantine

        # se resta incoerente: isolo le affermazioni sui personaggi citati negli errori.
        # HermiT controlla la coerenza in un attimo; owlrl serve a trovare i colpevoli.
        for _attempt in range(5):
            common, base = make_base(src)
            if apply_hermit(base, infer=False).consistent is not False:
                break
            errors = apply_owlrl(base).errors
            bad = {URIRef(m) for e in errors for m in re.findall(rf"{re.escape(str(RES))}[^\s,]+", e)}
            moved = Graph()
            for t in src:
                if t[0] in bad or t[2] in bad:
                    moved.add(t)
            if not len(moved):
                log(f"[{name}] incoerente, ma non trovo le affermazioni da isolare")
                break
            for x in sorted(bad):
                conflict(name, x, next(e for e in errors if str(x) in e))
            log(f"[{name}] incoerente, isolo: {', '.join(local(x) for x in sorted(bad))}")
            quarantine += moved
            src = src - moved
        r = reason(base)
        if len(quarantine):
            put(f"conflicts/{name}", quarantine)
        cleaned[name] = src
        export_protege(name, LABELS.get(name, name), base)
        view = common + src
        for level, g in zip(LEVELS, (r.rules, r.owlrl.inferred, r.hermit.inferred)):
            put(f"inferred/{name}/{level}", g)
            meta.add((GRAPH[name], MYTH[f"inferredBy_{level}"], Literal(len(g), datatype=XSD.integer)))
            meta.add((GRAPH[f"inferred/{name}/{level}"], MYTH.inferredFor, GRAPH[name]))
            meta.add((GRAPH[f"inferred/{name}/{level}"], MYTH.level, Literal(level)))
            view += g
        put(f"view/{name}", view)
        if len(r.hermit.tbox):              # sottoclassi dedotte da HermiT (Parricide ⊑ Kinslayer)
            put(f"inferred/{name}/tbox", r.hermit.tbox)
        meta.add((GRAPH[f"view/{name}"], MYTH.viewOf, GRAPH[name]))
        meta.add((GRAPH[name], RDF.type, MYTH.SourceGraph))
        meta.add((GRAPH[name], MYTH.assertedTriples, Literal(len(src), datatype=XSD.integer)))
        meta.add((GRAPH[name], MYTH.constrained, Literal(name != ALL_VERSIONS)))
        record(name, r, LABELS.get(name, name))
        log(f"[{name}] asserite {len(src)} | rules +{len(r.rules)} | owlrl +{len(r.owlrl.inferred)} "
            f"(consistente={r.owlrl.consistent}) | {r.hermit.message} +{len(r.hermit.inferred)}  "
            f"[{time.time() - t0:.0f}s]")

    # fusione ingenua: le fonti antiche insieme, con i vincoli di una fonte sola
    merged_src = Graph()
    for name, src in cleaned.items():
        if name != ALL_VERSIONS:
            merged_src += src
    merged = tbox + constraints + shared_for(merged_src, shared) + merged_src
    merged += all_different(characters_in(merged_src, shared))
    export_protege("merged-naive", "fusione ingenua delle fonti antiche (inconsistente)", merged)
    r = reason(merged)
    meta.add((GRAPH["merged-naive"], RDF.type, MYTH.NaiveMerge))
    record("merged-naive", r, "Fusione ingenua delle fonti antiche")
    log(f"[merged-naive] owlrl consistente={r.owlrl.consistent} errori={len(r.owlrl.errors)} | {r.hermit.message}")
    for e in r.owlrl.errors[:5]:
        log("   -", e)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    ds.serialize(OUTPUT_FILE, format="trig")
    log(f"Scritto {OUTPUT_FILE} ({len(ds)} quad) in {time.time() - t0:.1f}s")
    return ds


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    build()
    sys.exit(0)
