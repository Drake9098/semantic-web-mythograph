"""Le competency question restituiscono le risposte attese; la pipeline è coerente.

I test leggono data/generated/mythograph.trig. Se manca lo ricostruiscono (la build
completa richiede qualche minuto): per forzarla, MYTHOGRAPH_REBUILD=1.
"""
import os

import pytest
from rdflib import Graph, Literal
from rdflib.namespace import RDF

from mythograph.build import build
from mythograph.namespaces import (GRAPH, MYTH, ONTOLOGY_FILE, OUTPUT_FILE, RAW_DIR, RES, ROOT,
                                   SOURCES_DIR, SWRL_FILE)
from mythograph.reasoning import swrl_to_sparql
from mythograph.store import Store


@pytest.fixture(scope="session")
def store():
    if os.environ.get("MYTHOGRAPH_REBUILD") or not OUTPUT_FILE.exists():
        build(verbose=False)
    return Store(OUTPUT_FILE)


def rows(store, n, target=None):
    _, rs = store.run_cq(n, target)
    return {tuple(r) for r in rs}


def view(store, name):
    return store.graph(f"view/{name}")


# ------------------------------------------------------------ pipeline

def test_no_handwritten_facts():
    """I fatti vengono tutti dalla pipeline: non esistono più file di fonti scritti a mano."""
    assert not (ROOT / "data" / "sources").exists()
    assert (RAW_DIR / "02_statements.json").exists()
    assert (SOURCES_DIR / "wikidata.ttl").exists()


def test_swrl_rules_are_translated():
    tbox = Graph().parse(ONTOLOGY_FILE).parse(SWRL_FILE)
    names = {n for n, _ in swrl_to_sparql(tbox)}
    assert len(names) == 11
    assert "swrl: parricidio" in names


def test_every_source_is_consistent(store):
    meta = store.graph("meta")
    for name in store.sources:
        assert meta.value(GRAPH[name], MYTH.consistentOWLRL) == Literal(True), name


def test_naive_merge_is_inconsistent(store):
    meta = store.graph("meta")
    assert meta.value(GRAPH["merged-naive"], MYTH.consistentOWLRL) == Literal(False)


# --------------------------------------------------------- competency questions

def test_cq1_aphrodite_has_two_fathers_in_wikidata(store):
    fathers = {r[2] for r in rows(store, 1) if r[0] == GRAPH.wikidata and r[1] == MYTH.hasFather}
    assert {RES.Zeus, RES.Uranus} <= fathers


def test_cq2_conflicts_found(store):
    contested = {(r[0], r[1]) for r in rows(store, 2)}
    assert (RES.Aphrodite, MYTH.hasFather) in contested


def test_cq3_heracles_ancestors_are_inferred(store):
    ancestors = {r[1] for r in rows(store, 3) if r[0] == GRAPH.wikidata}
    assert {RES.Zeus, RES.Cronus, RES.Uranus} <= ancestors
    assert (RES.Heracles, MYTH.hasAncestor, RES.Cronus) not in store.graph("wikidata")


def test_cq4_achilles_is_a_demigod(store):
    """Morto a Troia -> mortale; la madre Teti è una Nereide -> divinità; quindi semidio."""
    demigods = {(r[1], r[2]) for r in rows(store, 4) if r[0] == GRAPH.wikidata}
    assert (RES.Achilles, RES.Thetis) in demigods
    assert (RES.Achilles, RDF.type, MYTH.Demigod) not in store.graph("shared")


def test_cq9_oedipus_killed_an_ancestor(store):
    assert (RES.Oedipus, MYTH.killedAncestor, RES.Laius) in rows(store, 9)


def test_cq11_consanguineous_marriages(store):
    rs = rows(store, 11)
    assert any(r[0] == RES.Oedipus and r[1] == MYTH.marriedAncestor and r[2] == RES.Jocasta for r in rs)
    assert any(r[0] == RES.Zeus and r[1] == MYTH.marriedSibling and r[2] == RES.Hera for r in rs)


def test_oedipus_is_classified_by_the_reasoner(store):
    v = view(store, "wikidata")
    for cls in (MYTH.Parricide, MYTH.Kinslayer, MYTH.ConsanguineousSpouse, MYTH.OedipalFigure):
        assert (RES.Oedipus, RDF.type, cls) in v, cls


def test_cq12_hesiod_contradicts_himself(store):
    """Secondo Esiodo Urano è figlio di Gea, ma anche di Emera."""
    found = {(r[0], r[1]) for r in rows(store, 12)}
    assert (GRAPH.hesiod, RES.Uranus) in found


def test_cq10_heroes_killed_monsters(store):
    heroes = rows(store, 10)
    assert (RES.Perseus, RES.Medusa) in heroes
    assert (RES.Theseus, RES.Minotaur) in heroes          # ibrido uomo-animale -> mostro
    v = view(store, "wikidata")                           # la Chimera è figlia di Tifone ed Echidna:
    assert (RES.Chimera, RDF.type, MYTH.Monster) in v     # mostro per la GCI, non per Wikidata


def test_creatures_are_not_humans(store):
    """Wikidata mette "leone immaginario" sotto "essere umano immaginario": vince la creatura."""
    v = view(store, "wikidata")
    assert (RES.NemeanLion, RDF.type, MYTH.Monster) in v
    assert (RES.NemeanLion, RDF.type, MYTH.Human) not in v


def test_selection_follows_the_cycles(store):
    """Circa 200 personaggi, partendo dai protagonisti dei cicli (tables/cycles.ttl)."""
    chars = set(store.graph("shared").subjects(RDF.type, MYTH.Character))
    assert 150 <= len(chars) <= 250
    assert {RES.Oedipus, RES.Cassiphone, RES.Bellerophon, RES.Gaia} <= chars


def test_cassiphone_married_and_killed_her_half_brother(store):
    """Cassifone e Telemaco sono figli di Odisseo: lei lo sposa e lo uccide."""
    v = view(store, "wikidata")
    assert (RES.Cassiphone, MYTH.marriedSibling, RES.Telemachus) in v
    assert (RES.Cassiphone, RDF.type, MYTH.Kinslayer) in v

