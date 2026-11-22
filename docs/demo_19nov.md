# Presentazione del 19/11 — scaletta e domande probabili

> Versione del 19/11, prima della revisione: i dati ora vengono da Wikidata (vedi `docs/pipeline.md`).

## Prima di entrare
```bash
cd mythograph
.venv\Scripts\activate
python -m mythograph.build
uvicorn mythograph.web.app:app
```
Apri http://localhost:8000. Funziona offline (Cytoscape è salvato in locale).

---

## Scaletta (circa 8 minuti)

**1. L'idea, in una frase (30 s)**
"Ho trasformato la mitologia greca in un grafo di conoscenza. Il problema
interessante è che le fonti antiche si contraddicono, esattamente come succede
sul Web (AAA). Il progetto mostra come il Semantic Web gestisce questa situazione."

**2. L'ontologia (2 min)** — apri `ontology/mythograph.ttl`
- La gerarchia: Personaggio → Divinità → Olimpico…; Umano; Creatura.
- Le proprietà di parentela: `hasFather ⊑ hasParent ⊑ hasAncestor`, inverse,
  simmetriche, transitive, la catena per gli zii.
- Le classi definite: **Semidio ≡ Umano ⊓ ∃hasParent.Divinità**. Nessuno è
  dichiarato semidio.

**3. Le fonti come named graph (1,5 min)** — apri `data/sources/hesiod.ttl`, `homer.ttl`, `ovid.ttl`
- Afrodite: per Esiodo padre Urano e nessuna madre; per Omero Zeus e Dione.
- Efesto: per Esiodo nessun padre, *negato esplicitamente* per l'open world.
- Reificazione: `:claim_hes_aphrodite_father` con il passo "vv. 188-206".
- Ovidio usa i nomi romani: `Venere owl:sameAs Afrodite` **solo nel suo grafo**.
  In Esiodo e Omero Giove e Zeus restano distinti (in `shared.ttl` c'è solo
  `romanCounterpart`). Il named graph limita la portata dell'identità.

**4. Demo dell'interfaccia (3 min)**
1. Grafo con *Tutte le fonti*: archi arancio = Esiodo, blu = Omero, rossi = contestati.
2. Cerca **Afrodite** → scheda: due versioni in disaccordo e i fatti divisi per fonte,
   ognuno con il badge *asserita* / *regola* / *OWL RL*.
3. Cerca **Eracle**, poi Vista → **Albero genealogico**: antenati fino a Gea e Urano,
   tutti dedotti dalla transitività. Nella scheda, *Semidio* ed *Eroe* hanno il badge OWL RL.
   Togli la spunta **inferite**: Eracle torna "umano" e le classificazioni spariscono.
4. Tab **Domande** → CQ3 (antenati di Eracle: Crono, Gea, Urano… tutti dedotti),
   CQ4 (semidei), CQ6 (eventi in Sicilia: Polifemo, Scilla e Cariddi, le vacche del Sole).
5. Vista → **Mappa dei luoghi**: le coordinate vengono da Wikidata tramite la query
   federata `SERVICE` (`queries/federated_wikidata.rq`). In Sicilia: ratto di
   Proserpina a Enna, Tifeo sotto l'Etna, Aci e Galatea, Polifemo, Scilla e Cariddi.
   Nella scheda di un personaggio: link a Wikidata, DBpedia, Wikipedia.
6. Tab **Fonti** → ogni fonte è consistente, la **fusione ingenua no**. Le violazioni:
   hasFather funzionale ⇒ Urano = Zeus ⇒ (hasMother funzionale) Gea = Rea:
   l'errore si propaga a cascata, ma AllDifferent lo vieta.
7. Tab **SPARQL**: una query libera (es. i figli di Zeus per fonte).

**5. Ragionamento su tre livelli (1 min)** — `src/mythograph/reasoning.py`
- Regole SPARQL CONSTRUCT come nelle lezioni (`ontology/rules/`).
- OWL 2 RL con owlrl.
- OWL 2 DL con HermiT (consistenza e classificazione completa).
- **Esempio di cosa aggiunge HermiT**: cerca *Idra di Lerna* → classe *Mortale*
  con badge HermiT. Ragionamento per casi: ogni personaggio è Immortale o
  Mortale; gli immortali non possono essere uccisi; Eracle ha ucciso l'Idra ⇒
  è mortale. OWL RL non gestisce le unioni nella parte destra degli assiomi.

**6. Allineamento e linked data (30 s)** — `ontology/alignments.ttl`, `data/links.ttl`
Come OntoComedySources: eventi e luoghi agganciati a CIDOC CRM, opere a FaBiO.
Ogni personaggio collegato a Wikidata e DBpedia.

**7. Cosa manca, cioè il piano fino all'esame (30 s)**
Apollodoro (varianti reificate, 12 fatiche come `rdf:Seq`), regole SWRL,
il caso Eracle/apoteosi, relazione.

---

## Domande probabili e risposte

**Perché named graph e non un unico grafo?**
Un unico grafo con versioni contraddittorie è inconsistente: lo dimostra la fusione
ingenua. Con un grafo per fonte ogni versione resta consistente e posso
interrogarle singolarmente o confrontarle con `GRAPH ?g`.

**Che differenza c'è tra reificazione e named graph?**
Il named graph dà un nome a un *insieme* di triple, cioè tutta la versione di
Esiodo. La reificazione descrive *una singola* tripla come risorsa (`rdf:Statement`),
così posso attaccarle metadati come il passo esatto. Le uso entrambe.

**Perché domain e range non "validano"?**
In RDFS sono regole di inferenza, non vincoli. Se scrivo `X hasFather Gea`,
il reasoner non rifiuta la tripla: deduce che Gea è Male. Solo dopo, grazie alla
disgiunzione Male ⊥ Female, emerge l'inconsistenza.

**Open World Assumption: esempio?**
Esiodo non nomina il padre di Efesto. Questo non basta a dire che non ce l'ha:
l'ho dovuto affermare con `maxCardinality 0` su hasFather.

**Perché Zeus e Giove non sono owl:sameAs?**
`sameAs` fonde tutte le proprietà delle due risorse. Uso una proprietà simmetrica
dedicata, `romanCounterpart`.

**Differenza tra OWL RL e OWL DL?**
OWL RL è un profilo implementabile con regole, polinomiale ma incompleto (owlrl).
OWL DL è più espressivo e completo, con reasoner a tableau come HermiT, ma più
costoso. Nel progetto li uso in cascata. Esempio concreto: solo HermiT deduce che
l'Idra è mortale, perché serve ragionare per casi su `Immortal ⊔ Mortal`.

**Se le fonti sono in disaccordo, perché HermiT non si accorge di nulla?**
Perché lo eseguo fonte per fonte e ogni fonte è coerente. Sulla fusione ingenua
invece HermiT, esattamente come OWL RL, dice "inconsistente".

**Quante triple?** Circa 720 asserite nelle tre fonti, più circa 1.000 di entità
comuni e 400 di TBox. Le triple dedotte sono circa 6.000. Come suggerito, conta la struttura, non la quantità.

**Perché hasSibling non è una catena OWL?**
`hasParent ∘ hasChild` includerebbe la persona stessa. Serve `FILTER(?x != ?y)`
in una regola CONSTRUCT (o `differentFrom` in SWRL).

**Perché owl:sameAs tra Venere e Afrodite solo nel grafo di Ovidio?**
Perché è Ovidio a farla, quell'identificazione. Messa in `shared.ttl` varrebbe per
tutte le fonti e fonderebbe tutto: anche le affermazioni greche su Afrodite
diventerebbero affermazioni su Venere. Il named graph ne limita la portata.

**Come funziona la query federata?**
Il blocco `SERVICE <https://query.wikidata.org/sparql>` viene inviato a Wikidata,
che restituisce coordinate e pagine Wikipedia. Il join con le nostre risorse
(`?risorsa owl:sameAs ?wd`) avviene in locale. I risultati sono salvati in
`data/links.ttl`, così la demo funziona anche offline. La mappa di sfondo
(OpenStreetMap) richiede però internet.

**Come avete trovato gli identificativi Wikidata?**
Con una query SPARQL sulle etichette inglesi, scegliendo il candidato con la
descrizione coerente (es. "Greek goddess…") e più pagine Wikipedia collegate.
Una quindicina di casi ambigui (Poseidone/Nettuno, Tebe greca/egizia…) li ho
controllati e fissati a mano in `enrich.py` (OVERRIDES).
