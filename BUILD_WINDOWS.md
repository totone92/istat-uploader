# Istat Uploader su Windows — come averlo, come provarlo

Un programma che carica su Turismatica i file ISTAT, giorno per giorno. Entri
una volta con SPID o CIE, lui riconosce le tue strutture dal portale, e da lì
trascini lo zip del mese e controlli il piano prima che parta.

Servono: Windows 10 o 11, **Google Chrome** installato, il tuo SPID o la CIE.
Python **non** serve (solo per la strada B).

---

## A. Scaricare l'.exe già pronto (la strada normale)

1. apri <https://github.com/totone92/istat-uploader/releases/latest>;
2. sotto **Assets** scarica i due file:
   - **`IstatUploader.exe`** — il programma;
   - **`prova-settembre-2026.zip`** — file ISTAT **inventati**, per la prima
     prova. Non aprirlo: si trascina così com'è nel programma.
3. Mettili sul Desktop o in una cartella tua (per esempio
   `Documenti\IstatUploader`), non in `Programmi`: accanto all'.exe il programma
   scrive il suo registro.

Non serve un account GitHub. (Gli «artefatti» delle singole build, nella pagina
Actions, sono lo stesso .exe ma si scaricano solo da entrati, e dopo 90 giorni
spariscono: la Release no.)

## B. Costruirlo sul PC (di riserva)

Solo se GitHub non è raggiungibile o se vuoi rifarlo tu.

1. **Installa Python 3.12** da <https://www.python.org/downloads/>
   (una versione 3.12.x, «Windows installer (64-bit)»).
   ⚠️ Nella **prima** schermata dell'installazione metti la spunta su
   **«Add python.exe to PATH»**, poi «Install Now».
2. Scarica il progetto: <https://github.com/totone92/istat-uploader> → bottone
   verde **Code** → **Download ZIP**, e scompattalo.
3. Nella cartella scompattata fai **doppio clic su `build.bat`**. Una finestra
   nera lavora da sola per qualche minuto: installa, controlla, costruisce, e
   alla fine apre un attimo la finestra del programma per vedere che funziona.
   Se un controllo fallisce **si ferma e non costruisce**.
4. Alla fine scrive `FATTO: dist\IstatUploader.exe`.

## Se Windows lo blocca

L'.exe **non è firmato** (la firma costa e serve un certificato aziendale):
Windows non lo conosce e prova a fermarlo. È normale.

- **Il browser dice «file non scaricato comunemente»**: tre puntini accanto al
  download → **Mantieni** (Edge: «Mostra altro» → «Mantieni comunque»).
- **«Windows ha protetto il PC» (SmartScreen)** al primo doppio clic:
  **«Ulteriori informazioni»** → **«Esegui comunque»**. Lo richiede a ogni
  versione nuova.
- **Non succede niente, o l'.exe sparisce** (Defender lo ha messo in
  quarantena): Start → **Sicurezza di Windows** → **Protezione da virus e
  minacce** → **Cronologia protezione** → la voce di `IstatUploader.exe` →
  **Azioni** → **Consenti nel dispositivo**. Poi riscaricalo.
- **Un messaggio dice che manca «Microsoft Edge WebView2»**: è il componente
  di Windows che disegna la finestra. Il programma apre da solo la pagina di
  Microsoft: scegli **«Evergreen Bootstrapper»**, installalo, riapri il
  programma. (Su Windows 10 e 11 aggiornati c'è già.)
- **Dice di non trovare Chrome**: installalo da <https://www.google.com/chrome>.
  Edge e Firefox non vanno bene per il portale.

> ⚠️ Non mandarlo per **WhatsApp o Gmail**: bloccano gli .exe. Usa il link di
> GitHub, Drive o una chiavetta.

---

## Come funziona, in breve

1. **Primo avvio → «Collega Turismatica».** Si apre Chrome sul portale: entri
   con SPID o CIE, con calma (non c'è nessuna scadenza).
2. **Il programma legge le tue strutture**, in sola lettura: quelle che il
   portale mostra al tuo accesso, con numero, comune e tipologia.
3. **«Gestisci una struttura o più strutture?»**: la risposta è già proposta in
   base a quante ne ha trovate.
4. **Per ogni struttura guarda i giorni** del mese scorso e di quello in corso:
   quali sono già caricati e quali mancano. Non preme niente che scriva.
5. **Riepilogo**: le strutture con lo stato dei giorni. Togli quelle che non
   gestisci, premi **Conferma**. Solo ora si salva qualcosa (nella cartella dati
   di Windows, mai password né dati SPID).
6. **Da qui in poi** il programma si apre sulle tue strutture: giorni caricati
   (verde), mancanti (rosso), e la zona dove **trascinare lo zip**.
7. **I file si abbinano da soli** alla struttura dal nome scritto dentro i
   file; se non è chiaro, il programma **chiede** (e, se vuoi, si ricorda la
   risposta).
8. **Il piano prima di partire**: «Settembre 2026, Casa Lavanda: 28 giorni già
   presenti, 2 da caricare (12 e 19)». Poi parte, giorno per giorno.

«**Aggiorna le mie strutture**» rifà i passi 1–5 quando vuoi, per esempio se
ne aggiungi una.

### Se le strutture non si leggono da sole

La pagina del portale con l'elenco delle strutture non si è potuta vedere
durante lo sviluppo, quindi la lettura automatica potrebbe non riuscire al
primo colpo. In quel caso il programma:

- lo dice, e ti fa **scrivere a mano** il numero di ogni struttura (lo trovi
  nell'indirizzo della pagina dei movimenti, dopo `idStruttura=`);
- salva **accanto al registro** una copia della pagina, **senza dati
  personali** (tolti codice fiscale, nomi delle persone, email, telefoni,
  token di sessione), con un nome tipo `pagina-strutture-20261020-093000.html`.

**Manda quel file**: con quello la lettura si sistema. Prima di mandarlo puoi
aprirlo con un doppio clic e guardarlo.

## La modalità PROVA (è quella con cui si apre)

In cima c'è una fascia colorata:

- **gialla — PROVA**: fa tutto, giorno per giorno, fino a «Carica» pronto, e lì
  si ferma **senza premerlo**. Alla fine ti mostra cosa *avrebbe* caricato.
- **rossa — VERA**: carica davvero. Ci passi con **«Passa alla modalità
  vera…»**, che chiede conferma; e prima di partire chiede di nuovo, col mese e
  le strutture scritti.

Il programma **si apre sempre in prova**, a ogni avvio.

> ⚠️ **Perché tanta cautela**: un giorno già sul portale il programma lo
> **salta**, in entrambe le modalità. Ma se il portale lo mostra come *non*
> caricato e il programma lo carica, il file **sostituisce** quello che c'era.

**Lo zip di prova non si carica mai davvero**: in modalità vera il programma lo
riconosce e si ferma con «Questo è lo zip di prova: serve solo in modalità
prova». In prova, siccome «STRUTTURA DI PROVA» non è nessuna delle tue, ti
chiede a quale abbinarlo — solo per vedere il giro.

## Il registro e i «Dettagli»

In alto a destra c'è **«Dettagli»**: il percorso del registro, **«Apri la
cartella»**, **«Copia tutto»** (riepilogo + ultime righe del registro, da
incollare in un messaggio), **«Verifica il computer»** e le ultime righe.

Il registro si chiama **`IstatUploader.log`** e sta **accanto all'.exe** (se lì
non si può scrivere: `%APPDATA%\UploaderTurismatica\`). Una riga per giorno:
struttura, giorno, esito, nome del file, errore. **Niente** password, dati degli
ospiti o nome utente di Windows.

**Se qualcosa non va**: «Dettagli» → «Copia tutto», e manda anche
`IstatUploader.log` (e l'eventuale `pagina-…html`).

---

## La scaletta della prima prova

Nell'ordine. Se un passo non torna, **fermati lì** e manda registro e copie.

### 0. Il computer

1. Doppio clic su `IstatUploader.exe`. 5–15 secondi prima della finestra sono
   normali (si scompatta a ogni avvio).
2. «Dettagli» → **«Verifica il computer»**: devono uscire tutte ✓ (cartella
   delle impostazioni, WebView2, Chrome che si apre e si chiude).

### 1. Collega Turismatica

1. **«Collega Turismatica»** → entra con SPID/CIE in Chrome → (se non prosegue
   da solo) **«Sono dentro: vai»**.
2. Il programma trova le tue strutture e chiede «una o più».
   - ❌ se dice che non è riuscito a leggerle: scrivi a mano i numeri, vai
     avanti, e **manda il file `pagina-strutture-….html`** che ha salvato.
3. Nel **riepilogo** controlla, per ogni struttura, i giorni del mese scorso:
   devono corrispondere a quello che vedi sul portale (aprilo in un'altra
   finestra e guarda due o tre giorni, caricati e no).
   - ❌ se una struttura dice «Il portale mostra … e non sono riuscito a passare
     a …»: il cambio di mese non ha funzionato. Puoi proseguire lo stesso;
     segnalalo, e manda il file `pagina-movimenti-….html` se c'è.
4. **Conferma**.

### 2. Lo zip di prova, in prova

1. Fascia **gialla**. Trascina `prova-settembre-2026.zip` nella zona dello zip.
2. Ti chiede a quale struttura abbinarlo (sono file inventati): scegline una.
3. Il **piano** dice quanti giorni di settembre 2026 risultano già presenti e
   quanti caricherebbe. Avvia.
4. Guarda Chrome lavorare: per ogni giorno da caricare apre la finestrella,
   sceglie il file e la chiude **senza premere «Carica»**.
5. L'esito comincia con **«Prova finita: non ho caricato niente»**.
6. Prova il blocco: **«Passa alla modalità vera…»** → conferma → trascina di
   nuovo lo zip di prova. Deve dire **«Questo è lo zip di prova: serve solo in
   modalità prova»**. Poi **«Torna alla modalità prova»**.

### 3. I file veri, in prova

Trascina lo zip ISTAT vero di un mese (dal tuo gestionale; con HostLab:
Report → ISTAT). I file devono **abbinarsi da soli** o con una domanda chiara.
Il piano deve tornare con quello che vedi sul portale. Avvia la prova.

### 4. Un giorno solo, in modalità vera

Usa uno zip che abbia **un solo giorno mancante** sul portale (il piano deve
dire «1 da caricare»). Passa alla modalità vera, avvia, conferma. Poi guarda
quel giorno sul portale: i numeri devono essere quelli del file. Riapri il
programma e fai «Aggiorna le mie strutture»: quel giorno ora è verde.

### 5. Il mese intero

Un giro in prova, poi in vera, guardando lo schermo la prima volta.
