# Caricare i movimenti su Turismatica

Un programma che carica su Turismatica i movimenti giornalieri, uno per uno, al
posto tuo. Quello che facevi a mano trenta volte al mese.

Ti serve: il computer, SPID (o la carta d'identità elettronica) e cinque minuti.

---

## La prima volta

### 1. Installa il programma

Non c'è niente da installare davvero: è **un file solo**. Salvalo dove vuoi — va
benissimo il Desktop.

Quando lo apri la prima volta Windows fa una faccia strana e scrive
**«Windows ha protetto il PC»**. È normale e non è un virus: succede a tutti i
programmi nuovi che non sono famosi.

> Clicca su **«Ulteriori informazioni»** (la scritta piccola), poi su
> **«Esegui comunque»**.

Lo fa solo la prima volta.

### 2. Controlla che il computer sia a posto

Apri il programma e premi **«Verifica il computer»**.

Ci mette una decina di secondi, apre e chiude Google Chrome da solo, e poi ti
dice com'è messo. **Devono uscire tre spunte verdi ✓.**

Se una riga ha una ✗, ti dice lei cosa fare. Quasi sempre è: *installa Google
Chrome*. Lo scarichi da **google.com/chrome**; Edge non va bene.

### 3. Dichiara la tua struttura (si fa una volta sola)

Premi **«Aggiungi struttura…»**. Ti chiede due cose:

- **il nome**: quello che vuoi tu, serve solo a riconoscerla nell'elenco;
- **il numero su Turismatica**: lo trovi **nell'indirizzo** della pagina dei
  movimenti, in fondo. Entra su Turismatica, vai sulla pagina dove carichi i
  file, e guarda in alto nella barra dell'indirizzo:

  ```
  ...movimentoospiti.xhtml?idStruttura=12345
                                       ─────
  ```

  Scrivi quel numero: **12345**.

> ⚠️ Non è il numero di bed-and-breakfast.it. Sono due cose diverse.

Da adesso in poi il programma se lo ricorda. Se hai più di una struttura,
aggiungile tutte: le fa una dietro l'altra con un accesso solo.

---

## Ogni volta (cinque minuti)

### 1. Scarica i file ISTAT del mese

Dal tuo gestionale o channel manager scarica i file ISTAT giornalieri del mese
(con HostLab: **Report → ISTAT**). Ti viene giù un file `.zip`. **Non aprirlo**: lasciandolo com'è fai prima.

### 2. Apri il programma e digli tre cose

1. **Che mese**: di solito è già giusto (propone il mese scorso).
2. **Quale struttura**: metti la spunta ☑ accanto a quelle da fare.
3. **Dove sono i file**: seleziona la riga della struttura e premi
   **«Scegli i file…»**, poi indica il `.zip` che hai appena scaricato.

   *(Se l'avevi già aperto e hai una cartella con dentro tanti file `.txt`, va
   bene lo stesso: dì di no allo zip e ti fa scegliere la cartella.)*

### 3. Scegli la modalità, poi premi **Avvia**

In cima c'è una fascia colorata. Il programma si apre sempre in **PROVA**
(gialla): fa tutto ma **non carica niente**, e alla fine ti dice cosa avrebbe
caricato. Quando l'elenco ti torna, premi **«Passa alla modalità VERA…»** (la
fascia diventa rossa) e rilancia: ora carica davvero.

Si apre **Google Chrome** sulla pagina di Turismatica, e il programma **si
ferma**. Compare una finestra che dice **«Ora tocca a te»**.

### 4. Entra con SPID

Vai sulla finestra di Chrome che si è aperta, premi **«Accedi»** ed entra con
SPID o CIE, esattamente come fai sempre.

> **Prenditi tutto il tempo che ti serve.** Il programma aspetta e basta, non
> scade. Se devi prendere il telefono, inquadrare il codice, confermare — fai
> con calma.

> Il programma **non conosce le tue credenziali** e non le salva da nessuna
> parte. L'accesso lo fai tu, sul tuo computer.

### 5. Torna sul programma e premi **«Sono dentro: vai»**

Da qui in poi fa tutto lui. Sotto vedi scorrere i giorni man mano che li carica.
**Non toccare la finestra di Chrome** mentre lavora.

### 6. Leggi il riepilogo

Alla fine si apre una finestra che dice com'è andata. Per ogni struttura:

- **quanti giorni ha caricato**;
- **quanti c'erano già** (li salta — è normale, non è un errore);
- **se manca qualche file**;
- **se qualche giorno non è passato**.

In fondo, se c'è qualcosa da fare, c'è scritto **DA FARE** con l'elenco.
Se non c'è, c'è scritto **«Tutto a posto»** e hai finito.

C'è un tasto **«Copia tutto»**, se ti serve mandarlo a qualcuno.

---

## Domande che vengono a tutti

**Posso rilanciarlo sullo stesso mese?**
Sì, tranquillamente. I giorni già caricati li salta e te lo dice
(«N già c'erano»). Non fa danni e non carica niente due volte.

**Mi dice che manca il file di qualche giorno.**
Quel giorno non c'era nel `.zip`. Riscarica quel mese dal gestionale e
rilancia: i giorni che ci sono già li salta e carica solo i mancanti.

**Si è fermato a metà.**
Rilancialo. Riparte e fa solo quello che manca.

**Mi dice che la struttura risulta «CESSATA».**
Su Turismatica quella struttura non è più attiva, quindi non c'è la pagina dove
caricare. Non è un problema del programma: è una cosa da sistemare sul portale.

**Chrome si è aperto ma non succede niente.**
Guarda se c'è la finestra **«Ora tocca a te»**, magari finita dietro. Il
programma sta aspettando che tu entri con SPID.

**Ho chiuso Chrome per sbaglio mentre caricava.**
Non è grave: quello che aveva già caricato resta. Rilancia e finisce il resto.

**Devo lasciare il computer acceso?**
Solo mentre carica. Un mese sono pochi minuti.

---

Se qualcosa non torna, premi **«Copia tutto»** sul riepilogo e manda quello:
c'è dentro tutto quello che serve per capire.
