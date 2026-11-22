"""Ragionamento: regole CONSTRUCT, poi owlrl (OWL 2 RL), poi HermiT (OWL 2 DL).

Ogni livello restituisce solo le triple nuove, così si sa chi ha dedotto cosa.
"""
from __future__ import annotations

import io
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection
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


# --- livello 1: regole CONSTRUCT
def load_rules() -> list[tuple[str, str]]:
    return [(f.stem, f.read_text(encoding="utf-8")) for f in sorted(RULES_DIR.glob("*.rq"))]


SWRL = Namespace("http://www.w3.org/2003/11/swrl#")


def swrl_to_sparql(tbox: Graph) -> list[tuple[str, str]]:
    """Traduce le regole SWRL dell'ontologia in CONSTRUCT: corpo -> WHERE, testa -> template.

    differentFrom diventa FILTER(?x != ?y): qui vale l'ipotesi dei nomi unici.
    """
    def var(node) -> str:
        return "?" + str(node).rsplit("#", 1)[-1]

    def atoms(lst) -> list[str]:
        out = []
        for a in Collection(tbox, lst):
            kind = tbox.value(a, RDF.type)
            x, y = tbox.value(a, SWRL.argument1), tbox.value(a, SWRL.argument2)
            if kind == SWRL.ClassAtom:
                out.append(f"{var(x)} a <{tbox.value(a, SWRL.classPredicate)}> .")
            elif kind == SWRL.IndividualPropertyAtom:
                out.append(f"{var(x)} <{tbox.value(a, SWRL.propertyPredicate)}> {var(y)} .")
            elif kind == SWRL.DifferentIndividualsAtom:
                out.append(f"FILTER({var(x)} != {var(y)})")
            else:
                raise ValueError(f"atomo SWRL non gestito: {kind}")
        return out

    rules = []
    for imp in tbox.subjects(RDF.type, SWRL.Imp):
        name = str(tbox.value(imp, RDFS.label) or "swrl")
        head = " ".join(atoms(tbox.value(imp, SWRL.head)))
        body = " ".join(atoms(tbox.value(imp, SWRL.body)))
        rules.append((f"swrl: {name}", f"CONSTRUCT {{ {head} }} WHERE {{ {body} }}"))
    return sorted(rules)


def apply_rules(graph: Graph, max_rounds: int = 20) -> Graph:
    """Applica tutte le regole (file .rq + SWRL tradotte) finché non producono più triple nuove."""
    work = Graph()
    work += graph
    rules = load_rules() + swrl_to_sparql(graph)
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


# --- livello 2: OWL RL
@dataclass
class RLResult:
    inferred: Graph
    consistent: bool | None
    errors: list[str] = field(default_factory=list)


def apply_owlrl(graph: Graph) -> RLResult:
    import owlrl

    work = Graph()
    work += graph
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, axiomatic_triples=False, datatype_axioms=False).expand(work)
    # owlrl scrive le violazioni come  [] a err:ErrorMessage ; err:error "..."
    err = URIRef("http://www.daml.org/2002/03/agents/agent-ont#error")
    errors = [str(o) for o in work.objects(None, err)]
    nothing = [s for s in work.subjects(RDF.type, OWL.Nothing) if s != OWL.Nothing]
    errors += [f"{s} è istanza di owl:Nothing" for s in nothing]
    new = Graph()
    for t in work:
        if t not in graph and keep_triple(*t):
            new.add(t)
    return RLResult(new, consistent=not errors, errors=errors)


# --- livello 3: HermiT
@dataclass
class DLResult:
    available: bool
    consistent: bool | None
    inferred: Graph
    message: str = ""
    tbox: Graph = field(default_factory=Graph)


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
    """Toglie la reificazione (vocabolario riservato in OWL 2 DL) e gli owl:imports (i moduli sono già qui)."""
    statements = set(graph.subjects(RDF.type, RDF.Statement))
    out = Graph()
    for s, p, o in graph:
        if s in statements or p in _REIFICATION_PREDICATES or p == OWL.imports:
            continue
        out.add((s, p, o))
    return out


def apply_hermit(graph: Graph, infer: bool = True) -> DLResult:
    """infer=False: solo controllo di coerenza."""
    if not java_available():
        return DLResult(False, None, Graph(), "Java non trovato: HermiT saltato.")

    import owlready2
    import owlready2.reasoning
    from owlready2 import World, sync_reasoner_hermit
    from owlready2.base import OwlReadyInconsistentOntologyError

    owlready2.JAVA_EXE = find_java()
    # la JVM a 32 bit non regge i 2 GB di default
    owlready2.reasoning.JAVA_MEMORY = 1000

    dl = _dl_input(graph)
    data = dl.serialize(format="nt", encoding="utf-8")
    world = World()
    onto = world.get_ontology("https://example.org/mythograph/dl-input")
    onto.load(fileobj=io.BytesIO(data), format="ntriples")
    try:
        with onto:
            sync_reasoner_hermit(world, infer_property_values=infer, debug=0)
    except OwlReadyInconsistentOntologyError:
        return DLResult(True, False, Graph(), "HermiT: ontologia INCONSISTENTE.")
    except owlready2.OwlReadyJavaError as exc:  # pragma: no cover - dipende dall'ambiente
        return DLResult(False, None, Graph(), f"Errore Java/HermiT: {exc}")
    if not infer:
        return DLResult(True, True, Graph(), "HermiT: ontologia consistente.")

    result = world.as_rdflib_graph()
    # classificazione della TBox: sottoclassi dedotte tra classi con nome (Parricide ⊑ Kinslayer)
    tbox = Graph()
    for c, sup in result.subject_objects(RDFS.subClassOf):
        if (isinstance(c, URIRef) and isinstance(sup, URIRef) and c != sup
                and str(c).startswith(str(MYTH)) and str(sup).startswith(str(MYTH))
                and (c, RDFS.subClassOf, sup) not in dl):
            tbox.add((c, RDFS.subClassOf, sup))
    new = Graph()
    for s, p, o in result.triples((None, None, None)):
        t = (s, p, o)
        # owlready2 ritipizza i letterali: non sono inferenze
        if isinstance(o, Literal):
            continue
        if t not in dl and keep_triple(*t):
            new.add(t)
    return DLResult(True, True, new, "HermiT: ontologia consistente.", tbox)


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
    """I tre livelli in cascata su ``base`` (TBox + entità comuni + fonte)."""
    rules = apply_rules(base)
    rl = apply_owlrl(_as_graph(base, rules))
    rl.inferred -= rules
    dl = apply_hermit(_as_graph(base, rules, rl.inferred))
    dl.inferred -= rules
    dl.inferred -= rl.inferred
    dl.inferred += superclass_closure(_as_graph(base, rules, rl.inferred, dl.inferred), dl.tbox)
    return SourceReasoning(rules, rl, dl)


def superclass_closure(g: Graph, inferred_tbox: Graph) -> Graph:
    """HermiT restituisce solo la classe più specifica: aggiungo le superclassi con nome."""
    hier = Graph()
    for c, sup in g.subject_objects(RDFS.subClassOf):
        if isinstance(c, URIRef) and isinstance(sup, URIRef):
            hier.add((c, RDFS.subClassOf, sup))
    hier += inferred_tbox
    supers: dict = {}
    out = Graph()
    for x, c in list(g.subject_objects(RDF.type)):
        if not isinstance(c, URIRef):
            continue
        if c not in supers:
            supers[c] = set(hier.transitive_objects(c, RDFS.subClassOf)) - {c}
        for sup in supers[c]:
            t = (x, RDF.type, sup)
            if t not in g and keep_triple(*t):
                out.add(t)
    return out


__all__ = ["reason", "apply_rules", "apply_owlrl", "apply_hermit", "keep_triple", "java_available"]
