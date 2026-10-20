# Istat Uploader — i movimenti ISTAT su Turismatica, senza farli a mano

Chi gestisce una struttura ricettiva **in Umbria** comunica alla Regione, su
**Turismatica**, il movimento turistico di ogni giorno: un file per giorno,
caricato a mano dal portale, trenta volte al mese.

Istat Uploader lo fa al posto tuo. Scegli il mese e lo zip con i file
giornalieri, entri con SPID o CIE, e lui li carica uno dopo l'altro. Alla fine
ti dice cosa è andato, cosa c'era già e cosa manca ancora.

Serve a chiunque gestisca una struttura in Umbria e abbia già i file ISTAT
giornalieri: B&B, affittacamere, case vacanze, agriturismi, alberghi.

---

## Scaricalo

1. Vai su **[Releases](https://github.com/totone92/istat-uploader/releases/latest)**.
2. Sotto **Assets** scarica **`IstatUploader.exe`** e, per la prima prova,
   **`prova-settembre-2026.zip`**.
3. Mettili sul Desktop o in una cartella tua, e apri l'.exe con un doppio clic.

Non c'è niente da installare. Ti servono Windows 10 o 11 e **Google Chrome**.

Al primo avvio Windows potrebbe dire **«Windows ha protetto il PC»**: il
programma non è firmato, e Windows non lo conosce ancora. Clicca
**«Ulteriori informazioni» → «Esegui comunque»**. Cosa fare se lo blocca
l'antivirus → [`BUILD_WINDOWS.md`](BUILD_WINDOWS.md).

## Parte sempre in modalità PROVA

In cima alla finestra c'è una fascia colorata.

- **Gialla — PROVA**, ed è così a **ogni** avvio. Fa tutto, giorno per
  giorno, fino al bottone «Carica», e lì si ferma **senza premerlo**. Alla fine
  ti mostra l'elenco di cosa *avrebbe* caricato. Sul portale non cambia niente.
- **Rossa — VERA**: carica davvero. Ci si passa con un bottone, e prima di
  partire ti chiede conferma due volte.

Perché tanta cautela? Sul portale, ricaricare un giorno **sostituisce** quello
che c'era. Il programma salta i giorni già caricati, ma il primo giro vero è
bene farlo dopo averne visto uno di prova sullo stesso mese.

## La prima prova: con lo zip di prova

Non ti serve nessun file vero. `prova-settembre-2026.zip` ha un file per ogni
giorno di settembre 2026, con numeri **inventati** e la struttura «STRUTTURA DI
PROVA». Sceglilo come file, scegli settembre 2026 e avvia **in prova**: vedrai
il programma lavorare sul portale, giorno per giorno, senza caricare niente.
Lo zip di prova **non si può usare in modalità vera**: il programma lo
riconosce e si ferma con «Questo è lo zip di prova: serve solo in modalità
prova». La scaletta completa è in [`BUILD_WINDOWS.md`](BUILD_WINDOWS.md).

## Come si usa

1. **«Verifica il computer»**: controlla che Chrome si apra. Devono uscire
   tre ✓.
2. **«Aggiungi struttura…»**: un nome a tua scelta e il **numero della
   struttura su Turismatica**. Lo trovi nell'indirizzo della pagina dei
   movimenti, dopo `idStruttura=`.
3. **«Scegli i file…»**: lo zip con i file giornalieri del mese. Il programma
   riconosce i file `schedine_istat_<id>_<AAAAMMGG>.txt` e `GGMMAAAA.txt`.
4. Scegli il mese e premi **Avvia**. Chrome si apre su Turismatica: entra con
   **SPID o CIE**, con calma, poi premi **«Sono dentro: vai»**.

Il programma **non vede e non salva** le tue credenziali: l'accesso lo fai tu,
nel browser. Accanto all'.exe scrive un registro, `IstatUploader.log`, con
l'esito di ogni giorno e niente dati personali. Se qualcosa non va, è il file
da mandare a chi ti assiste.

Guida completa, prova passo per passo e costruzione dell'.exe dal sorgente →
[`BUILD_WINDOWS.md`](BUILD_WINDOWS.md). Istruzioni brevi per chi lo usa ogni
mese → [`ISTRUZIONI.md`](ISTRUZIONI.md). Com'è fatto →
[`docs/SVILUPPO.md`](docs/SVILUPPO.md).

## Cosa non fa

- Non **genera** i file ISTAT: li carica. I file li prepara il tuo gestionale
  o il tuo channel manager.
- Non fa il login al posto tuo: SPID e CIE sono tuoi, e così deve restare.
- Funziona solo con Turismatica (Regione Umbria) e con Google Chrome.

Non è un prodotto della Regione Umbria né è collegato a Turismatica: è uno
strumento indipendente che usa il portale come faresti tu.

---

Creato da **Fortitudo** con l'AI. Licenza [MIT](LICENSE): usalo, modificalo,
ridistribuiscilo liberamente. È fornito così com'è, senza garanzie: i dati che
carichi su Turismatica restano una tua dichiarazione.
