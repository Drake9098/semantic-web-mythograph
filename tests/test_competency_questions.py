"""Ogni competency question deve restituire le risposte attese.

I test ricostruiscono il grafo da zero (build) e poi interrogano il TriG.
"""
import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import RDF

from mythograph.build import build
from mythograph.namespaces import GRAPH, MYTH, OUTPUT_FILE, RES
from mythograph.store import Store


@pytest.fixture(scope="session")
def store():
    build(verbose=False)
    return Store(OUTPUT_FILE)


def rows_as_sets(store, n, target=None):
    _, rows = store.run_cq(n, target)
    return {tuple(r) for r in rows}


def test_cq1_aphrodite_parents_differ_by_source(store):
    rows = rows_as_sets(store, 1)
    assert (GRAPH.hesiod, MYTH.hasFather, RES.Uranus) in rows
    assert (GRAPH.homer, MYTH.hasFather, RES.Zeus) in rows
    assert (GRAPH.homer, MYTH.hasMother, RES.Dione) in rows


def test_cq2_conflicts_found(store):
    _, rows = store.run_cq(2)
    contested = {(r[0], r[1]) for r in rows}
    assert (RES.Aphrodite, MYTH.hasFather) in contested
    assert (RES.Aphrodite, MYTH.hasMother) in contested     # negata da Esiodo
    assert (RES.Hephaestus, MYTH.hasFather) in contested    # negata da Esiodo
    assert (RES.Eros, MYTH.hasParent) in contested          # Esiodo: nessuno; Ovidio: Venere
    # Demetra (Esiodo) e Cerere (Ovidio) sono la stessa madre: nessun falso conflitto
    assert (RES.Persephone, MYTH.hasMother) not in contested
    assert all(r[0] not in (RES.Venus, RES.Proserpina) for r in rows)


def test_ovid_identification_is_scoped_to_ovid(store):
    """owl:sameAs Venere = Afrodite vale solo nel grafo di Ovidio."""
    ovid, homer = store.graph("view/ovid"), store.graph("view/homer")
    assert (RES.Eros, MYTH.hasMother, RES.Aphrodite) in ovid
    assert (RES.Persephone, MYTH.hasFather, RES.Zeus) in ovid
    same_as = URIRef("http://www.w3.org/2002/07/owl#sameAs")
    assert (RES.Venus, same_as, RES.Aphrodite) in store.graph("ovid")
    assert (RES.Venus, same_as, RES.Aphrodite) not in homer
    assert (RES.Aphrodite, same_as, RES.Venus) not in store.graph("view/hesiod")


def test_cq3_heracles_ancestors_are_inferred(store):
    ancestors = {r[1] for r in rows_as_sets(store, 3) if r[0] == GRAPH.hesiod}
    assert {RES.Zeus, RES.Cronus, RES.Uranus, RES.Gaia, RES.Alcmene} <= ancestors


def test_cq4_demigods_classified(store):
    demigods = {r[1] for r in rows_as_sets(store, 4)}
    assert {RES.Heracles, RES.Achilles, RES.Sarpedon, RES.Helen} <= demigods
    assert RES.Zeus not in demigods          # una divinità non è umana
    assert RES.Pegasus not in demigods       # figlio di un dio, ma non umano


def test_cq5_heracles_uncles(store):
    rows = rows_as_sets(store, 5)
    uncles = {r[2] for r in rows if r[1] == MYTH.hasUncle}
    aunts = {r[2] for r in rows if r[1] == MYTH.hasAunt}
    assert {RES.Poseidon, RES.Hades} <= uncles
    assert RES.Demeter in aunts and RES.Zeus not in uncles


def test_cq6_events_in_sicily(store):
    events = {r[1] for r in rows_as_sets(store, 6)}
    assert {RES.BlindingOfPolyphemus, RES.CattleOfHelios, RES.PassageOfScyllaAndCharybdis} <= events
    # Ovidio: il ratto di Proserpina è al lago di Pergusa ⊂ Enna ⊂ Sicilia (locatedIn transitiva)
    assert {RES.AbductionOfProserpina, RES.TyphonUnderEtna, RES.AcisAndGalatea} <= events


def test_cq7_attestations(store):
    _, rows = store.run_cq(7)
    assert any(r[1] == RES.Aphrodite and r[4] == RES.Theogony and str(r[5]) == "vv. 188-206" for r in rows)


def test_cq8_multi_source_characters(store):
    names = {r[0] for r in rows_as_sets(store, 8)}
    assert {RES.Zeus, RES.Aphrodite, RES.Heracles, RES.Achilles} <= names


def test_cq9_killings_inverse(store):
    rows = rows_as_sets(store, 9)
    assert (GRAPH.homer, RES.Achilles, RES.Hector) in rows
    # killedBy è dedotta dall'inversa
    view = store.graph("view/homer")
    assert (RES.Hector, MYTH.killedBy, RES.Achilles) in view


def test_cq10_heroes(store):
    heroes = {r[1] for r in rows_as_sets(store, 10)}
    assert {RES.Heracles, RES.Perseus, RES.Odysseus, RES.Achilles} <= heroes


def test_hermit_reasoning_by_cases(store):
    """Solo un reasoner DL deduce che chi è stato ucciso è mortale
    (copertura Immortal ⊔ Mortal + Immortal ⊑ ≤0 killedBy)."""
    from mythograph.reasoning import java_available
    if not java_available():
        pytest.skip("Java non disponibile")
    hermit = store.graph("inferred/hesiod/hermit")
    for victim in (RES.Hydra, RES.NemeanLion, RES.Geryon):
        assert (victim, RDF.type, MYTH.Mortal) in hermit
    # e non lo avevano trovato i livelli precedenti
    assert (RES.Hydra, RDF.type, MYTH.Mortal) not in store.graph("inferred/hesiod/owlrl")


def test_each_source_consistent_but_naive_merge_is_not(store):
    meta = store.graph("meta")
    for src in store.sources:
        assert (GRAPH[src], MYTH.consistentOWLRL, Literal(True)) in meta
    assert (GRAPH["merged-naive"], MYTH.consistentOWLRL, Literal(False)) in meta
    if (GRAPH["merged-naive"], MYTH.consistentHermiT, None) in meta:
        for src in store.sources:
            assert (GRAPH[src], MYTH.consistentHermiT, Literal(True)) in meta
        assert (GRAPH["merged-naive"], MYTH.consistentHermiT, Literal(False)) in meta


def test_linked_data_and_alignment(store):
    """owl:sameAs verso Wikidata, coordinate dalla query federata, allineamento CIDOC."""
    from mythograph.namespaces import CRM, GEO, WD
    from rdflib.namespace import OWL
    links = store.graph("links")
    assert (RES.Zeus, OWL.sameAs, WD.Q34201) in links
    assert links.value(RES.Etna, GEO.lat) is not None
    # ogni evento del mito risulta anche un crm:E5_Event (regola subClassOf + alignments.ttl)
    assert (RES.AbductionOfProserpina, RDF.type, CRM.E5_Event) in store.graph("view/ovid")


def test_web_api_smoke():
    from fastapi.testclient import TestClient
    from mythograph.web.app import app
    c = TestClient(app)
    assert c.get("/api/places").json()
    e = c.get("/api/entity/Aphrodite").json()
    assert e["external"]["wikidata"].endswith("Q35500")
    assert not any(n["id"] == "Venus" for n in c.get("/api/graph?source=ovid").json()["nodes"])
