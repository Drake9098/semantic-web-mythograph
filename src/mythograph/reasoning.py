"""Ragionamento su tre livelli.

1. ``rules``   regole SPARQL CONSTRUCT (ontology/rules/*.rq), applicate fino a
               punto fisso, nello stile degli esempi di lezione
               (``g += g.query(CONSTRUCT ...)``).
2. ``owlrl``   chiusura OWL 2 RL con la libreria owlrl.
3. ``hermit``  reasoner OWL 2 DL HermiT (via owlready2, richiede Java):
               classificazione completa e controllo di consistenza.

Ogni livello restituisce solo le triple NUOVE e "interessanti" (vedi
``keep_triple``), così la UI può mostrare da quale livello viene ogni
inferenza.
"""
from __future__ import annotations

import io
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import BNode, Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from .namespaces import EXTERNAL_NS, MYTH, RES, ROOT

RULES_DIR = ROOT / "ontology" / "rules"

_SKIP_TYPES = {OWL.Thing, OWL.NamedIndividual, RDFS.Resource}
_REIFICATION_PREDICATES = {RDF.subject, RDF.predicate, RDF.object}


def keep_triple(s, p, o) -> bool:
    """True se la tripla è un fatto sul dominio (non rumore del reasoner)."""
    if not isinstance(s, URIRef) or not str(s).startswith(str(RES)):
        return False
    if isinstance(o, BNode):
        return False
    if p == RDF.type:
        return (isinstance(o, URIRef) and o not in _SKIP_TYPES
                and str(o).startswith((str(MYTH), *EXTERNAL_NS)))
    if p == OWL.sameAs:
        return s != o
    return str(p).startswith((str(MYTH), *EXTERNAL_NS))


# --------------------------------------------------------------------------- #
# Livello 1 — regole CONSTRUCT
# --------------------------------------------------------------------------- #
def load_rules() -> list[tuple[str, str]]:
    return [(f.stem, f.read_text(encoding="utf-8")) for f in sorted(RULES_DIR.glob("*.rq"))]


def apply_rules(graph: Graph, max_rounds: int = 20) -> Graph:
    """Applica tutte le regole finché non si producono più triple nuove."""
    work = Graph()
    work += graph
    rules = load_rules()
    for _ in range(max_rounds):
        before = len(work)
        for _name, query in rules:
            for t in work.query(query):
                work.add(t)
        if len(work) == before:
            break
    new = Graph()
    for t in work:
        if t not in graph and keep_triple(*t):
            new.add(t)
    return new


# --------------------------------------------------------------------------- #
# Livello 2 — OWL 2 RL (owlrl)
# --------------------------------------------------------------------------- #
@dataclass
class RLResult:
    inferred: Graph
    consistent: bool
    errors: list[str] = field(default_factory=list)


def apply_owlrl(graph: Graph) -> RLResult:
    import owlrl

    work = Graph()
    work += graph
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(work)
    # owlrl scrive le violazioni come  [] a err:ErrorMessage ; err:error "..."
    err = URIRef("http://www.daml.org/2002/03/agents/agent-ont#error")
    errors = [str(o) for o in work.objects(None, err)]
    # In OWL RL l'inconsistenza si manifesta come un individuo di tipo owl:Nothing
    # o come violazioni segnalate da owlrl.
    nothing = [s for s in work.subjects(RDF.type, OWL.Nothing) if s != OWL.Nothing]
    errors += [f"{s} è istanza di owl:Nothing" for s in nothing]
    new = Graph()
    for t in work:
        if t not in graph and keep_triple(*t):
            new.add(t)
    return RLResult(new, consistent=not errors, errors=errors)


# --------------------------------------------------------------------------- #
# Livello 3 — OWL 2 DL (HermiT via owlready2)
# --------------------------------------------------------------------------- #
@dataclass
class DLResult:
    available: bool
    consistent: bool | None
    inferred: Graph
    message: str = ""


_JAVA_CANDIDATES = [
    r"C:\Program Files (x86)\Common Files\Oracle\Java\java8path\java.exe",
    r"C:\Program Files\Common Files\Oracle\Java\javapath\java.exe",
]


def find_java() -> str | None:
    """Cerca java: variabile JAVA_EXE, poi PATH, poi JAVA_HOME, poi percorsi tipici di Windows."""
    import glob
    import os

    if os.environ.get("JAVA_EXE") and Path(os.environ["JAVA_EXE"]).exists():
        return os.environ["JAVA_EXE"]
    if exe := shutil.which("java"):
        return exe
    if home := os.environ.get("JAVA_HOME"):
        cand = Path(home) / "bin" / "java.exe"
        if cand.exists():
            return str(cand)
    patterns = _JAVA_CANDIDATES + [
        r"C:\Program Files\Eclipse Adoptium\*\bin\java.exe",
        r"C:\Program Files\Java\*\bin\java.exe",
        r"C:\Program Files (x86)\Java\*\bin\java.exe",
    ]
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def java_available() -> bool:
    return find_java() is not None


def _dl_input(graph: Graph) -> Graph:
    """Rimuove la reificazione: il vocabolario rdf: è riservato in OWL 2 DL."""
    statements = set(graph.subjects(RDF.type, RDF.Statement))
    out = Graph()
    for s, p, o in graph:
        if s in statements or p in _REIFICATION_PREDICATES:
            continue
        out.add((s, p, o))
    return out


def apply_hermit(graph: Graph) -> DLResult:
    if not java_available():
        return DLResult(False, None, Graph(), "Java non trovato: HermiT saltato.")

    import owlready2
    import owlready2.reasoning
    from owlready2 import World, sync_reasoner_hermit
    from owlready2.base import OwlReadyInconsistentOntologyError

    owlready2.JAVA_EXE = find_java()
    # Una JVM a 32 bit non riesce ad allocare i 2 GB di default di owlready2.
    owlready2.reasoning.JAVA_MEMORY = 1000

    dl = _dl_input(graph)
    data = dl.serialize(format="nt", encoding="utf-8")
    world = World()
    onto = world.get_ontology("https://example.org/mythograph/dl-input")
    onto.load(fileobj=io.BytesIO(data), format="ntriples")
    try:
        with onto:
            sync_reasoner_hermit(world, infer_property_values=True, debug=0)
    except OwlReadyInconsistentOntologyError:
        return DLResult(True, False, Graph(), "HermiT: ontologia INCONSISTENTE.")
    except owlready2.OwlReadyJavaError as exc:  # pragma: no cover - dipende dall'ambiente
        return DLResult(False, None, Graph(), f"Errore Java/HermiT: {exc}")

    result = world.as_rdflib_graph()
    new = Graph()
    for s, p, o in result.triples((None, None, None)):
        t = (s, p, o)
        # owlready2 ritipizza i letterali (es. "vv. 1-10" → xsd:string): non
        # sono inferenze vere, e HermiT qui non deduce nuovi valori di dati.
        if isinstance(o, Literal):
            continue
        if t not in dl and keep_triple(*t):
            new.add(t)
    return DLResult(True, True, new, "HermiT: ontologia consistente.")


def _as_graph(*graphs: Graph) -> Graph:
    g = Graph()
    for x in graphs:
        g += x
    return g


@dataclass
class SourceReasoning:
    rules: Graph
    owlrl: RLResult
    hermit: DLResult


def reason(base: Graph) -> SourceReasoning:
    """Esegue i tre livelli in cascata su ``base`` (TBox + shared + fonte)."""
    rules = apply_rules(base)
    rl = apply_owlrl(_as_graph(base, rules))
    rl.inferred -= rules
    dl = apply_hermit(_as_graph(base, rules, rl.inferred))
    dl.inferred -= rules
    dl.inferred -= rl.inferred
    return SourceReasoning(rules, rl, dl)


__all__ = ["reason", "apply_rules", "apply_owlrl", "apply_hermit", "keep_triple", "java_available"]
