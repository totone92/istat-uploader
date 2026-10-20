# Istat Uploader — i movimenti ISTAT su Turismatica, senza farli a mano

Chi gestisce una struttura ricettiva **in Umbria** comunica alla Regione, su
**Turismatica**, il movimento turistico di ogni giorno: un file per giorno,
caricato a mano dal portale, trenta volte al mese.

Istat Uploader lo fa al posto tuo. Entri una volta con SPID o CIE, lui
riconosce le tue strutture dal portale e ti mostra, per ognuna, quali giorni
sono già caricati e quali mancano. Poi trascini lo zip del mese: abbina i file
alla struttura giusta, ti dice cosa farà, e lo fa.

Serve a chiunque gestisca una struttura in Umbria e abbia già i file ISTAT
giornalieri: B&B, affittacamere, case vacanze, agriturismi, alberghi.

---

## Scaricalo

1. Vai su **[Releases](https://github.com/totone92/istat-uploader/releases/latest)**.
2. Sotto **Assets** scarica **`IstatUploader.exe`** e, per la prima prova,
   **`prova-settembre-2026.zip`**.
3. Mettili sul Desktop o in una cartella tua, e apri l'.exe con un doppio clic.

Non c'è niente da installare. Ti servono Windows 10 o 11 e **Google Chrome**.
La finestra usa WebView2, il componente di Edge già presente su Windows 10 e
11; se mancasse, il programma lo dice e ti porta alla pagina per installarlo.

Al primo avvio Windows potrebbe dire **«Windows ha protetto il PC»**: il
programma non è firmato. Clicca **«Ulteriori informazioni» → «Esegui
comunque»**. Cosa fare se lo blocca l'antivirus →
[`BUILD_WINDOWS.md`](BUILD_WINDOWS.md).

## Come funziona

1. **Collega Turismatica**: si apre Chrome sul portale, entri con SPID o CIE.
2. **Le tue strutture**: il programma le legge dal portale, in sola lettura, e
   ti chiede se ne gestisci una o più.
3. **Lo stato dei giorni**: per il mese scorso e quello in corso, quali sono già
   caricati e quali mancano.
4. **Conferma**: controlli il riepilogo, togli ciò che non gestisci, e solo
   allora si salva.
5. **Ogni mese**: trascini lo zip, i file si abbinano da soli (o il programma
   chiede, se non è chiaro), leggi il piano — «Settembre, Casa Lavanda: 28 giorni
   già presenti, 2 da caricare (12 e 19)» — e parti.

Se la lettura automatica delle strutture non riesce, il programma te le fa
scrivere a mano e salva una copia della pagina **senza dati personali**, da
mandare a chi ti assiste.

## Parte sempre in modalità PROVA

In cima alla finestra c'è una fascia colorata.

- **Gialla — PROVA**, ed è così a **ogni** avvio. Fa tutto, giorno per
  giorno, fino al bottone «Carica», e lì si ferma **senza premerlo**. Alla fine
  ti mostra cosa *avrebbe* caricato. Sul portale non cambia niente.
- **Rossa — VERA**: carica davvero. Ci si passa con un bottone, e prima di
  partire ti chiede conferma due volte.

Sul portale, ricaricare un giorno **sostituisce** quello che c'era: il
programma salta i giorni già caricati, ma il primo giro vero è bene farlo dopo
averne visto uno di prova.

## La prima prova: con lo zip di prova

Non ti serve nessun file vero. `prova-settembre-2026.zip` ha un file per ogni
giorno di settembre 2026, con numeri **inventati** e la struttura «STRUTTURA DI
PROVA». Trascinalo nel programma in modalità prova, abbinalo a una delle tue
strutture e guarda il giro sul portale: arriva fino a «Carica» e non carica
niente. Lo zip di prova **non si può usare in modalità vera**: il programma lo
riconosce e si ferma. La scaletta completa è in
[`BUILD_WINDOWS.md`](BUILD_WINDOWS.md).

## Le tue credenziali e i tuoi dati

- Il programma **non vede e non salva** password o codici: l'accesso lo fai tu,
  nel browser.
- Ricorda solo numeri e nomi delle strutture, lo stato dei giorni e quale file
  va a quale struttura (nella cartella dati di Windows).
- Accanto all'.exe scrive un registro, `IstatUploader.log`, con l'esito di ogni
  giorno e niente dati personali. In **Dettagli** c'è «Copia tutto» per
  mandarlo a chi ti assiste.

Guida completa → [`BUILD_WINDOWS.md`](BUILD_WINDOWS.md). Istruzioni brevi →
[`ISTRUZIONI.md`](ISTRUZIONI.md). Com'è fatto → [`docs/SVILUPPO.md`](docs/SVILUPPO.md).

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
