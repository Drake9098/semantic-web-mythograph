# MythoGraph

Ontologia OWL delle genealogie della mitologia greca, costruita **interamente da Wikidata**.
Contiene circa 200 personaggi, scelti partendo da dieci cicli mitici (Tebe, Atridi, Eracle,
Teseo, Troia, Odissea, Argonauti...) per le deduzioni che permettono: parricidi, nozze tra
consanguinei, semidei, eroi.
Le fonti antiche non sono d'accordo tra loro: ogni fonte (Esiodo, Omero, Apollodoro,
Pausania, ...) è un *named graph* separato, ricavato dai riferimenti che Wikidata
attacca a ogni affermazione. Il ragionatore lavora fonte per fonte; i vincoli di
coerenza (un solo padre, una sola madre) valgono dentro una fonte e non tra fonti.

Progetto per il corso di Semantic Web (A.A. 2025/26, Prof.ssa M. Nicolosi Asmundo).

## Avvio rapido

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
pip install -e .
python -m mythograph.extract    # Wikidata -> data/raw/*.json (già nel repository; --refresh per riscaricare)
python -m mythograph.lift       # JSON -> RDF nel modello di Wikidata
python -m mythograph.mapping    # CONSTRUCT -> vocabolario MythoGraph, un grafo per fonte
python -m mythograph.build      # ragionamento, data/generated/mythograph.trig, exports/ per Protégé
uvicorn mythograph.web.app:app  # http://localhost:8000  (oppure doppio clic su avvia.bat)
pytest
```

Il ragionamento OWL 2 DL (HermiT) si fa in **Protégé**, aprendo i file di `exports/`: la pipeline usa solo rdflib e owlrl.

## Documentazione

- [`docs/pipeline.md`](docs/pipeline.md): come è costruito il grafo, passo per passo.
- [`docs/protege.md`](docs/protege.md): come aprire l'ontologia in Protégé e cosa mostrare.
- [`docs/competency_questions.md`](docs/competency_questions.md): le domande a cui l'ontologia risponde.

## Struttura

| Percorso | Contenuto |
|---|---|
| `ontology/mythograph.ttl` | modulo core: classi (anche definite), proprietà, assiomi |
| `ontology/constraints.ttl` | vincoli validi dentro una sola fonte (funzionali, cardinalità) |
| `ontology/rules.ttl` | 11 regole SWRL |
| `ontology/alignments.ttl` | allineamento a CIDOC CRM, FaBiO, FOAF, Dublin Core |
| `ontology/catalog-v001.xml` | catalogo per gli `owl:imports` in Protégé |
| `ontology/rules/*.rq` | regole SPARQL CONSTRUCT (RDFS e parte di OWL) |
| `pipeline/extract/*.rq` | query SELECT verso Wikidata |
| `pipeline/tables/*.ttl` | tabelle di corrispondenza (classi, proprietà, fonti) e cicli mitici |
| `pipeline/mapping/*.rq` | query CONSTRUCT: Wikidata -> MythoGraph |
| `data/raw/` | risposte di Wikidata (JSON) e il loro lifting in RDF |
| `data/mapped/` | output del mapping: `shared.ttl`, `links.ttl`, `sources/<fonte>.ttl` |
| `data/generated/mythograph.trig` | tutti i named graph, asserite e dedotte |
| `exports/` | un file per fonte da aprire in Protégé |
| `src/mythograph/` | `extract`, `lift`, `mapping`, `build`, `reasoning`, `web/` |
| `queries/cq*.rq` | una query SPARQL per competency question |
| `tests/` | risposte attese delle CQ, coerenza delle fonti |
