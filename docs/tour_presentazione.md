# Tour della presentazione (revisione del 19/11)

Obiettivo: far vedere che il progetto l'ho capito io. Spiegazione a grandi linee,
quasi tutta nell'interfaccia, un solo file e una sola query. Circa 10 minuti.

## Prima di entrare

- Doppio clic su `avvia.bat`: si apre il browser su http://localhost:8000.
- Fonte: **Tutte le fonti**, Vista: **Vicinato**.
- Editor aperto su `ontology/mythograph.ttl`, sezione delle proprietà di parentela.
- Internet collegato (serve solo allo sfondo della mappa).

---

## 1. L'idea (30 s)
**Schermo:** l'interfaccia con Zeus al centro.

> Ho trasformato la mitologia greca in un grafo di conoscenza. Il punto
> interessante è che le fonti antiche si contraddicono, come i dati sul Web:
> chiunque può dire qualunque cosa. Il progetto mostra come il Semantic Web
> gestisce questa situazione.

## 2. Il problema: Afrodite (1,5 min)
**Schermo:** cerco **Afrodite**. Indico gli archi rossi e il riquadro
"Versioni in disaccordo".

> Per Esiodo nasce dalla spuma del mare, figlia di Urano e senza madre. Per
> Omero è figlia di Zeus e di Dione. Archi arancioni = Esiodo, blu = Omero,
> rossi = contestati.

## 3. La soluzione: un named graph per fonte (1,5 min)
**Schermo:** Fonte → Esiodo, poi Omero (il grafo cambia). Poi la scheda **Fonti**.

> Ogni fonte è un named graph separato, come un quaderno per ogni narratore.
> Da sola ogni fonte è coerente. Se le metto tutte insieme diventa
> inconsistente: il padre ammette un solo valore, quindi dovrei concludere che
> Urano e Zeus sono la stessa persona, ma ho dichiarato che sono diversi.
> Per questo servono grafi separati.

## 4. Dove stanno le regole (1,5 min)
**Schermo:** l'editor su `mythograph.ttl` (`hasFather`, `hasParent`,
`hasAncestor`, `hasSpouse`). Pochi secondi, poi torno all'interfaccia.

> Scrivo due cose. Qui le regole del mondo: il padre è un genitore, genitore e
> figlio sono inversi, l'antenato del mio antenato è mio antenato, se A sposa B
> allora B sposa A. Nei file delle fonti ci sono solo i fatti, tipo "Eracle ha
> padre Zeus". Il ragionatore applica le regole ai fatti e deduce il resto.

## 5. La deduzione: Eracle (2 min) ⭐
**Schermo:**
1. Cerco **Eracle**, Vista → **Albero genealogico**.
2. Nella scheda: **Semidio** ed **Eroe** con l'etichetta OWL RL.
3. Tolgo la spunta **inferite** → resta un semplice umano. La rimetto.
4. (facoltativo) Cerco **Idra di Lerna** → *Mortale* con l'etichetta HermiT.

> Nelle fonti c'è solo che Eracle è figlio di Zeus e Alcmena. L'albero fino a
> Urano e Gea l'ha dedotto il sistema. Nessuna fonte dice che è un semidio: lo
> deduco io con una definizione, umano con almeno un genitore divino. Se spengo
> le deduzioni resta un umano.
> Con un ragionatore più potente vado oltre: gli immortali non si possono
> uccidere, Eracle ha ucciso l'Idra, quindi l'Idra è mortale.

## 6. Una query: i semidei (1,5 min)
**Schermo:** scheda **Domande** → CQ4 → Esegui → "Spiegazione e query".

> Il progetto risponde a dieci domande scritte in SPARQL. Questa chiede, per ogni
> fonte, chi sono i semidei e chi è il loro genitore divino. Incrocia la classe
> dedotta, la parentela scritta nelle fonti e il tipo del genitore, fonte per
> fonte.

Lettura della query, riga per riga:
1. per ogni fonte…
2. …dentro il suo grafo…
3. …chi è un Semidio (dedotto, non scritto)…
4. …e chi è suo genitore…
5. …purché il genitore sia una divinità.

## 7. Ovidio, la Sicilia, Wikidata (1 min)
**Schermo:** Fonte → Ovidio, cerco **Persefone** (padre Zeus, madre Demetra).
Poi Vista → **Mappa dei luoghi**, zoom sulla Sicilia.

> Ovidio usa i nomi romani, Giove e Cerere. Solo nel suo grafo dichiaro che
> Giove è Zeus, così le sue storie si confrontano con le altre. Messo
> dappertutto fonderebbe tutto.
> Sulla mappa ci sono i miti siciliani: Proserpina a Enna, Tifeo sotto l'Etna,
> Polifemo. Le coordinate vengono da Wikidata con una query federata, e ogni
> personaggio è collegato a Wikidata e DBpedia.

## 8. Chiusura (30 s)

> Le fonti si contraddicono, quindi un named graph per ciascuna. Il ragionamento
> deduce antenati, semidei ed eroi che nessuno ha scritto. I dati sono collegati
> al Web tramite Wikidata. Per l'esame aggiungo Apollodoro e qualche regola.

---

## Se ho meno tempo

| Tempo | Tappe |
|---|---|
| 10 min | tutte |
| 5–6 min | 1, 2, 3, 5, 8 |
| 3 min | 1, 2, 5, 8 |

Il nucleo da non saltare: **Afrodite → Fonti → Eracle**.

## Domande probabili, risposta in una riga

- **Perché un grafo per fonte?** Fonderle rende l'ontologia inconsistente, e lo faccio vedere.
- **Reificazione o named graph?** Il named graph raggruppa tutta una fonte; la reificazione descrive una singola affermazione, per attaccarle il verso.
- **Da dove vengono i dati?** Dai testi: nessun dataset riporta le genealogie divise per fonte. Poi li ho collegati a Wikidata.
- **Dove usi CONSTRUCT?** Il primo livello di ragionamento sono regole CONSTRUCT, ripetute finché non aggiungono più niente.
- **Perché sameAs solo in Ovidio?** È lui a identificare Giove con Zeus; messo ovunque fonderebbe tutte le fonti.
- **Domain e range validano?** No, deducono: chi è padre di qualcuno viene classificato maschio.
- **Mondo aperto?** Efesto in Esiodo non ha padre: l'ho dovuto scrivere, altrimenti sarebbe solo "sconosciuto".

## Consigli

- Parlo alla prof, non allo schermo: clicco, mi giro, spiego.
- Se mi interrompe rispondo e riprendo dalla tappa dopo.
- Se qualcosa non va (internet, una vista), salto la tappa: il messaggio sta in 2, 3 e 5.
