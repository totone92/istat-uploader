# Istat Uploader su Windows — come averlo, come provarlo

Un programma che carica su Turismatica i file ISTAT di un mese, giorno per
giorno. Tu scegli il mese e lo zip, entri con SPID/CIE, e lui fa il resto.

Servono: un PC Windows 10 o 11, **Google Chrome** installato, il tuo SPID o la
CIE. Python **non** serve (solo per la strada B, più sotto).

---

## A. Scaricare l'.exe già pronto (la strada normale)

L'.exe lo costruisce GitHub da solo, su una macchina Windows, a ogni modifica.
Per la Release non serve un account GitHub; per gli artefatti delle build sì
(GitHub li fa scaricare solo a chi è entrato).

**Dalla Release** (link fisso, la versione «ufficiale»):

1. apri <https://github.com/totone92/istat-uploader/releases/latest>;
2. in fondo, sotto **Assets**, clicca **`IstatUploader.exe`**: si scarica
   direttamente.

**Dall'ultima build** (la più recente, anche se non ancora in una Release):

1. apri <https://github.com/totone92/istat-uploader/actions/workflows/build-windows.yml>;
2. clicca sulla prima riga con il pallino **verde** ✓;
3. in fondo alla pagina, sotto **Artifacts**, clicca **`IstatUploader.exe`**:
   si scarica direttamente l'eseguibile, niente zip da aprire;
4. spostalo sul Desktop o in una cartella tua (per esempio
   `Documenti\IstatUploader`).

> ⚠️ Gli artefatti delle build restano su GitHub **90 giorni**, poi spariscono.
> Le Release no.

Metti l'.exe in una cartella **tua** (Desktop, Documenti), non in
`Programmi`: accanto all'.exe il programma scrive il suo registro.

## B. Costruirlo sul PC (di riserva)

Solo se GitHub non è raggiungibile o se vuoi rifarlo tu.

1. **Installa Python 3.12** da <https://www.python.org/downloads/>
   (scegli una versione 3.12.x, «Windows installer (64-bit)»).
   ⚠️ Nella **prima** schermata dell'installazione metti la spunta su
   **«Add python.exe to PATH»**, poi «Install Now».
2. Scarica il progetto: dalla pagina <https://github.com/totone92/istat-uploader>
   → bottone verde **Code** → **Download ZIP**, e scompattalo.
3. Nella cartella scompattata fai **doppio clic su `build.bat`**. Si apre una
   finestra nera che lavora da sola per qualche minuto: installa, fa i
   controlli, costruisce. Se un controllo fallisce **si ferma e non
   costruisce**.
4. Alla fine scrive `FATTO: dist\IstatUploader.exe`. L'.exe è nella cartella
   `dist`.

## Se Windows lo blocca

L'.exe **non è firmato** (la firma costa e serve un certificato aziendale):
Windows non lo conosce e prova a fermarlo. È normale, succede a ogni programma
nuovo e poco diffuso.

- **Il browser dice «file non scaricato comunemente» / «potrebbe essere
  pericoloso»**: clicca i tre puntini accanto al download → **Mantieni** (Edge:
  «Mostra altro» → «Mantieni comunque»).
- **«Windows ha protetto il PC» (SmartScreen)** al primo doppio clic: clicca la
  scritta piccola **«Ulteriori informazioni»** → **«Esegui comunque»**. Lo
  chiede solo la prima volta (e di nuovo a ogni versione nuova).
- **Non succede niente, o l'.exe sparisce** (Windows Defender lo ha messo in
  quarantena): Start → **Sicurezza di Windows** → **Protezione da virus e
  minacce** → **Cronologia protezione** → apri la voce di `IstatUploader.exe`
  → **Azioni** → **Consenti nel dispositivo**. Poi riscaricalo.
- **Si apre ma dice di non trovare Chrome**: installa Chrome da
  <https://www.google.com/chrome>. Edge e Firefox non vanno bene.

> ⚠️ Non mandarlo per **WhatsApp o Gmail**: bloccano gli .exe. Usa il link di
> GitHub, Drive o una chiavetta.

---

## La modalità PROVA (è quella con cui si apre)

In cima alla finestra c'è una fascia colorata:

- **gialla — MODALITÀ PROVA**: fa tutto, giorno per giorno — apre la riga,
  apre la finestrella di caricamento, sceglie il file, aspetta che «Carica» si
  accenda — e **lì si ferma senza premerlo**. Alla fine ti mostra l'elenco
  `giorno ← file` di **cosa avrebbe caricato**. Sul portale non cambia niente.
- **rossa — MODALITÀ VERA**: preme «Carica» davvero.

Il programma **si apre sempre in prova**, a ogni avvio. Per il giro vero
premi **«Passa alla modalità VERA…»** nella fascia: ti chiede conferma, e al
momento di «Avvia» te la chiede ancora, con il mese e le strutture scritti.

> ⚠️ **Perché tanta cautela**: se un giorno è già sul portale il programma lo
> **salta**, in tutte e due le modalità. Ma se il portale lo mostra come *non*
> caricato e il programma lo carica, il file **sostituisce** quello che c'era —
> anche una correzione fatta a mano sul portale. Per questo il primo giro vero
> va fatto dopo una prova sullo stesso periodo.

## Il registro (il file da rimandare se qualcosa non va)

Si chiama **`IstatUploader.log`** e sta **nella stessa cartella dell'.exe**.
In fondo alla finestra c'è scritto il percorso esatto e il bottone **«Apri la
cartella del registro»**.

- Se la cartella dell'.exe non è scrivibile, il registro va in
  `%APPDATA%\UploaderTurismatica\IstatUploader.log` (la finestra lo dice).
- Quando supera 1 MB si rinomina in `IstatUploader.log.1` e ne riparte uno
  nuovo (ne tiene tre).
- Una riga per giorno: data e ora, numero della struttura su Turismatica,
  giorno, esito (`caricato`, `gia_caricato`, `da_caricare` in prova,
  `file_mancante`, `non_riuscito`), nome del file, errore. In più l'inizio e la
  fine di ogni giro, con la modalità.
- **Non contiene** password né codici (il programma non li vede: l'accesso lo
  fai tu nel browser), né dati degli ospiti (del file scrive solo il nome), né
  il tuo nome utente di Windows (le cartelle personali diventano `~`).

**Se qualcosa non va**: rimanda `IstatUploader.log` **e** il testo del
riepilogo finale (bottone «Copia tutto»). Se il problema è all'avvio, anche
`%APPDATA%\UploaderTurismatica\controllo.txt` (lo scrive «Verifica il
computer»).

---

## La scaletta della prima prova

Nell'ordine. Se un passo non torna, **fermati lì** e manda il registro.

### 0. Il computer

1. Doppio clic su `IstatUploader.exe` (SmartScreen: vedi sopra). Conta i
   secondi fino alla finestra: 5–15 sono normali (si scompatta a ogni avvio).
2. Controlla che la fascia in cima sia **gialla — MODALITÀ PROVA**.
3. Premi **«Verifica il computer»**: Chrome si apre e si chiude da solo. Devono
   uscire **tre ✓**.

### 1. Prova su un mese GIÀ caricato (per esempio uno caricato a mano)

Serve a vedere che riconosce i giorni già dentro, che è la cosa che protegge
il portale nel giro vero.

1. **«Aggiungi struttura…»**: un nome a piacere e il **numero su Turismatica**
   (nell'indirizzo della pagina dei movimenti, dopo `idStruttura=`; non è il
   numero di beb.it).
2. Seleziona la riga → **«Scegli i file…»** → lo zip ISTAT di quel mese
   (scaricato da HostLab: Report → ISTAT; vanno bene sia i file di beb sia
   quelli che genera HostLab, `schedine_istat_<id>_<AAAAMMGG>.txt`).
3. In alto scegli **quel mese** e premi **Avvia**.
4. Chrome si apre su Turismatica e compare **«Ora tocca a te»**: entra con
   SPID/CIE con calma (il programma non ha fretta), poi **«Sono dentro: vai»**.
5. Alla fine il riepilogo deve dire, per la struttura, **«N già c'erano»** con N
   uguale ai giorni del mese, e **nessun «da caricare»**.
   - ✅ così: il riconoscimento funziona. Avanti.
   - ❌ se compaiono giorni «da caricare» che sul portale sono già caricati:
     **non passare alla modalità vera**. Manda registro e riepilogo.

### 2. Un giorno solo, in modalità VERA

1. Scegli il **primo giorno non ancora caricato** di una struttura (il portale
   apre un giorno solo se il precedente c'è).
2. In alto: **«Oppure dal»** quel giorno **«al»** lo stesso giorno.
3. Prima in **prova**: il riepilogo deve dire «1 giorni da caricare» e il file
   giusto accanto alla data giusta.
4. Poi **«Passa alla modalità VERA…»** → conferma → **Avvia** → conferma.
5. Il riepilogo deve dire **«1 giorni caricati»**. Apri il portale e guarda
   quel giorno: i numeri (arrivi, partenze, presenze, camere) devono essere
   quelli del file.
6. Rilancia lo stesso giorno (in prova va benissimo): ora deve dire
   **«1 già c'erano»**.

### 3. Il mese intero

1. Scegli il mese, lascia **«Il mese di»**.
2. Un giro in **prova** e leggi l'elenco `giorno ← file`.
3. Se torna: **modalità VERA** → Avvia, guardando lo schermo la prima volta.
4. Rilancia lo stesso mese: deve dire solo «N già c'erano».

Dopo, per gli altri mesi basta il punto 3.
