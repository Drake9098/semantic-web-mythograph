# Competency Questions

Le competency question (CQ) sono le domande a cui l'ontologia deve saper rispondere.
Guidano la progettazione (ogni classe/proprietà esiste perché serve ad almeno una CQ)
e servono come criterio di valutazione: ogni CQ ha una query SPARQL in `queries/`
e un test in `tests/`.

| # | Domanda | Concetti usati | Query |
|---|---------|----------------|-------|
| CQ1 | Chi sono i genitori di un personaggio **secondo ciascuna fonte**? | named graph, `GRAPH ?g` | `queries/cq01_parents_by_source.rq` |
| CQ2 | Quali affermazioni genealogiche sono **contestate** tra fonti diverse? | named graph, confronto tra grafi, `FILTER` | `queries/cq02_conflicts.rq` |
| CQ3 | Chi sono **tutti gli antenati** di Eracle? | `owl:TransitiveProperty`, `rdfs:subPropertyOf` | `queries/cq03_ancestors.rq` |
| CQ4 | Quali personaggi sono **semidei**? (non asserito: lo deduce il reasoner) | classe definita, `owl:equivalentClass`, `owl:intersectionOf`, `owl:someValuesFrom` | `queries/cq04_demigods.rq` |
| CQ5 | Chi sono gli **zii** di un personaggio? | property chain / regola CONSTRUCT | `queries/cq05_uncles.rq` |
| CQ6 | Quali miti sono ambientati in un luogo e nei luoghi che contiene (es. Sicilia)? | `locatedIn` transitiva | `queries/cq06_events_in_place.rq` |
| CQ7 | Quale fonte e quale passo attestano una certa affermazione? | reificazione `rdf:Statement`, Dublin Core | `queries/cq07_attestation.rq` |
| CQ8 | Quali personaggi compaiono in **più fonti**? | named graph, `GROUP BY`/`HAVING` | `queries/cq08_multi_source.rq` |
| CQ9 | Chi ha **ucciso chi**? | `owl:inverseOf` (`killed`/`killedBy`) | `queries/cq09_killings.rq` |
| CQ10 | Quali personaggi sono **eroi** e a quali imprese hanno partecipato? | classe definita con `owl:unionOf` | `queries/cq10_heroes.rq` |
