"""Ragionamento: regole CONSTRUCT (più le SWRL tradotte), poi owlrl (OWL 2 RL).

Ogni livello restituisce solo le triple nuove, così si sa chi ha dedotto cosa.
Il ragionamento OWL 2 DL (HermiT) si fa in Protégé, sui file di exports/.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import BNode, Graph, Namespace, URIRef
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


def _as_graph(*graphs: Graph) -> Graph:
    g = Graph()
    for x in graphs:
        g += x
    return g


@dataclass
class SourceReasoning:
    rules: Graph
    owlrl: RLResult


def reason(base: Graph) -> SourceReasoning:
    """I due livelli in cascata su ``base`` (TBox + entità comuni + fonte)."""
    rules = apply_rules(base)
    rl = apply_owlrl(_as_graph(base, rules))
    rl.inferred -= rules
    return SourceReasoning(rules, rl)


__all__ = ["reason", "apply_rules", "apply_owlrl", "keep_triple"]
