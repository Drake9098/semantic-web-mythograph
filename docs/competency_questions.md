# Competency Questions

Le competency question (CQ) sono le domande a cui l'ontologia deve saper rispondere.
Guidano la progettazione (ogni classe o proprietà esiste perché serve ad almeno una CQ)
e servono come criterio di valutazione: ogni CQ ha una query SPARQL in `queries/`,
quasi tutte hanno un test in `tests/`.

| # | Domanda | Concetti usati | Query |
|---|---------|----------------|-------|
| CQ1 | Chi sono i genitori di un personaggio **secondo ciascuna fonte**? | named graph, `GRAPH ?g` | `cq01_parents_by_source.rq` |
| CQ2 | Quali parentele sono **contestate**? | confronto tra grafi, `FILTER`, `UNION` | `cq02_conflicts.rq` |
| CQ3 | Chi sono **tutti gli antenati** di un personaggio? | `owl:TransitiveProperty`, `rdfs:subPropertyOf` | `cq03_ancestors.rq` |
| CQ4 | Quali personaggi sono **semidei**? | classe definita (`Mortal and hasParent some Deity`) | `cq04_demigods.rq` |
| CQ5 | Chi sono gli **zii** e le **zie**? | catena di proprietà + SWRL con il genere | `cq05_uncles.rq` |
| CQ6 | Chi ha **regnato** su un luogo? | catena `holdsTitle o titleOver`, classe definita `Ruler` | `cq06_rulers.rq` |
| CQ7 | Quali **opere antiche** attestano le parentele di un personaggio? | named graph per autore, provenienza da Wikidata (P248) | `cq07_attestation.rq` |
| CQ8 | Quali personaggi compaiono in **più fonti**? | `GROUP BY` / `HAVING` | `cq08_multi_source.rq` |
| CQ9 | Chi ha **ucciso un parente**? | regole SWRL (uccisione + parentela), gerarchia di proprietà | `cq09_kinslayers.rq` |
| CQ10 | Quali personaggi sono **eroi**, e quale mostro hanno ucciso? | classe definita (`Mortal and killed some Monster`), inversa | `cq10_heroes.rq` |
| CQ11 | Chi ha **sposato un consanguineo**? Chi è una **figura edipica**? | SWRL + classi definite su proprietà dedotte | `cq11_consanguineous.rq` |
| CQ12 | Quali fonti **si contraddicono da sole**? | controllo di coerenza, vincoli funzionali | `cq12_internal_conflicts.rq` |

Le risposte più interessanti sono tutte **dedotte**: nessuna affermazione di Wikidata dice
che Achille è un semidio, che Edipo è un parricida o che Zeus ha sposato la sorella.
