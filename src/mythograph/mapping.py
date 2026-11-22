"""Pipeline, passo 3: mapping (python -m mythograph.mapping).

Esegue in ordine le CONSTRUCT di pipeline/mapping/ sul grafo grezzo di Wikidata
più le tabelle di corrispondenza, con rdflib (g += g.query(CONSTRUCT)).
La prima riga di ogni query dice dove va il risultato:

    # graph: work        resta nel grafo di lavoro, serve alle query successive;
                         la query si ripete finché aggiunge triple nuove
    # graph: shared      entità comuni a tutte le fonti   -> data/mapped/shared.ttl
    # graph: links       owl:sameAs verso Wikidata/DBpedia -> data/mapped/links.ttl
    # graph: per source  una volta per named graph        -> data/mapped/sources/<fonte>.ttl
"""
from __future__ import annotations

import sys
import time

from rdflib import BNode, Graph, Literal, Namespace, URIRef

from .lift import RAW_FILE
from .namespaces import GRAPH, MAP, MAPPED_DIR, PIPELINE_DIR, PREFIXES

SCHEMA = Namespace("http://schema.org/")

MAPPING_DIR = PIPELINE_DIR / "mapping"
SHARED_OUT = MAPPED_DIR / "shared.ttl"
LINKS_OUT = MAPPED_DIR / "links.ttl"
SOURCES_OUT = MAPPED_DIR / "sources"


def queries() -> list[tuple[str, str, str]]:
    header = (MAPPING_DIR / "_prefixes.rq").read_text(encoding="utf-8")
    out = []
    for f in sorted(MAPPING_DIR.glob("[0-9]*.rq")):
        text = f.read_text(encoding="utf-8")
        target = text.splitlines()[0].removeprefix("# graph:").strip()
        out.append((f.stem, target, header + text))
    return out


def new_graph() -> Graph:
    g = Graph()
    for prefix, ns in PREFIXES.items():
        g.bind(prefix, ns)
    return g


PROPERTY_ROWS = """
PREFIX map: <https://example.org/mythograph/pipeline#>
PREFIX wikibase: <http://wikiba.se/ontology#>
SELECT ?wdprop ?p ?ps WHERE {
  { ?wdprop map:toProperty [] } UNION { ?wdprop map:typing true }
  ?wdprop wikibase:claim ?p ; wikibase:statementProperty ?ps .
}"""


def construct(work: Graph, query: str, graph: URIRef | None = None) -> Graph:
    """Esegue una CONSTRUCT; ?graph, se c'è, è fissato con initBindings.

    Le query che leggono la tabella delle proprietà (?wdprop) girano una volta per
    proprietà, con ?wdprop, ?p e ?ps già fissati: con il predicato variabile
    (?item ?p ?st) rdflib scorrerebbe tutte le triple per ogni personaggio.
    """
    base = {"graph": graph} if graph is not None else {}
    rows = [dict(zip(("wdprop", "p", "ps"), r)) for r in work.query(PROPERTY_ROWS)] \
        if "?wdprop" in query else [{}]
    out = new_graph()
    for row in rows:
        out += work.query(query, initBindings={**base, **row}).graph
    return out


def focus(work: Graph, tables: Graph, depth: int = 5) -> Graph:
    """Il sottografo dei personaggi scelti: tutto ciò che si raggiunge da loro in pochi passi
    (affermazione -> valore o riferimento -> opera -> autore), più le tabelle.

    Le query successive leggono solo questo: su tutto il grafo grezzo (127 mila triple)
    rdflib impiegherebbe troppo. Gli altri personaggi scaricati non si attraversano.
    """
    others = set(work.subjects(MAP.extracted, None)) - set(work.subjects(MAP.inScope, None))
    out = Graph()
    out += tables
    frontier = set(work.subjects(MAP.inScope, None))
    seen = set(frontier)
    for _ in range(depth):
        nxt = set()
        for node in frontier:
            for p, o in work.predicate_objects(node):
                out.add((node, p, o))
                if isinstance(o, (URIRef, BNode)) and o not in seen and o not in others:
                    nxt.add(o)
                elif o in others:           # un personaggio escluso: basta sapere che esiste
                    out.add((o, MAP.extracted, Literal(True)))
        seen |= nxt
        frontier = nxt
    out += work.triples((None, MAP.under, None))     # classi -> classi della tabella
    for node in set(tables.subjects()):              # proprietà: wikibase:claim, statementProperty
        out += work.triples((node, None, None))
    for node in seen:                                # voce di Wikipedia (punta al personaggio)
        for article in work.subjects(SCHEMA.about, node):
            out += work.triples((article, None, None))
    return out


def run(verbose: bool = True) -> tuple[Graph, Graph, dict[str, Graph]]:
    log = print if verbose else (lambda *a, **k: None)
    work = Graph().parse(RAW_FILE)
    tables = Graph()
    for f in sorted((PIPELINE_DIR / "tables").glob("*.ttl")):
        tables.parse(f)
    work += tables
    graphs = sorted(set(tables.objects(None, MAP.graph))) + [GRAPH.wikidata]

    shared, links = new_graph(), new_graph()
    sources = {str(g).removeprefix(str(GRAPH)): new_graph() for g in graphs}
    focused = False
    for name, target, query in queries():
        t0 = time.time()
        if target != "work" and not focused:
            work, focused = focus(work, tables), True
            log(f"  {'(sottografo)':<16}               {len(work):>6} triple")
        if target == "per source":
            for gid in graphs:
                sources[str(gid).removeprefix(str(GRAPH))] += construct(work, query, gid)
            n = sum(len(g) for g in sources.values())
        elif target == "work":              # fino al punto fisso, come le regole
            n = 0
            while new := construct(work, query) - work:
                work += new
                n += len(new)
        else:
            res = construct(work, query)
            {"shared": shared, "links": links}[target].__iadd__(res)
            n = len(res)
        log(f"  {name:<16} -> {target:<10} {n:>6} triple  ({time.time() - t0:.1f}s)")
    return shared, links, sources


def write(g: Graph, path, what: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Generato da `python -m mythograph.mapping` ({what}). Non modificare a mano.\n"
                    + g.serialize(format="turtle"), encoding="utf-8")


def main() -> None:
    shared, links, sources = run()
    write(shared, SHARED_OUT, "entità comuni")
    write(links, LINKS_OUT, "collegamenti")
    for old in SOURCES_OUT.glob("*.ttl") if SOURCES_OUT.exists() else []:
        old.unlink()
    for name, g in sources.items():
        if len(g):
            write(g, SOURCES_OUT / f"{name}.ttl", f"affermazioni del grafo g:{name}")
    print("Fonti:", ", ".join(f"{n} {len(g)}" for n, g in sources.items()))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
