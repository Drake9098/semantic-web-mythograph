"""Pipeline, passo 2: lifting (python -m mythograph.lift).

Trasforma i JSON di data/raw/ in RDF *nel modello di Wikidata*, senza
interpretare niente: wdt:, p:/ps: per le affermazioni con rango e fonte (prov:),
rdfs:label. Unica aggiunta: map:key, il nome leggibile che diventerà l'IRI
(res:Zeus invece di res:Q34201). Output: data/raw/wikidata.ttl
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import defaultdict

from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDFS

from .namespaces import MAP, RAW_DIR, WD

WDT = Namespace("http://www.wikidata.org/prop/direct/")
P = Namespace("http://www.wikidata.org/prop/")
PS = Namespace("http://www.wikidata.org/prop/statement/")
PR = Namespace("http://www.wikidata.org/prop/reference/")
PROV = Namespace("http://www.w3.org/ns/prov#")
WIKIBASE = Namespace("http://wikiba.se/ontology#")
SCHEMA = Namespace("http://schema.org/")
GEOSPARQL = Namespace("http://www.opengis.net/ont/geosparql#")
RAW_FILE = RAW_DIR / "wikidata.ttl"


def load(name: str) -> list[dict]:
    return json.loads((RAW_DIR / f"{name}.json").read_text(encoding="utf-8"))


def is_entity(iri: str) -> bool:
    return re.fullmatch(r"http://www\.wikidata\.org/entity/Q\d+", iri) is not None


def camel(label: str) -> str:
    """'Twelve Olympians' -> 'TwelveOlympians', 'Ἀθηνᾶ' resta fuori (solo ASCII)."""
    text = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    text = re.sub(r"\(.*?\)", "", text)
    words = re.findall(r"[A-Za-z0-9]+", text)
    return "".join(w[:1].upper() + w[1:] for w in words)


def keys(labels: dict[str, dict[str, str]], sitelinks: dict[str, int]) -> dict[str, str]:
    """Un nome unico per entità; a parità di nome vince la più nota, le altre prendono il QID."""
    by_name = defaultdict(list)
    for q, langs in labels.items():
        name = camel(langs.get("en") or "") or q
        if name[0].isdigit():
            name = "E" + name
        by_name[name].append(q)
    out = {}
    for name, qs in by_name.items():
        qs.sort(key=lambda q: (-sitelinks.get(q, 0), int(q[1:])))
        out[qs[0]] = name
        for q in qs[1:]:
            out[q] = f"{name}_{q}"
    return out


def lift() -> Graph:
    g = Graph()
    for prefix, ns in {"wd": WD, "wdt": WDT, "p": P, "ps": PS, "pr": PR, "prov": PROV,
                       "wikibase": WIKIBASE, "schema": SCHEMA, "map": MAP}.items():
        g.bind(prefix, ns)

    # personaggi scelti al passo 1
    sitelinks = {}
    for r in load("01_characters"):
        item = URIRef(r["item"])
        g.add((item, MAP.extracted, Literal(True)))
        sitelinks[str(item).rsplit("/", 1)[-1]] = int(r["sitelinks"])

    # affermazioni: modello completo (statement node, rango, riferimento)
    for r in load("02_statements"):
        if not is_entity(r["value"]):           # "valore sconosciuto" di Wikidata
            continue
        item, st, value = URIRef(r["item"]), URIRef(r["st"]), URIRef(r["value"])
        pid = r["prop"].rsplit("/", 1)[-1]
        g.add((WD[pid], WIKIBASE.claim, P[pid]))
        g.add((WD[pid], WIKIBASE.statementProperty, PS[pid]))
        g.add((item, P[pid], st))
        g.add((st, PS[pid], value))
        g.add((st, WIKIBASE.rank, URIRef(r["rank"])))
        if "work" in r:
            ref = BNode(f"ref_{str(st).rsplit('/', 1)[-1]}_{r['work'].rsplit('/', 1)[-1]}")
            g.add((st, PROV.wasDerivedFrom, ref))
            g.add((ref, PR.P248, URIRef(r["work"])))

    # entità citate: classe, coordinate, giurisdizione, autore, nascita
    for r in load("04_entities"):
        item = URIRef(r["item"])
        if not is_entity(r["item"]):
            continue
        if "class" in r:
            g.add((item, WDT.P31, URIRef(r["class"])))
        if "coord" in r:
            g.add((item, WDT.P625, Literal(r["coord"], datatype=GEOSPARQL.wktLiteral)))
        for k, pid in (("jurisdiction", "P1001"), ("author", "P50")):
            if k in r and is_entity(r[k]):
                g.add((item, WDT[pid], URIRef(r[k])))

    # nomi e voci Wikipedia
    labels: dict[str, dict[str, str]] = defaultdict(dict)
    for r in load("03_labels"):
        if not is_entity(r["item"]):
            continue
        item = URIRef(r["item"])
        q = r["item"].rsplit("/", 1)[-1]
        if "label" in r:
            g.add((item, RDFS.label, Literal(r["label"], lang=r["lang"])))
            labels[q][r["lang"]] = r["label"]
        if "sitelinks" in r:
            g.set((item, WIKIBASE.sitelinks, Literal(int(r["sitelinks"]))))
            sitelinks.setdefault(q, int(r["sitelinks"]))
        if "article" in r:
            g.add((URIRef(r["article"]), SCHEMA.about, item))
            g.add((URIRef(r["article"]), SCHEMA.isPartOf, URIRef("https://en.wikipedia.org/")))
        labels.setdefault(q, {})

    # classe -> classe "ancora" della tabella (P279*)
    for r in load("05_superclasses"):
        g.add((URIRef(r["class"]), MAP.under, URIRef(r["anchor"])))

    for q, name in keys(labels, sitelinks).items():
        g.add((WD[q], MAP.key, Literal(name)))
    return g


def main() -> None:
    g = lift()
    RAW_FILE.write_text(
        "# Generato da `python -m mythograph.lift`: dati di Wikidata nel loro modello originale.\n"
        + g.serialize(format="turtle"), encoding="utf-8")
    print(f"Scritto {RAW_FILE} ({len(g)} triple)")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
