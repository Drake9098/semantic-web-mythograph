# MythoGraph

Ontologia OWL della mitologia greca in cui **le fonti antiche non sono d'accordo**.
Ogni fonte (Esiodo, Omero, Ovidio; Apollodoro in arrivo) è un *named graph* separato:
le versioni contrastanti convivono senza contraddizioni, il reasoner lavora fonte
per fonte, e un'interfaccia web rende il grafo visibile e interrogabile.

Progetto per il corso di Semantic Web (A.A. 2025/26, Prof.ssa M. Nicolosi Asmundo).

## Avvio rapido

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
pip install -e .
python -m mythograph.enrich     # (facoltativo, serve internet) aggiorna i link a Wikidata/DBpedia
python -m mythograph.build      # ragiona e genera data/generated/mythograph.trig
uvicorn mythograph.web.app:app  # http://localhost:8000
pytest                          # verifica le competency question
```

Per il livello OWL 2 DL (HermiT) serve **Java** (8 o superiore): viene cercato in
`JAVA_EXE`, nel PATH, in `JAVA_HOME` e nelle cartelle tipiche di Windows. Senza Java la pipeline
salta quel livello e usa regole CONSTRUCT + OWL RL.

## Struttura

| Percorso | Contenuto |
|---|---|
| `ontology/mythograph.ttl` | TBox: classi, proprietà, restrizioni, classi definite |
| `ontology/rules/*.rq` | regole di inferenza SPARQL CONSTRUCT (RDFS + OWL) |
| `ontology/alignments.ttl` | allineamento a CIDOC CRM, FaBiO, Dublin Core, FOAF, SKOS |
| `data/links.ttl` | `owl:sameAs` verso Wikidata/DBpedia e coordinate (generato da `enrich`) |
| `src/mythograph/enrich.py` | ricerca dei QID + query federata `SERVICE` su Wikidata |
| `data/shared.ttl` | entità su cui le fonti concordano (nomi it/en/grc, luoghi, opere) |
| `data/sources/*.ttl` | ABox di ogni fonte, con riferimenti ai versi |
| `data/generated/mythograph.trig` | output: tutti i named graph (asserite + dedotte) |
| `src/mythograph/build.py` | pipeline: carica → ragiona per fonte → TriG |
| `src/mythograph/reasoning.py` | 3 livelli: CONSTRUCT, owlrl, HermiT |
| `src/mythograph/web/` | FastAPI + Cytoscape.js |
| `queries/cq*.rq` | una query SPARQL per ogni competency question |
| `tests/` | ogni CQ ha la sua risposta attesa |
| `docs/` | competency question, guida ai concetti, scaletta della demo |

## Named graph prodotti

| Grafo | Contenuto |
|---|---|
| `g:ontology` | TBox |
| `g:alignments` | allineamento alle ontologie fondazionali |
| `g:links` | collegamenti a Wikidata/DBpedia e coordinate (fuori dal ragionamento) |
| `g:shared` | entità comuni + `owl:AllDifferent` |
| `g:hesiod`, `g:homer`, `g:ovid` | affermazioni asserite da ciascuna fonte |
| `g:inferred/<fonte>/rules\|owlrl\|hermit` | triple dedotte, separate per livello |
| `g:view/<fonte>` | shared + asserite + dedotte (comoda per le query) |
| `g:meta` | consistenza di ogni fonte e della fusione ingenua, conteggi |
