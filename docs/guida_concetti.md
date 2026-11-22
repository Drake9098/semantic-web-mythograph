# Guida ai concetti: dalla teoria al progetto

Per ogni argomento del corso: **dove è applicato** in MythoGraph e **come spiegarlo**.
Tieni aperto il file indicato mentre studi la slide.

---

## Lezione 1 — Perché il Semantic Web

| Concetto | Nel progetto | Come spiegarlo |
|---|---|---|
| Web di dati, non di documenti | Ogni personaggio è un IRI (`res:Zeus`), collegato al suo IRI su Wikidata e DBpedia (`data/mapped/links.ttl`) | "Non ho pagine su Zeus, ho dati su Zeus che una macchina può combinare." |
| **AAA** (chiunque dice qualunque cosa) | Wikidata dà ad Afrodite due padri e tre madri, ognuno da una fonte diversa | "Le fonti antiche sono come il Web: ognuno dice la sua. Il progetto mostra come conviverci." |
| **Open World Assumption** | Se Wikidata non dice che Teti è una dea non è falso: è sconosciuto. Lo deduce il ragionatore (è una Nereide) | "Quello che manca non è falso, è sconosciuto." |
| **Non unique naming** | `owl:AllDifferent` generato in `build.py` per ogni fonte | "Due IRI diversi possono indicare la stessa cosa. Senza AllDifferent, con un solo padre per fonte, il reasoner dedurrebbe Zeus = Urano invece di segnalare il conflitto." |

## Lezione 2 — Ontologie, DB vs KB, logica

| Concetto | Nel progetto |
|---|---|
| Ontologia = specifica formale di una concettualizzazione | `ontology/` (TBox, scritta e documentata a mano) separata dai fatti (ABox, generata dalla pipeline) |
| Tassonomia | `Character → Immortal → Deity → MinorDeity → Nymph → Nereid` |
| Inferenza logica | Teti è `memberOf Nereids` ⇒ Nereide ⇒ Ninfa ⇒ Divinità ⇒ Immortale |

## Lezione 3 — Merge di grafi, URI, namespace

| Concetto | Nel progetto |
|---|---|
| Merge = unione delle triple | La **fusione ingenua** delle fonti antiche diventa inconsistente (`exports/mythograph-merged-naive.ttl`) |
| Prefissi | `myth:` (TBox), `res:` (individui), `g:` (named graph), `map:` (tabelle della pipeline), `wd:`/`wdt:`/`p:`/`ps:` (Wikidata) |
| `owl:sameAs` | verso Wikidata e DBpedia (`data/mapped/links.ttl`), tenuto fuori dal ragionamento |

## Lezione 4 — Letterali, blank node, named graph

| Concetto | Nel progetto |
|---|---|
| Letterali con lingua | `rdfs:label "Zeus"@it, "Ζεύς"@el` (dai nomi di Wikidata) |
| Letterali tipati | `geo:lat 37.6^^xsd:decimal`, `"0"^^xsd:nonNegativeInteger` |
| Statement di Wikidata (simile alla reificazione) | `data/raw/wikidata.ttl`: ogni affermazione è un nodo con valore, rango e fonte (`prov:wasDerivedFrom`) |
| Blank node | restrizioni anonime, nodi riferimento di Wikidata |
| **Named graph** | un grafo per fonte (`g:hesiod`...), per livello di inferenza, per vista, per conflitti |

## Lezioni 5-6 — Serializzazioni, contenitori, Linked Data

| Concetto | Nel progetto |
|---|---|
| Turtle / TriG / N-Triples | sorgenti / `mythograph.trig` / input per HermiT |
| `rdf:List` | `owl:unionOf ( … )`, `owl:propertyChainAxiom ( … )`, corpo e testa delle regole SWRL |
| Wikidata, DBpedia | **tutti i dati** vengono da Wikidata (`docs/pipeline.md`) |

## Lezioni 7-8 — SPARQL

| Concetto | Nel progetto |
|---|---|
| SELECT verso un endpoint remoto | `pipeline/extract/*.rq`, eseguite su query.wikidata.org |
| **CONSTRUCT per convertire vocabolari** | `pipeline/mapping/*.rq`: Wikidata → MythoGraph |
| **CONSTRUCT come regola** | `ontology/rules/*.rq` più le regole SWRL tradotte in automatico |
| Property path | `prov:wasDerivedFrom/pr:P248/map:inGraph`, `wdt:P279*` |
| `FILTER NOT EXISTS` | scegliere la classe più specifica (`04_types.rq`) |
| `GRAPH ?g`, `GROUP BY`/`HAVING`, `UNION` | CQ1, CQ2, CQ8 |
| `SERVICE` (federazione) | `queries/federated_wikidata.rq` |

## Lezioni 9-10 — RDFS

| Concetto | Regola / file |
|---|---|
| `rdfs:subClassOf`, `subPropertyOf` | `rules/01_subclass.rq`, `rules/02_subproperty.rq` — `hasFather ⊑ hasParent ⊑ hasAncestor` |
| `rdfs:domain` / `range` **inferiscono** | `rules/03_domain.rq`, `04_range.rq`: il mapping non scrive che Troia è un luogo, lo deduce il range di `diedIn` |

## Lezioni 11-12 e parti II–III — OWL, DL, SWRL

| Concetto | Nel progetto |
|---|---|
| `inverseOf`, `SymmetricProperty`, `TransitiveProperty` | `hasParent`/`hasChild`, `hasSpouse`, `hasAncestor` |
| `AsymmetricProperty`, `IrreflexiveProperty` | `hasParent`, `hasChild`, `hasSpouse`, `hasSibling` |
| `FunctionalProperty` | `hasFather`, `hasMother`, solo nel modulo `constraints.ttl` |
| **Classi definite** (`equivalentClass`) | `Demigod`, `Hero`, `Ruler`, `Olympian`, `Nereid`, `Deceased`, `RealPlace`, `Kinslayer`, `Parricide`, `OedipalFigure`... (tabella in `docs/protege.md`) |
| `someValuesFrom`, `hasValue`, `oneOf` | `Demigod`, `Olympian`, `HomericCharacter`, i figli di Tifone ed Echidna |
| Unione | `Deceased ≡ ∃diedIn.Place ⊔ ∃mannerOfDeath.MannerOfDeath` |
| Cardinalità | `Character ⊑ ≤2 hasParent`, `Immortal ⊑ ≤0 killedBy` (vincoli per fonte) |
| GCI (assioma generale) | `∃hasFather.Mortal ⊓ ∃hasMother.Mortal ⊑ Mortal`; `Creature ⊓ ∃hasParent.{Typhon, Echidna} ⊑ Monster` |
| Disgiunzione e copertura | `Immortal ⊥ Mortal`, `Character ⊑ Immortal ⊔ Mortal` |
| **Ragionamento per casi** (solo DL) | ucciso ⇒ non immortale ⇒ mortale: HermiT sì, OWL RL no |
| Catene di proprietà | `hasGrandparent`, `hasParentSibling`, `rulesOver = holdsTitle ∘ titleOver` |
| **SWRL** | `ontology/rules.ttl`: 11 regole (parricidio, nozze tra consanguinei, zii...) |
| Classificazione della TBox | HermiT mette `Parricide` sotto `Kinslayer` senza che sia scritto |
| Consistenza | ogni fonte coerente; fusione ingenua no; fonti che si contraddicono da sole (CQ12) |
| Ontologie fondazionali | `alignments.ttl`: CIDOC CRM, FaBiO, FOAF, Dublin Core |
| Modularità, `owl:imports` | core, constraints, rules, alignments + `catalog-v001.xml` |

---

## Le scelte da saper difendere

**Perché un named graph per fonte?** Le fonti si contraddicono. Con un solo padre per
fonte, fondendole il reasoner dovrebbe dedurre `Urano owl:sameAs Zeus`, in conflitto
con `owl:AllDifferent`: inconsistente, e da un'ontologia inconsistente segue qualunque
cosa. Separate, ognuna è coerente e le query le **confrontano** (CQ1, CQ2).

**Perché i vincoli in un modulo a parte?** "Un solo padre" vale dentro una versione del
mito. `g:wikidata` raccoglie tutte le versioni: lì il vincolo non si applica, e le
varianti diventano dati da interrogare invece che errori.

**Perché SWRL?** OWL non sa intersecare due proprietà sugli stessi individui: "x ha ucciso
y **e** y è un antenato di x" non si esprime. Una regola SWRL sì.

**Perché i fratelli con una regola e non con una catena?** `hasParent ∘ hasChild`
renderebbe ognuno fratello di se stesso. Serve `differentFrom(?x, ?y)` nella regola.

**Cosa succede quando Wikidata è incoerente?** Il controllo di qualità della build mette da
parte le affermazioni coinvolte (grafo `conflicts/…`) e le segnala. Esempi veri:
- **Echidna** per Wikidata è una dea, ma muore uccisa da Argo: divina e mortale insieme;
- **Apollodoro** dà a Tindaro due padri, Ebalo e Periere;
- **Esiodo** dà a Urano due madri, Gea ed Emera.

**Perché solo 300 personaggi?** La selezione parte da dieci cicli mitici
(`pipeline/tables/cycles.ttl`), scelti per le deduzioni che portano, e prende da
Wikidata famiglie e genealogie complete. Conta la qualità del modello, non la quantità
di triple: ogni personaggio presente serve a una competency question o a una deduzione.
