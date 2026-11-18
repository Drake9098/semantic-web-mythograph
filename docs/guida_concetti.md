# Guida ai concetti: dalla teoria al progetto

Per ogni argomento delle lezioni 1–12 trovi **dove è applicato** in MythoGraph e
**come spiegarlo**. Studia le slide tenendo aperto il file indicato: ogni
concetto ha un esempio concreto nel tuo progetto.

---

## Lezione 1 — Perché il Semantic Web

| Concetto | Nel progetto | Come spiegarlo |
|---|---|---|
| Web di dati, non di documenti | Ogni personaggio è un IRI (`res:Zeus`), le relazioni sono triple | "Non ho pagine su Zeus, ho dati su Zeus che una macchina può combinare." |
| **AAA** (Anyone can say Anything about Any topic) | Esiodo e Omero dicono cose diverse su Afrodite: `data/sources/hesiod.ttl` vs `homer.ttl` | "Le fonti antiche sono come il Web: ognuno dice la sua. Il progetto mostra come conviverci." |
| **Open World Assumption** | In Esiodo Efesto *non ha padre*: non basta non scriverlo, va **negato esplicitamente** con `maxCardinality 0` (`hesiod.ttl`, sezione Efesto) | "Se un'informazione manca non è falsa, è sconosciuta. Per dire 'non ha padre' devo scriverlo." |
| **Non unique naming** | `owl:AllDifferent` generato in `build.py` (`unique_names`) | "Due IRI diversi possono indicare la stessa cosa. Io dichiaro che i miei personaggi sono tutti distinti: senza questo il reasoner dedurrebbe Zeus = Urano invece di segnalare il conflitto." |

## Lezione 2 — Ontologie, DB vs KB, logica

| Concetto | Nel progetto |
|---|---|
| Ontologia = specifica formale ed esplicita di una concettualizzazione condivisa | `ontology/mythograph.ttl` (TBox) separata dai fatti (ABox in `data/`) |
| Concetti = predicati unari, relazioni = predicati binari | Classi (`myth:Deity`) e proprietà (`myth:hasParent`) |
| Tassonomia come spina dorsale | Gerarchia `Character → Deity → Olympian…` |
| Inferenza logica (prof → faculty → staff) | `Olympian ⊑ Deity ⊑ Character`: Zeus è dichiarato Olympian, il resto è dedotto (badge "REGOLA" nella scheda) |
| Tripla = cella di una tabella distribuita (riga, colonna, valore) | Ogni affermazione è soggetto/predicato/oggetto |

## Lezione 3 — Merge di grafi, URI, namespace

| Concetto | Nel progetto |
|---|---|
| Merge di grafi = unione delle triple | La **fusione ingenua** in `build.py` unisce tutte le fonti… e diventa inconsistente (scheda *Fonti* della UI) |
| URI come identità globale | `https://example.org/mythograph/resource/Zeus` |
| CURIE / prefissi | `myth:` (TBox), `res:` (individui), `g:` (named graph), `dcterms:`, `skos:` |
| Namespace standard rdf/rdfs/owl | Usati in tutti i file `.ttl` |
| `owl:sameAs` | Tre usi diversi: **(1)** tra Zeus e Giove *non* in `shared.ttl` (lì c'è solo `myth:romanCounterpart`); **(2)** *solo* nel grafo di Ovidio (`ovid.ttl`), che identifica esplicitamente Venere con Afrodite: il named graph limita la portata dell'identità; **(3)** verso Wikidata e DBpedia in `data/links.ttl` |

## Lezione 4 — Letterali, reificazione, blank node, named graph

| Concetto | Nel progetto |
|---|---|
| Letterali con tag di lingua | `rdfs:label "Zeus"@it, "Ζεύς"@grc` in `shared.ttl` |
| Letterali tipati | `myth:composedAround -700` (xsd:integer), `"0"^^xsd:nonNegativeInteger` |
| **Reificazione** (`rdf:Statement`) | `:claim_hes_aphrodite_father` in `hesiod.ttl`: "la Teogonia vv. 188-206 afferma che Urano è padre di Afrodite". CQ7 |
| Valori strutturati | Il passo (`myth:Passage`) è una risorsa con opera + locus |
| Blank node | Le restrizioni anonime (`[ a owl:Restriction ; … ]`) sono blank node |
| **Named graph** | Il cuore del progetto: un grafo per fonte, per livello di inferenza, per vista |

## Lezioni 5-6 — Serializzazioni, contenitori, DBpedia

| Concetto | Nel progetto |
|---|---|
| Turtle | Tutti i file sorgente |
| TriG (Turtle + named graph) | `data/generated/mythograph.trig` |
| N-Triples | Formato usato per passare i dati a HermiT (`reasoning.py`) |
| Collezioni `rdf:List` | `owl:AllDifferent ( … )`, `owl:unionOf ( … )`, `owl:propertyChainAxiom ( … )` |
| DBpedia / Wikidata | `data/links.ttl`: 150 risorse collegate a Wikidata e DBpedia con `owl:sameAs`, coordinate dei luoghi (vocabolario W3C Basic Geo) |

## Lezioni 7-8 — SPARQL

| Concetto | Nel progetto |
|---|---|
| SELECT, graph pattern, variabili | `queries/cq*.rq`, scheda *Domande* della UI |
| FILTER | CQ2 (`FILTER(?valore1 != ?valore2)`), regola fratelli |
| DISTINCT, ORDER BY | quasi tutte le CQ |
| GROUP BY / HAVING / COUNT | CQ8 (personaggi presenti in più fonti) |
| `GRAPH ?g { … }` | tutte le CQ: interrogare una fonte o confrontarne due |
| Property path | `rdfs:subClassOf+`, `myth:identifiedWith?/myth:locatedIn*` (CQ6) |
| **CONSTRUCT come regola** | `ontology/rules/*.rq`: le stesse regole delle lezioni (hasUncle, subClassOf, domain…) |
| UNION | CQ2, regola zio/zia |
| **Query federate SERVICE** | `queries/federated_wikidata.rq`, eseguita da `enrich.py`: il blocco `SERVICE` va all'endpoint di Wikidata (coordinate, pagina Wikipedia), il resto gira sul nostro grafo (join con `owl:sameAs`). Alimenta la **mappa** |

## Lezioni 9-10 — RDFS

| Concetto | Regola / file |
|---|---|
| `rdfs:subClassOf` | `rules/01_subclass.rq` |
| `rdfs:subPropertyOf` (trasferimento di proprietà) | `rules/02_subproperty.rq` — `hasFather ⊑ hasParent ⊑ hasAncestor` |
| `rdfs:domain` classifica il soggetto | `rules/03_domain.rq` — chi ha `rulesOver` è un Character |
| `rdfs:range` classifica l'oggetto (esempio navi → Captain) | `rules/04_range.rq` — chi è `hasFather` di qualcuno è **Male** |
| Domain/range **non validano**, inferiscono | Esempio: se scrivo `X hasFather Gea` il reasoner deduce Gea Male → conflitto con Female (disgiunte) |
| Union pattern / conciliazione di termini | Ovidio usa i nomi romani: `romanCounterpart` (debole, ovunque) + `owl:sameAs` (forte, solo nel suo grafo). CQ1 e CQ2 confrontano le tre fonti usando i nomi greci |
| `rdfs:label` | etichette multilingue, mostrate nella UI |

## Lezioni 11-12 — Verso OWL, OntoComedySources

| Concetto | Nel progetto |
|---|---|
| `owl:inverseOf` | `hasParent`/`hasChild`, `killed`/`killedBy` — `rules/05_inverse.rq` |
| `owl:SymmetricProperty` | `hasSpouse`, `hasSibling`, `romanCounterpart` — `rules/06_symmetric.rq` |
| `owl:TransitiveProperty` | `hasAncestor`, `locatedIn` — `rules/07_transitive.rq` |
| `owl:equivalentClass` | classi definite `Demigod`, `Hero`, `Ruler` |
| Ontologie fondazionali (CIDOC, DC, SPAR) | `ontology/alignments.ttl`: Evento ⊑ `crm:E5_Event`, Luogo ⊑ `crm:E53_Place`, Opera ⊑ `fabio:Work`, Personaggio ⊑ `crm:E28_Conceptual_Object` (un personaggio mitico non è una persona storica), `setIn` ⊑ `crm:P7_took_place_at`… Si usa subClassOf e non equivalentClass |
| Fonti e frammenti come in OntoComedySources | `myth:LiteraryWork`, `myth:Passage` con `myth:locus` |

## Oltre la lezione 12 (parti II–III del programma)

| Concetto | Nel progetto |
|---|---|
| Restrizioni `someValuesFrom` | `Demigod ≡ Human ⊓ ∃hasParent.Deity` |
| `allValuesFrom` | `Human ⊑ ∀hasParent.(Deity ⊔ Human)` |
| `hasValue` | `Olympian ⊑ ∃residesIn.{MountOlympus}` |
| Cardinalità | `Character ⊑ ≤2 hasParent`, `Immortal ⊑ ≤0 killedBy` |
| Proprietà funzionali | `hasFather`, `hasMother` |
| Disgiunzione | `Immortal ⊥ Mortal`, `Male ⊥ Female`, `RealPlace ⊥ MythicalPlace` |
| Copertura (unione a destra) | `Character ⊑ Immortal ⊔ Mortal` |
| **Ragionamento per casi (solo DL)** | Idra, leone di Nemea e Gerione sono uccisi da Eracle ⇒ non possono essere Immortal ⇒ HermiT deduce che sono **Mortal**. OWL RL e le regole non ci arrivano: è il badge viola "HermiT" nella scheda dell'Idra |
| Catene di proprietà | `hasParent ∘ hasSibling ⊑ hasParentSibling` |
| Consistenza / insoddisfacibilità | Fusione ingenua inconsistente (scheda *Fonti*) |
| OWL 2 RL vs DL | `owlrl` (regole, polinomiale) vs HermiT (tableau, completo) in `reasoning.py` |

---

## La scelta di progetto da saper difendere

**Perché un named graph per fonte?** Perché le fonti si contraddicono. Fondendole,
le proprietà funzionali (`hasFather`) costringono il reasoner a dedurre
`Urano owl:sameAs Zeus`. Questo è in conflitto con `owl:AllDifferent`, quindi
l'ontologia è inconsistente. E da un'ontologia inconsistente si deduce qualunque
cosa. Separando le fonti, ognuna resta consistente e le query possono
**confrontarle** (CQ1, CQ2).

**Perché non owl:sameAs tra Zeus e Giove?** `sameAs` fonde *tutte* le proprietà:
Giove erediterebbe ogni affermazione greca su Zeus e viceversa. Le due figure si
somigliano ma non sono la stessa risorsa.

**Perché fratelli con una regola e non con una catena?** La catena
`hasParent ∘ hasChild` renderebbe ognuno fratello di se stesso. In SPARQL basta
`FILTER(?x != ?y)`, che OWL non può esprimere in una catena.
