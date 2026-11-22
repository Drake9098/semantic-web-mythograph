# MythoGraph in Protégé

Guida per aprire l'ontologia in Protégé e mostrare cosa sa fare.

## Quali file aprire

| File | Cosa contiene | Quando usarlo |
|---|---|---|
| **`exports/mythograph-wikidata.ttl`** | schema + regole + i 303 personaggi dei cicli mitici, con tutte le versioni | **il file principale**: HermiT classifica in circa 6 secondi, ci sono tutte le deduzioni |
| `ontology/mythograph.ttl` | solo lo schema (modulo core) | per far vedere classi, proprietà e assiomi |
| `ontology/rules.ttl` | le regole SWRL; importa il core | per la scheda SWRL |
| `ontology/constraints.ttl` | i vincoli per singola fonte; importa il core | per spiegare i grafi per fonte |
| `exports/mythograph-hesiod.ttl` (e le altre fonti) | schema + regole + vincoli + personaggi di una fonte | ragionamento per fonte, con i vincoli (meno di 2 secondi) |
| `exports/mythograph-merged-naive.ttl` | le fonti antiche fuse, con i vincoli di una fonte sola | far vedere l'inconsistenza (risposta immediata) |

Tempi misurati con HermiT 1.4 (lo stesso di Protégé 5.6.9) sul portatile del progetto.

I moduli in `ontology/` si importano a vicenda con `owl:imports`. Protégé trova i file
grazie a `ontology/catalog-v001.xml`, quindi nessun download. I file in `exports/` invece
sono completi da soli: li genera `python -m mythograph.build`.

Per aprirli: **File > Open...**, scegli il file. Se Protégé chiede il formato, è Turtle.

## Cosa mostrare, in ordine

### 1. La gerarchia delle classi
Scheda **Entities > Classes**. Le classi con il simbolo ≡ sono **definite**: hanno
condizioni necessarie e sufficienti (*Equivalent To*), non solo una superclasse.

| Classe | Definizione (*Equivalent To*) |
|---|---|
| `Demigod` | `Mortal and (hasParent some Deity)` |
| `Hero` | `Mortal and (killed some Monster)` |
| `Ruler` | `Character and (holdsTitle some RoyalTitle)` |
| `Olympian` | `Deity and (memberOf value TwelveOlympians)` |
| `Nereid`, `Muse`, `Gorgon` | `memberOf value Nereids` (e così via) |
| `Deceased` | `(diedIn some Place) or (mannerOfDeath some MannerOfDeath)` |
| `RealPlace` | `Place and (geo:lat some xsd:decimal)` |
| `HomericCharacter` | `Character and (appearsIn some {Iliad, Odyssey})` |
| `Kinslayer` | `Character and (killedRelative some Character)` |
| `Parricide` | `Character and (killedAncestor some Character)` |
| `ConsanguineousSpouse` | `Character and (marriedRelative some Character)` |
| `OedipalFigure` | `Parricide and (marriedAncestor some Character)` |

Altri assiomi da indicare:
- `Immortal` e `Mortal` sono **disgiunte**, e ogni `Character` è l'una o l'altra
  (*SubClass Of*: `Immortal or Mortal`, un assioma di copertura).
- Nel modulo dei vincoli `Immortal` ha *SubClass Of* `killedBy max 0`: dentro una fonte un
  immortale non viene ucciso. In Wikidata, che mescola le versioni, Asclepio è un dio e
  Zeus lo uccide: per questo il vincolo non sta nel core.
- **Assioma generale** (General Class Axiom, menu *Window > Views > Class views*):
  `(hasFather some Mortal) and (hasMother some Mortal) SubClassOf Mortal`.
  A sinistra c'è un'espressione, non una classe con nome: è una GCI. L'inverso ("figli di
  due dei sono dei") l'ho tolto perché il mito stesso lo smentisce: Narciso è figlio di un
  dio fluviale e di una ninfa, ma è mortale.
- Seconda GCI: `Creature and (hasParent some {Typhon, Echidna}) SubClassOf Monster`.
  Per Wikidata il Leone di Nemea e la Chimera sono "animali mitici", non mostri: li fa
  diventare mostri la genealogia di Esiodo, che fa di Tifone ed Echidna i genitori dei
  mostri. Usa anche un'enumerazione (`oneOf`). Così Teseo ed Eracle risultano eroi.

### 2. Le proprietà
Scheda **Object properties**. Nel riquadro *Characteristics* si vedono:
- `hasAncestor`, `hasDescendant`: **transitive**;
- `hasSpouse`, `hasSibling`: **simmetriche**; `hasSpouse` e `hasSibling` anche **irriflessive**;
- `hasParent`, `hasChild`: **asimmetriche** e **irriflessive**;
- `hasFather`, `hasMother`: **funzionali**, ma solo aprendo `constraints.ttl` o un file di una fonte;
- inverse: `hasParent`/`hasChild`, `killed`/`killedBy`, `hasAncestor`/`hasDescendant`;
- **catene di proprietà** (*SubProperty Of (Chain)*):
  `hasGrandparent = hasParent o hasParent`, `hasParentSibling = hasParent o hasSibling`,
  `rulesOver = holdsTitle o titleOver`;
- gerarchie: `hasFather ⊑ hasParent ⊑ hasAncestor`; `killedAncestor ⊑ killedRelative ⊑ killed`.

### 3. Le regole SWRL
**Window > Tabs > SWRLTab**, oppure la vista *Rules*. Sono undici regole, con il nome in italiano:

```
padre:            hasParent(?x,?p) ^ Male(?p) -> hasFather(?x,?p)
madre:            hasParent(?x,?p) ^ Female(?p) -> hasMother(?x,?p)
fratelli:         hasParent(?x,?p) ^ hasParent(?y,?p) ^ differentFrom(?x,?y) -> hasSibling(?x,?y)
zio / zia:        hasParentSibling(?x,?u) ^ Male(?u) -> hasUncle(?x,?u)
parricidio:       killed(?x,?y) ^ hasAncestor(?x,?y) -> killedAncestor(?x,?y)
figlicidio, fratricidio, uxoricidio: lo stesso con hasDescendant, hasSibling, hasSpouse
nozze tra fratelli:     hasSpouse(?x,?y) ^ hasSibling(?x,?y) -> marriedSibling(?x,?y)
nozze con un antenato:  hasSpouse(?x,?y) ^ hasAncestor(?x,?y) -> marriedAncestor(?x,?y)
```

Perché servono: OWL non sa dire "x ha ucciso y **e** y è un antenato di x". Ci vorrebbe
l'intersezione di due proprietà sugli stessi due individui, e OWL non ce l'ha.

### 4. Il ragionatore
**Reasoner > HermiT > Start reasoner** (Ctrl+R). Poi:
- **Classi, vista *Inferred***: `Parricide` finisce sotto `Kinslayer` e `OedipalFigure`
  sotto `ConsanguineousSpouse`, anche se nessuno l'ha scritto. HermiT lo ricava dalle
  definizioni e dalla gerarchia delle proprietà (ragionamento sulla TBox).
- **Individui**: scegli `Oedipus`. Le righe con lo sfondo giallo sono dedotte:
  tipi `Parricide`, `ConsanguineousSpouse`, `OedipalFigure`; proprietà `killedAncestor Laius`,
  `marriedAncestor Jocasta`, `hasAncestor Labdacus`...
- **Spiegazioni**: accanto a ogni riga dedotta c'è un **?**. Cliccandolo Protégé mostra
  gli assiomi che la giustificano. È la domanda più probabile all'esame: "perché lo deduce?".

### 5. La catena più bella: Achille semidio
Individuo `Achilles`. Wikidata non dice né che è mortale né che è un semidio:
1. `Achilles diedIn Troy`, quindi `Deceased` (definizione con *or*), quindi `Mortal`;
2. la madre `Thetis` non è dichiarata dea, ma è `memberOf Nereids`: per la definizione
   è una `Nereid`, quindi `Nymph`, quindi `Deity`;
3. mortale con un genitore divino, quindi `Demigod`.

Nei file delle singole fonti (che includono i vincoli) c'è anche la strada per casi:
`killedBy` qualcuno, un immortale ha `killedBy max 0`, ogni personaggio è immortale
o mortale, quindi è mortale. Questa la fa solo HermiT, OWL RL no.

### 5b. Cassifone, tre deduzioni da due fatti
Individuo `Cassiphone`. Wikidata dice solo che è figlia di Odisseo e Circe, che ha
sposato Telemaco e che lo ha ucciso. Telemaco è figlio di Odisseo e Penelope, quindi:
1. la regola *fratelli* (genitore in comune, `differentFrom`) dà `hasSibling Telemachus`;
2. *nozze tra fratelli* dà `marriedSibling`, *fratricidio* `killedSibling`,
   *uxoricidio* `killedSpouse`;
3. le classi definite la mettono in `Kinslayer` e `ConsanguineousSpouse`.

Simile **Teseo**: uccide Sinis, Scirone e Perifete, che come lui sono figli di Poseidone.
Il ragionatore scopre da solo che sono suoi fratellastri.

### 6. DL Query
Scheda **DL Query** (con il ragionatore attivo). Query da provare:

```
Demigod
Mortal and hasParent some Olympian
hasAncestor value Uranus
killed some Monster
Ruler and rulesOver value Mycenae
Character and hasSpouse some (hasSibling some Character)
```

### 7. L'inconsistenza
Apri `exports/mythograph-merged-naive.ttl` e avvia HermiT: Protégé segnala che l'ontologia è
**inconsistente**. Con *Explain* si vede il motivo: due fonti danno padri diversi allo stesso
personaggio, `hasFather` è funzionale e i due padri sono dichiarati diversi (`AllDifferent`).
Nei file delle singole fonti questo non succede: è il motivo dei named graph separati.

### 8. Il grafo
**Window > Tabs > OntoGraf**: trascina una classe o un individuo nel riquadro per vedere
i collegamenti. Con *Entities > Individuals by class* si scelgono i personaggi da mostrare.
