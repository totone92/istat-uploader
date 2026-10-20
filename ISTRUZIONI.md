# Caricare i movimenti su Turismatica

Un programma che carica su Turismatica i movimenti giornalieri, uno per uno, al
posto tuo. Quello che facevi a mano trenta volte al mese.

Ti serve: il computer, SPID (o la carta d'identità elettronica) e cinque minuti.

---

## La prima volta

### 1. Apri il programma

Non c'è niente da installare: è **un file solo**. Salvalo dove vuoi — va
benissimo il Desktop.

La prima volta Windows scrive **«Windows ha protetto il PC»**. È normale:
succede a tutti i programmi nuovi che non sono famosi.

> Clicca su **«Ulteriori informazioni»** (la scritta piccola), poi su
> **«Esegui comunque»**.

### 2. Collega Turismatica

Premi **«Collega Turismatica»**. Si apre Google Chrome sul portale: premi
«Accedi» ed entra con SPID o CIE, come fai sempre.

> **Prenditi tutto il tempo che ti serve.** Il programma aspetta e basta, non
> scade. Il programma **non conosce le tue credenziali** e non le salva da
> nessuna parte.

Quando sei dentro il programma prosegue da solo (se non lo fa, premi **«Sono
dentro: vai»**). Legge le tue strutture e quali giorni hanno già il movimento.
Solo lettura: non tocca niente.

### 3. Controlla e conferma

Ti chiede se gestisci **una struttura o più** (la risposta giusta è già
proposta), poi ti mostra le strutture con i giorni: **verde** caricato,
**rosso** manca. Togli la spunta a quelle che non gestisci e premi
**Conferma**. Fatto: da adesso il programma si apre direttamente qui.

> Se il programma ti dice che non è riuscito a leggere le strutture, scrivi tu
> il numero di ognuna: lo trovi **nell'indirizzo** della pagina dei movimenti,
> dopo `idStruttura=` (per esempio `…movimentoospiti.xhtml?idStruttura=12345` →
> **12345**). Non è il numero di bed-and-breakfast.it. E manda a chi ti assiste
> il file `pagina-strutture-….html` che il programma ha salvato: è senza dati
> personali, e serve a sistemare la lettura.

---

## Ogni mese (cinque minuti)

1. **Scarica i file ISTAT del mese** dal tuo gestionale (con HostLab:
   **Report → ISTAT**). Ti viene giù un `.zip`: **non aprirlo**.
2. **Trascina lo zip** nel programma, nel riquadro tratteggiato (oppure
   «Scegli il file…»).
3. Il programma capisce da solo di quale struttura sono i file. Se non è
   chiaro **te lo chiede**: scegli la struttura, e lascia la spunta «Ricorda»
   così la prossima volta non lo chiede più.
4. Leggi il **piano**: «Settembre 2026, Casa Lavanda: 28 giorni già presenti, 2
   da caricare (12 e 19)».
5. In cima c'è una fascia. **Gialla = PROVA**: fa tutto ma **non carica
   niente**, e ti mostra cosa avrebbe caricato. Il programma si apre sempre
   così. Quando ti torna, premi **«Passa alla modalità vera…»** (diventa
   **rossa**), conferma, e avvia: ora carica davvero.
6. Rientri con SPID, e il programma lavora giorno per giorno. **Non toccare la
   finestra di Chrome** mentre lavora.
7. Alla fine leggi com'è andata. **«Copia tutto»** se vuoi mandarlo a qualcuno.

### La comunicazione mensile

Finito il mese, entro il **5 del mese dopo**, va fatta la comunicazione
telematica mensile. Nella schermata principale ogni struttura dice se il mese
risulta **comunicato** o **da comunicare**.

Il programma può farla per te come **ultimo passo** del giro: nel piano spunta
«Alla fine invia anche la comunicazione mensile». La invia solo se **tutti** i
giorni del mese risultano caricati, e solo in modalità vera con la conferma.

> ⚠️ Dopo la comunicazione **i dati del mese non si modificano più**. Spuntala
> quando sei sicuro che il mese è a posto.

---

## Domande che vengono a tutti

**Posso rilanciarlo sullo stesso mese?**
Sì. I giorni già caricati li salta, sempre. Non carica niente due volte.

**Ho aggiunto una struttura su Turismatica.**
Premi **«Aggiorna le mie strutture»**: rientri con SPID e la trova.

**Mi dice che manca il file di qualche giorno.**
Quel giorno non c'era nello zip. Riscarica il mese dal gestionale e rilancia.

**Mi dice che una struttura non è fra quelle del mio account.**
Il numero non corrisponde a nessuna struttura che puoi vedere con il tuo SPID.
Fai «Aggiorna le mie strutture» con lo SPID di chi gestisce quella struttura.

**Mi dice «Questo è lo zip di prova».**
È lo zip con i file inventati: serve solo in modalità prova. Per caricare
davvero usa lo zip vero del tuo gestionale.

**Ci sono giorni senza nessun movimento: devo usare «nessun nuovo movimento»?**
No. Il programma carica il file di ogni giorno, anche quando è vuoto: è più
sicuro, perché quel bottone del portale conferma anche le unità occupate del
giorno prima.

**Si è fermato a metà.**
Quello che ha già caricato resta. Rilancia: fa solo quello che manca.

---

Se qualcosa non torna: in alto a destra **«Dettagli»** → **«Copia tutto»**, e
manda quello. Dentro c'è tutto quello che serve per capire.
