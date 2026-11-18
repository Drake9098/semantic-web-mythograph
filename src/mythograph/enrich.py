"""Collegamento a Wikidata e DBpedia (linked data).

    python -m mythograph.enrich            # ricerca QID (usa la cache) + query federata
    python -m mythograph.enrich --refresh  # rifà anche la ricerca dei QID

Passo 1 — RICERCA. Per ogni personaggio, luogo, opera e autore cerca su Wikidata
le entità con la stessa etichetta inglese (query SPARQL a blocchi) e sceglie il candidato la cui
descrizione è coerente col tipo (es. "Greek goddess…" per una divinità). I
risultati vanno in data/wikidata_cache.json, che si può correggere a mano;
OVERRIDES fissa i casi ambigui. Nessun identificativo è inventato.

Passo 2 — QUERY FEDERATA (lezione 8, parola chiave SERVICE). Una query SPARQL
eseguita da rdflib sul NOSTRO grafo ("quali risorse hanno un sameAs verso
Wikidata?") delega una parte all'endpoint pubblico di Wikidata ("dammi le
coordinate e la pagina Wikipedia di queste entità"). Il risultato è salvato in
data/links.ttl, così la build e l'interfaccia funzionano anche offline.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, XSD

from .namespaces import (DBR, GEO, LINKS_FILE, MYTH, ONTOLOGY_FILE, PREFIXES, QUERIES_DIR,
                         RES, SHARED_FILE, WD, WIKIDATA_CACHE)

USER_AGENT = "MythoGraph/0.1 (university Semantic Web course project)"
ENDPOINT = "https://query.wikidata.org/sparql"

# Parole che, nella descrizione inglese di Wikidata, rendono un candidato
# coerente col tipo della nostra risorsa. Ogni parola trovata vale 1 punto.
KEYWORDS = {
    "character": ["mytholog", "goddess", "god of", "god ", "deity", "titan", "nymph", "oceanid", "nereid",
                  "hero", "trojan", "cyclop", "monster", "primordial", "son of", "daughter of", "iliad",
                  "odyssey", "legendary", "gorgon", "personification", "king of", "queen of", "wife of",
                  "mother of", "father of", "metamorphoses", "hesiod", "homer"],
    "roman": ["roman", "god", "goddess", "deity", "mytholog"],
    "place": ["island", "city", "mountain", "volcano", "region", "country", "lake", "strait",
              "comune", "ancient", "archaeological", "village", "municipality", "town", "sovereign state",
              "peninsula", "historical", "greece", "sicily", "italy", "crete", "turkey", "anatolia"],
    "mythplace": ["mytholog", "underworld", "abyss", "island", "homer", "odyssey"],
    "work": ["poem", "epic", "compendium", "hesiod", "homer", "ovid", "myth"],
    "author": ["poet", "writer", "author", "mythograph"],
}
# Descrizioni da scartare: opere, fiction, omonimi moderni.
EXCLUDE = ["tragedy", "play by", "opera by", "film", "novel", "album", "song", "fresco", "painting",
           "musical", "star trek", "dc universe", "marvel", "disney", "video game", "dungeons",
           "village in", "county", "genus", "species", "ship", "given name", "journal", "new york",
           "metope", "pelt", "asteroid", "moon of", "planet"]
# Bonus/penalità: una figura greca preferisce "greek", una romana "roman".
PREFER = {"character": ("greek", "roman"), "roman": ("roman", "greek")}

# Etichetta inglese ESATTA da cercare su Wikidata quando diversa dalla nostra.
# None = non collegare (nessuna entità corrispondente o troppo ambigua).
SEARCH_TERMS: dict[str, str | None] = {
    "TartarusPlace": None, "Charis": None, "Symaethis": None, "AcisRiver": None,
    "LandOfCyclopes": None, "StraitOfScylla": None, "Underworld": None,
    "Hydra": "Lernaean Hydra", "NemeanLion": "Nemean lion", "Dis": "Dis Pater",
    "Etna": "Mount Etna", "LakePergus": "Lake Pergusa", "Apollodorus": "Pseudo-Apollodorus",
    "Odyssey": "Odyssey", "Iliad": "Iliad", "MountOlympus": "Mount Olympus",
    "StraitOfMessina": "Strait of Messina",
    # etichette inglesi usate da Wikidata (trascrizioni diverse dalle nostre)
    "Alcmene": "Alkmene", "Crius": "Kreios", "Cythera": "Kythira", "Erebus": "Erebos",
    "Hydra": "Hydra", "Bibliotheca": "Bibliotheca",
}
# QID fissati a mano dopo aver controllato la descrizione su Wikidata
# (sovrascrivono la ricerca automatica).
OVERRIDES: dict[str, str | None] = {
    "Aglaea": "Q4439972",       # una delle Cariti (l'omonima figlia di Manteo è un'altra)
    "Briareus": "Q849647",      # uno dei Centimani
    "Poseidon": "Q41127",       # la ricerca sceglieva Nettuno (che ha "Poseidon" come alias)
    "Vulcan": "Q4640",          # non l'omonima città romena
    "Diana": "Q132543",
    "Hecuba": "Q193433",        # la sposa di Priamo, non la tragedia di Euripide
    "Peneus": "Q1364612",       # dio fluviale della Tessaglia
    "Ithaca": "Q187471",        # l'isola greca, non la città di New York
    "Italy": "Q38",
    "Chrysaor": "Q320660",      # figlio di Medusa (l'omonimo figlio di Glauco è un altro)
    "Laodamia": "Q1601938",     # figlia di Bellerofonte, madre di Sarpedonte
    "Menoetius": "Q1920680",    # padre di Patroclo, non il Titano
    "Enna": "Q13687",           # il comune moderno (con coordinate)
    "Thebes": "Q5760",          # Tebe in Beozia, non quella egizia
    "Typhon": "Q180237",        # il mostro greco, non il dio egizio
    "Cythera": "Q207239",       # l'isola di Citera
    "NemeanLion": "Q199438",
    "LakePergus": None,         # nessuna entità adeguata: la mappa usa Enna (locatedIn)
}


def http_json(url: str, data: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": USER_AGENT, "Accept": "application/sparql-results+json, application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def entities_to_link(shared: Graph, tbox: Graph) -> dict[str, tuple[str, str]]:
    """local id → (etichetta inglese, tipo per le parole chiave)."""
    def subclasses(c):
        return set(tbox.transitive_subjects(RDFS.subClassOf, c))
    roman = set(shared.subjects(MYTH.romanCounterpart, None))
    kinds = [(subclasses(MYTH.Character), "character"), ({MYTH.RealPlace}, "place"),
             ({MYTH.MythicalPlace}, "mythplace"), ({MYTH.LiteraryWork}, "work"), ({MYTH.Author}, "author")]
    out = {}
    for s in sorted(set(shared.subjects(RDF.type, None))):
        if not str(s).startswith(str(RES)):
            continue
        types = set(shared.objects(s, RDF.type))
        kind = next((k for classes, k in kinds if types & classes), None)
        if not kind:
            continue
        if s in roman or str(s).endswith("/Faunus"):
            kind = "roman"
        en = next((str(o) for o in shared.objects(s, RDFS.label) if getattr(o, "language", None) == "en"), None)
        if en:
            out[str(s).removeprefix(str(RES))] = (en.split(" (")[0], kind)
    return out


CANDIDATES_QUERY = """
SELECT ?label ?item ?desc ?links WHERE {
  VALUES ?label { %s }
  { ?item rdfs:label ?label } UNION { ?item skos:altLabel ?label }
  ?item schema:description ?desc ; wikibase:sitelinks ?links .
  FILTER(LANG(?desc) = "en")
}"""


def score(desc: str, kind: str) -> int:
    d = desc.lower()
    if any(x in d for x in EXCLUDE):
        return 0
    s = sum(k in d for k in KEYWORDS[kind])
    if kind in PREFER:
        good, bad = PREFER[kind]
        s += 2 * (good in d) - 2 * (bad in d)
    return s


def lookup(refresh: bool = False) -> dict:
    """Passo 1: trova i QID con query SPARQL a blocchi sulle etichette esatte."""
    cache = json.loads(WIKIDATA_CACHE.read_text(encoding="utf-8")) if WIKIDATA_CACHE.exists() else {}
    tbox, shared = Graph().parse(ONTOLOGY_FILE), Graph().parse(SHARED_FILE)
    todo = {}
    for local, (label, kind) in entities_to_link(shared, tbox).items():
        if local in cache and not refresh:
            continue
        term = SEARCH_TERMS.get(local, label)
        if term is None:
            cache[local] = {"qid": None, "reason": "non collegato di proposito"}
            continue
        todo[local] = (term, kind)

    candidates: dict[str, list[tuple[str, str, int]]] = {}
    terms = sorted({t for t, _ in todo.values()})
    for i in range(0, len(terms), 40):
        chunk = terms[i:i + 40]
        values = " ".join(json.dumps(t, ensure_ascii=False) + "@en" for t in chunk)
        res = http_json(ENDPOINT, {"query": CANDIDATES_QUERY % values, "format": "json"})
        for b in res["results"]["bindings"]:
            qid = b["item"]["value"].rsplit("/", 1)[-1]
            candidates.setdefault(b["label"]["value"], []).append(
                (qid, b["desc"]["value"], int(b["links"]["value"])))
        time.sleep(1)                                  # rispetto per il servizio pubblico

    for local, (term, kind) in sorted(todo.items()):
        best = None
        for qid, desc, links in candidates.get(term, []):
            sc = score(desc, kind)
            # tra i candidati coerenti vince il più noto (più pagine Wikipedia collegate)
            key = (min(sc, 2), links)
            if sc > 0 and (best is None or key > best[0]):
                best = (key, qid, desc)
        cache[local] = ({"qid": best[1], "label": term, "description": best[2]} if best
                        else {"qid": None, "reason": "nessun candidato coerente"})
    for local, qid in OVERRIDES.items():
        cache[local] = {**cache.get(local, {}), "qid": qid, "override": True}
    WIKIDATA_CACHE.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return cache


def _identify_rdflib_requests() -> None:
    """rdflib invia le richieste SERVICE con User-Agent "rdflibForAnUser"; la
    policy di Wikidata chiede di identificare il client. Sostituiamo l'header."""
    import rdflib.plugins.sparql.evaluate as ev
    if getattr(ev, "_mythograph_patched", False):
        return
    original = ev.urlopen

    def urlopen(req, *a, **kw):
        req.add_header("User-agent", USER_AGENT)   # urllib normalizza il nome in "User-agent"
        req.headers.pop("User-Agent", None)
        return original(req, *a, timeout=120, **kw)

    ev.urlopen = urlopen
    ev._mythograph_patched = True


def federated(cache: dict) -> Graph:
    """Esegue queries/federated_wikidata.rq: grafo locale + SERVICE Wikidata."""
    local = Graph()
    for k, v in cache.items():
        if v.get("qid"):
            local.add((RES[k], OWL.sameAs, WD[v["qid"]]))
    iris = " ".join(f"<{WD[v['qid']]}>" for v in cache.values() if v.get("qid"))
    query = (QUERIES_DIR / "federated_wikidata.rq").read_text(encoding="utf-8").replace("{{WIKIDATA_IRIS}}", iris)
    _identify_rdflib_requests()
    links = Graph()
    for prefix, ns in PREFIXES.items():
        links.bind(prefix, ns, override=True, replace=True)
    links += local
    try:
        rows = list(local.query(query))
    except Exception as exc:  # rete assente o endpoint non raggiungibile
        print(f"Query federata non riuscita ({exc}); salvo solo i sameAs.")
        rows = []
    for res_, wd, coord, article in rows:
        if article is not None:
            links.add((res_, RDFS.seeAlso, article))
            title = urllib.parse.unquote(str(article).rsplit("/wiki/", 1)[-1])
            links.add((res_, OWL.sameAs, DBR[title]))
        if coord is not None:                       # WKT: "Point(lon lat)"
            lon, lat = str(coord).removeprefix("Point(").rstrip(")").split()
            links.set((res_, GEO.lat, Literal(round(float(lat), 5), datatype=XSD.decimal)))
            links.set((res_, GEO.long, Literal(round(float(lon), 5), datatype=XSD.decimal)))
    return links


def main(argv: list[str]) -> None:
    cache = lookup(refresh="--refresh" in argv)
    links = federated(cache)
    LINKS_FILE.write_text(
        "# Generato da `python -m mythograph.enrich` — non modificare a mano.\n"
        "# owl:sameAs verso Wikidata/DBpedia, coordinate (W3C Basic Geo) e pagina Wikipedia.\n"
        + links.serialize(format="turtle"), encoding="utf-8")
    n_same = len(list(links.triples((None, OWL.sameAs, None))))
    n_geo = len(list(links.triples((None, GEO.lat, None))))
    print(f"Scritto {LINKS_FILE}: {n_same} owl:sameAs, {n_geo} luoghi con coordinate.")


if __name__ == "__main__":
    main(sys.argv[1:])
