"""Pipeline, passo 1: estrazione da Wikidata (python -m mythograph.extract [--refresh]).

Esegue le query SELECT di pipeline/extract/ sull'endpoint pubblico di Wikidata
e salva le risposte JSON in data/raw/. Le query lunghe vanno a blocchi.
Se i file esistono già non riscarica nulla: la build resta riproducibile offline.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request

from rdflib import Graph, Literal
from rdflib.namespace import RDFS

from .namespaces import MAP, PIPELINE_DIR, RAW_DIR, WD

ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "MythoGraph/0.2 (university Semantic Web course project)"
BATCH = 150


def tables() -> Graph:
    g = Graph()
    for f in sorted((PIPELINE_DIR / "tables").glob("*.ttl")):
        g.parse(f)
    return g


def http_json(url: str, data: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": USER_AGENT, "Accept": "application/sparql-results+json, application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def sparql(query: str) -> list[dict]:
    for attempt in range(4):
        try:
            res = http_json(ENDPOINT, {"query": query, "format": "json"})
            return [{k: v["value"] for k, v in b.items()} for b in res["results"]["bindings"]]
        except Exception as exc:  # 429/502/timeout: riprova con calma
            wait = 5 * (attempt + 1)
            print(f"   errore ({exc}), riprovo tra {wait}s")
            time.sleep(wait)
    raise RuntimeError("Wikidata non risponde")


def template(name: str) -> str:
    return (PIPELINE_DIR / "extract" / name).read_text(encoding="utf-8")


def qid(iri: str) -> str:
    return iri.rsplit("/", 1)[-1]


def values(ids) -> str:
    return " ".join(f"wd:{i}" for i in ids)


def batched(name: str, ids: list[str], **extra: str) -> list[dict]:
    rows = []
    q = template(name)
    for k, v in extra.items():
        q = q.replace("{{" + k + "}}", v)
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        rows += sparql(q.replace("{{ITEMS}}", values(chunk)))
        print(f"   {name}: {min(i + BATCH, len(ids))}/{len(ids)}")
        time.sleep(1)                       # rispetto per il servizio pubblico
    return rows


def save(name: str, rows: list[dict]) -> list[dict]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{name}.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"-> data/raw/{name}.json ({len(rows)} righe)")
    return rows


def cached(name: str, refresh: bool):
    f = RAW_DIR / f"{name}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text(encoding="utf-8"))
    return None


def main(argv: list[str]) -> None:
    refresh = "--refresh" in argv
    t = tables()
    selecting = sorted(qid(str(c)) for c in t.subjects(MAP.selects, Literal(True)))
    anchors = sorted(qid(str(c)) for c in t.subjects(MAP.toClass, None))
    props = sorted(qid(str(p)) for p in t.subjects(MAP.typing, Literal(True))) + \
        sorted(qid(str(p)) for p in t.subjects(MAP.toProperty, None))

    print("0. classi della mitologia greca (con sottoclassi)")
    classes = cached("00_classes", refresh) or save("00_classes", sparql(
        template("00_classes.rq").replace("{{CLASSES}}", values(selecting))))

    print("1. personaggi")
    chars = cached("01_characters", refresh) or save("01_characters", sparql(
        template("01_characters.rq").replace("{{CLASSES}}", values(sorted({qid(r["class"]) for r in classes})))))
    char_ids = sorted({qid(r["item"]) for r in chars})

    print("2. affermazioni")
    stmts = cached("02_statements", refresh) or save("02_statements", batched(
        "02_statements.rq", char_ids, PROPS=" ".join(f"p:{p}" for p in props)))

    print("3. entità citate (luoghi, gruppi, titoli, opere, autori)")
    entities = cached("04_entities", refresh)
    if entities is None:
        entities, seen = [], set(char_ids)
        todo = {qid(r["value"]) for r in stmts if not r["prop"].endswith(("/P31", "/P21"))}
        todo |= {qid(r["work"]) for r in stmts if "work" in r}
        while todo := sorted(todo - seen):
            seen |= set(todo)
            rows = batched("04_entities.rq", todo)
            entities += rows
            # secondo giro: la giurisdizione di un titolo, l'autore di un'opera
            todo = {qid(r[k]) for r in rows for k in ("jurisdiction", "author") if k in r}
        save("04_entities", entities)

    print("4. nomi e voci Wikipedia")
    ent_ids = sorted({qid(r["item"]) for r in entities})
    if cached("03_labels", refresh) is None:
        save("03_labels", batched("03_labels.rq", sorted(set(char_ids) | set(ent_ids))))

    print("5. classi -> classi della tabella (P279*)")
    if cached("05_superclasses", refresh) is None:
        classes = {qid(r["value"]) for r in stmts if r["prop"].endswith(("/P31", "/P21"))}
        classes |= {qid(r["class"]) for r in entities if "class" in r}
        classes |= set(anchors)             # serve a scegliere la classe più specifica
        save("05_superclasses", batched("05_superclasses.rq", sorted(classes), ANCHORS=values(anchors)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
