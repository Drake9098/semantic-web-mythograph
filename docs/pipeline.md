# Come è costruito il grafo: la pipeline

Nessun fatto è scritto a mano. Personaggi, parentele, uccisioni, titoli e luoghi
vengono da **Wikidata**, e le fonti antiche da cui dipendono vengono dai
**riferimenti** che Wikidata attacca a ogni affermazione (proprietà P248, *stated in*).
A mano ci sono solo lo **schema** (l'ontologia), tre **tabelle di corrispondenza**
tra il vocabolario di Wikidata e il nostro, e l'elenco dei **cicli mitici** da cui parte
la selezione dei personaggi.

```
 Wikidata (SPARQL)                                                          Protégé
      │                                                                        ▲
 ① estrazione ──► ② lifting ──► ③ mapping (CONSTRUCT) ──► ④ ragionamento ──► ⑤ export
  extract.py       lift.py        mapping.py                 build.py           exports/
  data/raw/*.json  data/raw/      data/mapped/               data/generated/
                   wikidata.ttl   shared.ttl, sources/       mythograph.trig
```

Comandi, nell'ordine (ognuno legge l'output del precedente):

```
python -m mythograph.extract    # scarica da Wikidata (solo se data/raw/ è vuota; --refresh per riscaricare)
python -m mythograph.lift       # JSON -> RDF nel modello di Wikidata
python -m mythograph.mapping    # CONSTRUCT: Wikidata -> MythoGraph, un grafo per fonte
python -m mythograph.build      # ragionamento per fonte, TriG, file per Protégé
```

I file intermedi sono tutti salvati nel repository: si può far vedere ogni passo.

---

## ① Estrazione — `src/mythograph/extract.py`, query in `pipeline/extract/`

Query **SELECT** all'endpoint pubblico `https://query.wikidata.org/sparql`. Le risposte
JSON finiscono in `data/raw/`, quindi la build funziona anche senza rete.

| Query | Cosa chiede | Risultato |
|---|---|---|
| `00_classes.rq` | le classi della mitologia greca con tutte le sottoclassi (`wdt:P279*`) | `00_classes.json` |
| `01_characters.rq` | i personaggi istanza di quelle classi **con almeno una parentela** | 4.386 personaggi |
| `02_statements.rq` | le loro affermazioni nel **modello completo**: valore, rango, opera citata | 27.674 righe |
| `04_entities.rq` | le entità citate: luoghi (coordinate), titoli (giurisdizione), opere (autore) | |
| `03_labels.rq` | nomi in it/en/el/grc/la, numero di voci Wikipedia, voce inglese | |
| `05_superclasses.rq` | per ogni classe usata, a quale classe della tabella appartiene (`P279*`) | |

Due dettagli:
- Le query lunghe vanno **a blocchi** di 150 personaggi (`VALUES ?item { ... }`), con
  una pausa tra un blocco e l'altro. Se l'endpoint risponde 429/502/timeout, si ritenta.
- `02_statements.rq` non usa le scorciatoie `wdt:`, che danno solo il valore "migliore".
  Usa i **nodi affermazione** `p:`/`ps:`, che portano anche il **rango** e il
  **riferimento**. Senza, non si saprebbe chi dice cosa.

```sparql
?item ?prop ?st .                                   # p:P22  -> nodo affermazione
?st ?ps ?value ; wikibase:rank ?rank .              # ps:P22 -> il padre
OPTIONAL { ?st prov:wasDerivedFrom/pr:P248 ?work }  # "stated in": l'opera antica
```

## ② Lifting — `src/mythograph/lift.py`

Il JSON diventa RDF (`data/raw/wikidata.ttl`, circa 127 mila triple) **senza interpretare
niente**: stesso vocabolario di Wikidata (`wd:`, `wdt:`, `p:`, `ps:`, `pr:`, `prov:`,
`wikibase:rank`). Per esempio, il padre di Afrodite secondo Apollodoro:

```turtle
wd:Q35500 p:P22 wds:Q35500-... .
wds:Q35500-... ps:P22 wd:Q34201 ;                       # Zeus
               wikibase:rank wikibase:NormalRank ;
               prov:wasDerivedFrom [ pr:P248 wd:Q817383 ] .   # Bibliotheca
```

Unica aggiunta: `map:key`, un nome leggibile ricavato dall'etichetta inglese, che
diventerà l'IRI (`res:Zeus` invece di `res:Q34201`). Se due entità hanno lo stesso nome,
la più nota (più voci Wikipedia) lo tiene e le altre prendono il QID: `res:Achilles` e
`res:Achilles_Q21547790`.

## ③ Mapping — `src/mythograph/mapping.py`, query in `pipeline/mapping/`

È la conversione di vocabolario vista a lezione: **CONSTRUCT** che leggono il grafo
grezzo e scrivono triple nel vocabolario `myth:`. Girano in ordine; la prima riga di
ogni file dice dove va il risultato. Le esegue rdflib, come negli esempi del corso:
`g += g.query(CONSTRUCT ...)`. Le query che restano nel grafo di lavoro si ripetono
finché non aggiungono niente (punto fisso), come le regole del ragionamento.

| Query | Destinazione | Cosa fa |
|---|---|---|
| `01_sources.rq` | lavoro | ogni opera citata va nel grafo del suo autore |
| `02_scope.rq` | lavoro | i protagonisti dei cicli e chi è legato a loro (vedi sotto) |
| `02b_ancestors.rq` | lavoro | i loro antenati, una generazione per volta fino ai primordiali |
| `03_characters.rq` | `shared` | IRI leggibile, nomi, `a myth:Character` |
| `04_types.rq` | `shared` | classi (P31) e genere (P21) con la tabella delle classi |
| `05_statements.rq` | **un grafo per fonte** | parentele, uccisioni, luoghi, titoli, gruppi, opere |
| `06_entities.rq` | `shared` | nomi e coordinate dei luoghi |
| `07_titles.rq` | `shared` | su quale luogo dà potere un titolo; quali titoli sono regali |
| `08_works.rq` | `shared` | le opere antiche e i loro autori |
| `09_links.rq` | `links` | `owl:sameAs` verso Wikidata e DBpedia |

### Quali personaggi: i cicli mitici

Wikidata ha migliaia di personaggi della mitologia greca, ma pochi partecipano alle
deduzioni interessanti. La selezione parte da `pipeline/tables/cycles.ttl`: quattordici
protagonisti di dieci cicli (Tebe, Atridi, Argo, Eracle, Atene, Troia, Odissea,
Argonauti, Corinto), ognuno scelto per le deduzioni che porta (Edipo per il parricidio,
Cassifone per le nozze con il fratellastro, Achille per il semidio...). Da lì:

1. `02_scope.rq` prende i protagonisti, i loro genitori, coniugi, chi hanno ucciso e
   chi li ha uccisi, e i figli **noti** (almeno 20 voci di Wikipedia: Eracle ha decine
   di figli minori);
2. `02b_ancestors.rq` aggiunge i genitori noti di chi è già dentro, e si ripete finché
   non trova nessuno di nuovo: così le genealogie risalgono intere fino a Caos e Gea.

Risultato: circa 300 personaggi, contro i 4.386 scaricati. Basta cambiare la tabella
per cambiare la selezione: i fatti restano tutti quelli di Wikidata.

### Le tabelle di corrispondenza (`pipeline/tables/`)

Sono configurazione, non dati: dicono *come* tradurre, non *che cosa*.

- **`classes.ttl`**: classe di Wikidata → classe nostra. Per esempio
  `wd:Q45713 map:toClass myth:Titan`. Vale anche per le sottoclassi ("dio della
  guerra" è sotto "divinità"), e si sceglie la più specifica: "semidio" è sotto
  "divinità" e sotto "creatura leggendaria", ma diventa solo `myth:Demigod`.
  Se Wikidata dà a un personaggio una classe da mortale e una da divinità o da creatura,
  vincono le seconde: il Leone di Nemea è "leone immaginario", che Wikidata mette sotto
  "essere umano immaginario", ma resta una creatura.
- **`properties.ttl`**: proprietà di Wikidata → proprietà nostra. Per esempio
  `wd:P22 map:toProperty myth:hasFather`, `wd:P157 map:toProperty myth:killedBy`.
- **`sources.ttl`**: autore antico → named graph. Per esempio `wd:Q44233 map:graph g:hesiod`.

### Un grafo per fonte

`05_statements.rq` gira una volta per ogni named graph, con `?graph` già fissato:

```sparql
FILTER(?graph = g:wikidata
       || EXISTS { ?st prov:wasDerivedFrom/pr:P248/map:inGraph ?graph })
```

- **`g:wikidata`** riceve tutte le affermazioni. È la tradizione nel suo insieme,
  con tutte le varianti: Afrodite ha due padri.
- **`g:hesiod`, `g:homer`, `g:apollodorus`, `g:pausanias`, `g:diodorus`, `g:herodotus`,
  `g:hyginus`, `g:apollonius`** ricevono solo le affermazioni che Wikidata attribuisce a
  un'opera di quell'autore (Teogonia, Iliade, Biblioteca...).

Il **tipo** di luoghi, titoli e gruppi non lo scrive il mapping: lo deduce il
ragionatore dal *range* della proprietà (`bornIn` ha range `Place`).

## ④ Ragionamento — `src/mythograph/build.py`, `src/mythograph/reasoning.py`

Ogni grafo si ragiona **da solo**, insieme all'ontologia e alle entità comuni:

| Grafo | Moduli dell'ontologia |
|---|---|
| fonti antiche | core + regole SWRL + allineamenti + **vincoli per fonte** + `owl:AllDifferent` |
| `g:wikidata` | core + regole SWRL + allineamenti (senza vincoli: contiene più versioni) |

Tre livelli, ognuno scrive solo le triple nuove nel suo grafo (`inferred/<fonte>/<livello>`),
così si sa sempre chi ha dedotto cosa:
1. **regole CONSTRUCT** (`ontology/rules/*.rq`) più le **regole SWRL** dell'ontologia,
   tradotte in automatico in CONSTRUCT (`swrl_to_sparql`), applicate finché non
   producono niente di nuovo;
2. **OWL 2 RL** con `owlrl`;
3. **OWL 2 DL** con **HermiT** (via owlready2): classi definite, ragionamento per casi.

### Il controllo di qualità
Prima di ragionare, la build controlla che ogni grafo sia **coerente**:
- se una fonte dà **due padri o due madri** allo stesso personaggio, si contraddice da sola
  (Esiodo: Urano è figlio di Gea, ma anche di Emera);
- se HermiT trova il grafo incoerente, `owlrl` dice quali personaggi sono coinvolti.

Le affermazioni coinvolte vanno nel grafo `conflicts/<fonte>`: **non si cancellano**,
si mettono da parte e si segnalano (CQ12, scheda Fonti). Il resto della fonte resta
utilizzabile.

## ⑤ Output

- `data/generated/mythograph.trig`: tutti i named graph, letti dall'interfaccia web.
- `exports/mythograph-<fonte>.ttl`: un file per fonte da aprire in **Protégé**
  (vedi `docs/protege.md`), senza inferenze: le calcola HermiT dentro Protégé.

## Perché così (domande probabili)

- **Perché non a mano?** Il mapping è ripetibile e verificabile: chiunque rilancia la
  pipeline ottiene lo stesso grafo, e ogni fatto ha l'indirizzo dell'affermazione di
  Wikidata da cui viene.
- **Perché CONSTRUCT e non Python?** Il mapping resta dichiarativo, in SPARQL: le regole
  di traduzione si leggono, non sono sepolte nel codice.
- **Perché tenere il modello completo di Wikidata?** Le scorciatoie `wdt:` danno un solo
  valore senza fonte; per i named graph serve sapere *chi* lo dice.
- **Perché i vincoli solo per fonte?** "Un solo padre" vale dentro una versione del mito,
  non per la tradizione intera. Applicato a tutte le versioni insieme rende l'ontologia
  inconsistente (`exports/mythograph-merged-naive.ttl`).
