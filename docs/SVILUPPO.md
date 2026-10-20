# Istat Uploader — note di sviluppo

> Chi lo usa legge il [`README`](../README.md) e
> [`BUILD_WINDOWS.md`](../BUILD_WINDOWS.md). Qui: com'è fatto, perché, e cosa
> non è ancora provato.
>
> **Per averlo e provarlo su Windows → [`BUILD_WINDOWS.md`](../BUILD_WINDOWS.md).**
> L'.exe lo costruisce GitHub (`.github/workflows/build-windows.yml`) a ogni
> push su `main`; con un tag `vX.Y.Z` finisce anche in una Release.

Carica i **movimenti ISTAT giornalieri** su Turismatica (Regione Umbria).
Gira sul PC del gestore, non sul nostro server.

> ⚠️ **Il login è SPID/CIE: non si automatizza e non deve.** L'app apre Chrome,
> si ferma e aspetta che la persona entri. È anche il motivo per cui questa cosa
> vive su un PC e non su un server: l'identità è di chi ce l'ha.

L'app fa **una cosa sola**: prende i `.txt` di un periodo, apre il portale,
aspetta SPID, carica giorno per giorno. Non genera e non converte niente — i
`.txt` li fa beb.it e li scarica HostLab, oppure, per una struttura senza beb,
li genera HostLab stesso (Report → ISTAT → «Genera file ISTAT»): stesso nome,
stesso tracciato.

**«Già caricato» si legge dalla tabella, non dal pulsante** (dal 19/10/2026,
allineato al job del Mac mini): il pulsante di caricamento resta anche dopo,
perché serve a sostituire il file. Un giorno è dentro se il portale scrive
«File caricato: …», se c'è l'icona del documento, o se i valori del movimento
ci sono (anche tutti zero) senza la doppia freccia. Un giorno che il portale
non apre ancora è **non riuscito**, non «già caricato».

**Si parte sempre in MODALITÀ PROVA** (dal 20/10/2026, v1.1.0): ogni giorno
arriva fino a «Carica» pronto e lì si chiude il dialog senza premerlo; il
riepilogo elenca `giorno ← file`. La differenza fra le due modalità è **una
riga** in `portale.carica_giorno` (e `prova` non ha default). Il portale
sostituisce un giorno ricaricato: il giro vero è un gesto, con due conferme.

**Il registro** `IstatUploader.log` sta accanto all'.exe (`registro.py`): una
riga per giorno — struttura, giorno, esito, nome del file, errore — senza
credenziali (non ce ne sono), senza dati degli ospiti e con la cartella
personale scritta `~`.

---

## v1.3.0 — il portale vero (20/10/2026)

La lettura delle strutture della v1.2.0 non ha funzionato alla prima prova di
Marco. Con due pagine **vere** del portale (ripulite: nomi e numeri inventati
ma coerenti) i selettori sono allineati a quelle. Le copie stanno in
`tests/fixtures/turismatica/` e i test in `tests/test_pagine_vere.py`.

| pezzo | com'è davvero | dove |
|---|---|---|
| elenco strutture | `prehome.xhtml`: `selectOneMenu` PrimeFaces, `<select>` nascosto con id `…_input`; `option value` = idStruttura, testo = nome (spazi in coda). La v1.2.0 cercava «strutt» nell'id e non trovava niente | `riconoscimento.strutture` / `_select_di_strutture` (vuole un titolo che parli di strutture: nella pagina dei movimenti c'è la tendina delle **provenienze**) |
| intestazione | `div.nomestruttura`: nome, «(tipologia - …)», «Comune: …», CIR, CIN; `div.stato VALIDATA`; l'id dai link della pagina (`dettagliostruttura.xhtml?idStruttura=`, `par_STRU%3D`) | `riconoscimento.intestazione` |
| tabella e bottoni | letta **in Python dall'HTML** (`driver.page_source`), non più con un JavaScript dentro Chrome: la stessa regola nei test e sul portale. Colonne per intestazione, bottoni per `title`/icona; il bottone di caricamento c'è solo sul primo giorno non inserito | `pagina_movimenti.leggi_pagina` |
| entrare in una struttura | GET diretta `?idStruttura=`; se apre un'altra struttura o nessuna tabella, `prehome` → widget `selectValue` → «Accedi», come il gestore | `portale.apri_movimenti` |
| mesi | frecce `monthButtonText` solo fra mesi **aperti** (spente nel campione); un mese prima di quelli è nel periodo chiuso → scheda «Movimento periodo chiuso» (TabView **dinamico**, `PF('tabView').select(i)`) | `portale.vai_al_mese` → `Raggiunto.CHIUSO`, `portale.leggi_mese` |
| comunicazione mensile | «Invia comunicazione telematica mensile» nelle «Azioni» del periodo aperto; dialogo `cdNotifica` «…per il mese Ottobre 2026…» con «Sì, procedi» / «No, annulla». Nella pagina ci sono altri tre «Sì, procedi» (uno **elimina** i movimenti) | `portale.invia_comunicazione`: chiesta dal gestore nel piano, solo a mese concluso ed entro il 5, solo con tutti i giorni dentro, solo se il dialogo nomina quel mese; in prova si ferma prima del bottone; verifica = il mese è passato nel periodo chiuso |
| abbinamento dal CIN | il CIN contiene l'idStruttura (ultime 6 cifre, zeri davanti) nel campione | `abbinamento.cin_affidabile`: il file col CIN esatto di una struttura si abbina da solo **solo se** la regola regge su **tutte** le strutture lette |

**Decisione: «nessun nuovo movimento fino a questo giorno» non si usa.** Il
portale conferma presenze **e unità occupate** dell'ultimo giorno compilato per
tutto l'intervallo: equivale a un file a zero movimenti solo se le unità non
cambiano, e sbaglia molti giorni in un gesto. Si carica il file di ogni giorno.

**Provato qui:** 196 test (17 sulle pagine vere). I tre JavaScript rimasti
(scelta in `prehome`, cambio scheda, dialogo della comunicazione) eseguiti in
Chromium headless sulle pagine vere, con PrimeFaces finto, invio dei moduli
bloccato e rete chiusa. **Non provato:** il contenuto della scheda «Movimento
periodo chiuso» (dinamica: nel campione è vuota), la GET diretta dopo il login,
la comunicazione mensile vera, il cambio di mese con frecce accese.

---

## v1.2.0 — strutture lette dal portale, interfaccia nuova (20/10/2026)

Dopo la prima prova vera (struttura scritta a mano, «123» inventato, giro fermo
su «la tabella dei movimenti non si è aperta») il flusso è cambiato: **le
strutture non si scrivono, si leggono dal portale**, e Tkinter è sostituito da
**pywebview** con un'interfaccia HTML/CSS locale (WebView2, nessuna CDN).

| pezzo | dove | provato come |
|---|---|---|
| il flusso, schermata per schermata | `api.Api` (niente finestra, niente browser) | `tests/test_flusso.py`, da capo a fondo con un `Portale` finto |
| la lettura delle strutture | `riconoscimento.strutture` — parte da **`idStruttura`**, l'unica cosa certa del portale | pagine **finte** nelle forme probabili (tabella PrimeFaces, select, schede) |
| la copia della pagina senza dati personali | `riconoscimento.ripulisci` | CF, persone, email, telefoni, ViewState, jsessionid tolti; classi, id, numeri e nomi delle strutture restano |
| lo stato dei giorni e il cambio di mese | `portale.leggi_mese`, `portale.vai_al_mese` | i due JavaScript eseguiti in Chromium su una pagina dei movimenti finta: righe classificate, «precedente/successivo» trovati, il «Carica» del dialog e un «Salva» con la stessa icona **scartati** |
| abbinamento file → struttura | `abbinamento.abbina` | nome nel file uguale → da solo; diverso → si chiede (la più simile in cima); scelta ricordata; ⚠️ l'id nel nome del file **non** è il numero Turismatica e non abbina mai |
| il piano | `piano.costruisci` | «Settembre 2026, Casa Lavanda: 28 giorni già presenti, 2 da caricare (12 e 19).» |
| i messaggi | `messaggi.py` | «La struttura 123 non è fra quelle del tuo account Turismatica» al posto della tabella |
| la finestra | `finestra.py` + `ui/` | screenshot in Chromium headless, chiaro e scuro, con gli stati veri di `Api`; sul runner Windows `--autoverifica-finestra` apre la finestra **vera** e aspetta che il JS parli col Python |

⚠️ **(superato dalla v1.3.0)** Non visto mai, da sistemare con la prima copia vera: la pagina con
l'elenco delle strutture e il comando che cambia mese nella pagina dei
movimenti. Se la lettura fallisce, l'app salva `pagina-strutture-*.html` /
`pagina-movimenti-*.html` (ripulite) accanto al registro e lascia inserire i
numeri a mano: con quel file si aggiungono i selettori e un test.

⚠️ **WebView2 assente ⇒ pywebview ripiega in silenzio su MSHTML** (Internet
Explorer). `finestra.py` lo controlla nel registro prima di aprire e rifiuta il
motore sbagliato in `events.initialized`.

---

## ⚠️ COSA NON HO POTUTO PROVARE DA QUI

Sviluppato su Linux, senza Windows e senza un accesso SPID a Turismatica.
Queste cose **non sono verificate** e vanno provate su un PC vero:

| cosa | perché no | come si scopre se è rotta |
|---|---|---|
| **il `.exe` per Windows** | PyInstaller **non compila per un altro sistema**: impacchetta l'interprete della macchina su cui gira. Da Linux esce un binario Linux. | ✅ ora lo costruisce GitHub su `windows-latest`, e l'.exe fa `--autoverifica` di sé (moduli Selenium, Selenium Manager, pywebview, interfaccia) e `--controllo` (apre Chrome). Resta da provare **su un PC vero** |
| **la finestra** | nessun display grafico in questo ambiente (niente X, e `xvfb` richiede i permessi di amministratore) | si vede al primo avvio |
| **il caricamento vero sul portale** | serve un accesso SPID a Turismatica, che è di una persona | primo giro vero, su **un mese solo** |
| **SmartScreen** | è una reputazione di Microsoft su un file firmato, non una proprietà del codice | primo download su un PC altrui |

**Cosa invece è provato**, e non a parole:

- **196 test** su tutto ciò che non è il browser: i nomi dei file (beb,
  generati da HostLab col CIN, script originale), lo zip, il periodo, il
  riepilogo, le regole del portale, le strutture salvate, **la modalità prova**
  (con un finto della *nostra* interfaccia `Passi`, non del portale) e il
  registro;
- **il pacchetto si costruisce e il binario congelato parte**: arriva fino ad
  aprire la finestra e fallisce solo per il display mancante;
- ⭐ **Selenium Manager funziona da dentro il binario congelato**: trova il
  browser e scarica il ChromeDriver giusto. È **la parte più a rischio di tutta
  la consegna**, ed è quella che ho potuto provare davvero;
- ⭐ **un difetto di impacchettamento vero, trovato e corretto qui** (sotto).

### Il difetto che il controllo ha già preso

Con l'elenco dei moduli Selenium scritto a mano, il pacchetto si costruiva
benissimo e poi moriva con:

```
No module named 'selenium.webdriver.chrome.webdriver'
```

Cioè: l'app partiva, mostrava la finestra, e falliva **nel momento peggiore** —
quando l'utente preme Avvia. Selenium risolve i suoi moduli per nome a runtime,
quindi PyInstaller non li vede seguendo gli import. Corretto con
`collect_submodules("selenium")` + `collect_data_files("selenium")` (l'eseguibile
di Selenium Manager **non è** un modulo Python e va copiato a parte).

È esattamente il tipo di guasto che si scopre davanti al cliente, ed è la
ragione per cui esiste `--controllo`.

---

## Lista di controllo per il primo avvio su un PC vero

Nell'ordine. Se una riga fallisce, fermati lì.

1. **Procurati il `.exe`**: dalla build di GitHub o con `build.bat` (vedi
   `BUILD_WINDOWS.md`). Entrambe falliscono apposta se i test o il linter non
   passano. Alla fine: `dist\IstatUploader.exe`.

2. **Copia SOLO il `.exe`** su un PC che **non ha Python** — è l'unica prova che
   conta. Un PC con Python può mascherare un modulo mancante.

3. **Esegui il controllo del computer**, prima di qualunque cosa:
   ```powershell
   .\IstatUploader.exe --controllo
   ```
   Scrive anche in `%APPDATA%\UploaderTurismatica\controllo.txt` (un `.exe`
   senza console non ha dove stampare). Devono uscire **tre** ✓:
   impostazioni scrivibili · finestra · **Chrome si apre**.
   ⚠️ Il terzo è quello che conta: apre e chiude Chrome davvero, quindi prova
   Selenium Manager sul PC vero.

4. **Avvia normalmente** (doppio clic). Segna quanti secondi passano prima che
   compaia la finestra: con `onefile` si estrae in una temporanea a ogni avvio,
   e 5–15 s sono normali. Se dà fastidio, metti `ONEDIR = True` in
   `IstatUploader.spec` (avvio immediato, ma una cartella invece di un file solo).

5. **SmartScreen**: al primo avvio scaricato da internet comparirà
   *«Windows ha protetto il PC»* → «Ulteriori informazioni» → «Esegui
   comunque». Vedi sotto.

6. **Dichiara una struttura** e **scegli lo zip** scaricato da HostLab.

7. **Primo giro vero su UN SOLO MESE**, e guardando lo schermo. Le cose da
   verificare con gli occhi, perché nessun test le copre:
   - [ ] Chrome si apre sulla pagina di Turismatica;
   - [ ] compare il pannello **«Ora tocca a te»**, e **non scade** mentre fai
         SPID col telefono (prenditi due minuti apposta per verificarlo);
   - [ ] dopo «Sono dentro: vai» parte, e la riga di stato nomina i giorni;
   - [ ] un giorno **già caricato** viene saltato senza rumore
         (⭐ **rilancia lo stesso mese due volte**: la seconda deve dire
         «N già c'erano» e nient'altro);
   - [ ] il riepilogo finale si legge e si copia.

8. **Solo dopo**, metti dentro le altre strutture.

---

## Consegna su Windows

### Come si impacchetta

`PyInstaller` in modalità **onefile**: un `.exe` solo, che si scarica e si apre.
Niente Python da installare, niente cartelle. La ricetta è in
`IstatUploader.spec`; le versioni sono fissate in `requirements.txt` e
`requirements-dev.txt` (generati da `requirements*.in` con `uv pip compile`,
risolti **per Windows**: il comando è in testa a `requirements.in`).

### Quanto pesa

**Misurato**: il binario equivalente su Linux è **32 MB**. Su Windows attendersi
lo stesso ordine di grandezza (25–40 MB): dentro ci sono l'interprete Python,
pywebview per la finestra e Selenium. ⚠️ **Non è un numero verificato su Windows** —
lo dice il riepilogo della build su GitHub.

Cosa NON c'è dentro, ed è voluto: `webdriver_manager` (superfluo), e `numpy`,
`pandas`, `PIL`, `PyQt` & co. sono esclusi esplicitamente nella spec — non li
usiamo, e ogni MB in meno è una possibilità in meno di falso positivo antivirus.

**UPX è spento di proposito**: comprimerebbe del 30-40%, ed è il primo motivo di
falso positivo antivirus. Non vale lo scambio.

### SmartScreen, al primo avvio

Cosa succede davvero: il file non è firmato, quindi Windows mostra
*«Windows ha protetto il PC — App sconosciuta»* con un solo bottone visibile
(«Non eseguire»). Il modo di procedere è **«Ulteriori informazioni» → «Esegui
comunque»**, ed è nascosto apposta: un utente che non lo sa si ferma lì.

Tre strade, in ordine di costo:

1. **Non fare niente** e dirlo nel foglio delle istruzioni (è quello che fa
   `ISTRUZIONI.md`). Funziona, ma è un momento in cui l'utente ha paura.
2. **Firmare** con un certificato *code signing*. **Azure Trusted Signing** è la
   strada economica (~10 $/mese, richiede una verifica dell'identità
   dell'organizzazione). Toglie l'«App sconosciuta» e attenua l'avviso.
3. ⚠️ **Un certificato normale non basta subito**: SmartScreen si basa sulla
   **reputazione**, che si accumula con i download. Con un certificato OV
   l'avviso può comparire lo stesso per settimane; solo l'**EV** (più caro, con
   token hardware) dà reputazione immediata.

**Consiglio**: per i primi utenti la strada 1 basta — sono persone a cui il
file lo dai tu. Se un giorno lo si mette in download da HostLab, allora la 2.

⚠️ **Da mettere agli atti**: mandare un `.exe` su **WhatsApp o Gmail non
funziona** — li bloccano entrambi. Usa un link (Drive, WeTransfer) o una
chiavetta.

### ChromeDriver su un PC che non sappiamo com'è messo

**Non lo gestiamo più.** Lo script originale usava `webdriver_manager`, che
scarica il driver per conto suo ed è **la parte che si rompe al primo
aggiornamento di Chrome**: il PC si aggiorna da solo, il driver no, e da lì in
poi l'app non parte più con un messaggio che non dice niente.

Da Selenium 4.6 c'è **Selenium Manager**, dentro Selenium: guarda quale Chrome
c'è, scarica il driver **della versione giusta** e lo tiene in cache
(`%USERPROFILE%\.cache\selenium`). Quando Chrome si aggiorna, al giro dopo
scarica il driver nuovo da solo. Per questo `chrome.py` passa il minimo: **meno
gli si dice, meno c'è da tenere allineato.**

⭐ **Provato da dentro il binario congelato** (vedi sopra): ha trovato il browser
e scaricato il driver corrispondente. È la prova che serviva.

Cosa può ancora rompersi, e cosa dice l'app:

| guasto | quando | cosa dice |
|---|---|---|
| Chrome non installato | PC nuovo, o solo Edge | «Non trovo Google Chrome… installalo da google.com/chrome» |
| prima accensione senza rete | il driver va scaricato una volta | «controlla di essere online… serve solo la prima volta» |
| rete aziendale con proxy | uffici | stesso messaggio, con «prova col telefono in hotspot» |
| antivirus che blocca il driver | raro | messaggio generico + dettaglio tecnico in coda |

⚠️ **Edge e Firefox non vanno bene**: il portale è stato provato con Chrome, e
i selettori sono quelli.

---

## Com'è fatto

```
uploader_turismatica/
├── api.py           il flusso, una schermata per volta — provato col portale finto
├── finestra.py      pywebview: WebView2, trascinamento, scelta del file
├── ui/              l'interfaccia: index.html, app.css, app.js (locali)
├── sessione.py      il Portale (interfaccia) e la sua versione Selenium
├── riconoscimento.py le strutture dalla pagina + la copia ripulita — PURO
├── pagina_movimenti.py la pagina dei movimenti letta dall'HTML (righe, frecce, schede, invio mensile) — PURO
├── abbinamento.py   file → struttura, senza indovinare — PURO
├── piano.py         stato dei giorni e piano — PURO
├── messaggi.py      cosa dire al gestore — PURO
├── configurazione.py cosa si ricorda (dopo l'OK) — provato
├── periodo.py       il periodo — PURO, provato
├── sorgente.py      zip/cartella → file per giorno — PURO, provato
├── strutture.py     la cartella delle impostazioni (v1: elenco a mano, non più usato)
├── esito.py         il riepilogo per l'albergatore — PURO, provato
├── portale.py       la meccanica Turismatica — le DECISIONI sono pure e provate
│                    (anche la sequenza di un giorno, `carica_giorno`, e la
│                    prova), i selettori no (serve il portale: `_PassiSelenium`)
├── registro.py      il file di log accanto all'.exe, senza dati personali
├── chrome.py        avvio del browser
├── diagnostica.py   il controllo del computer (--controllo) e l'autoverifica
│                    dell'.exe per la build (--autoverifica <file>)
└── __main__.py      l'ingresso: finestra, --controllo, --autoverifica[-finestra]
```

Le **decisioni** stanno fuori da Selenium e dai widget apposta: è ciò che si può
provare senza portale e senza schermo, e in questo progetto è quasi tutto.

### Cosa è stato conservato dello script originale

La **meccanica del portale**, che è costata prove sul campo, è portata com'era —
non riscritta: riga per data, dialog PrimeFaces aperto via `PrimeFaces.ab`,
campo file nascosto reso visibile prima di scriverci, **tre tentativi** sul
bottone «Carica», lettura dello stato `VALIDATA`/`CESSATA`, **tre file mancanti
di fila** fermano la struttura, verifica che la tabella apra sul mese giusto.

> ⚠️ **Non semplificarli senza riprovare dal vivo.** Non sono scelte di stile:
> sono il risultato di tentativi contro un portale JSF che non si comporta come
> una pagina normale.

### Cosa è stato tolto, e perché

| tolto | perché |
|---|---|
| percorsi macOS, binario Chrome cablato | è un prodotto, non uno script personale |
| id struttura e nomi cartella cablati | sono dati personali. La struttura la dichiara l'utente, **una volta**, e resta salvata |
| elenco delle strutture cessate cablato | ⭐ **lo stato lo dice il portale**. Una lista scritta a mano è una seconda verità che invecchia da sola |
| `webdriver_manager` | vedi ChromeDriver, sopra |
| `tkcalendar` | la comunicazione è **mensile**: due campi data per dire «settembre» sono due occasioni di sbagliare. Un mese e un anno bastano, e sono una dipendenza in meno da impacchettare |
| il click automatico su «Accedi» + attesa di 30 s | ⚠️ **era un difetto vero**: dopo «Accedi» si va su SPID, che ci mette minuti. Trenta secondi lì è la differenza fra un'app che funziona e una che non funziona |

### Decisioni che vale la pena conoscere

- **Nessuna credenziale salvata, e non per prudenza: non ce ne sono.** L'accesso
  è SPID/CIE e lo fa la persona nel browser. `strutture.json` contiene un numero
  pubblico, un'etichetta e un percorso — c'è un test che lo verifica.
- **Le impostazioni stanno in `%APPDATA%`, non accanto al `.exe`**: un eseguibile
  in Download dev'essere sostituibile senza perdere le strutture, e in
  `Program Files` non si può scrivere.
- ⭐ **«già caricato» non è un errore.** Rilanciare sullo stesso mese dev'essere
  innocuo: se «già c'era» comparisse come problema, l'utente non rilancerebbe
  mai — nemmeno quando serve.
- ⚠️ **«non riuscito» e «file mancante» non si fondono**, che è la tentazione
  naturale quando si conta solo il successo: sono la stessa riga non toccata con
  due significati opposti e due rimedi diversi (uno si risolve in HostLab,
  l'altro sul portale).
- **Lo zip si estrae in sicurezza**: solo i `.txt`, e solo dentro la cartella
  temporanea. Lo zip lo fa HostLab, ma il campo lo riempie l'utente e può
  scegliere qualunque file (`zip slip`).
- ⚠️ **La data si legge dal NOME del file, non dal contenuto.** Il file è il
  movimento di un giorno e il portale ha una riga per giorno: caricarlo sulla
  riga sbagliata è una dichiarazione falsa fatta a nome del gestore. Un nome che
  non dichiara una data **non si carica** — finisce fra i «non riconosciuti»,
  che è diverso da tacere.

### I due nomi di file che esistono davvero

Non se ne inventa un terzo, e non si chiede all'utente di rinominare niente:

| forma | chi la scrive |
|---|---|
| `schedine_istat_<idBooking>_<AAAAMMGG>.txt` | HostLab (`sync/istat_export.py`), ed è ciò che c'è nello zip |
| `GGMMAAAA.txt` | lo script originale |

⚠️ **L'`<idBooking>` nel nome di HostLab NON è l'id Turismatica**: è l'id della
struttura su beb.it. Sono due numeri diversi e non si deducono l'uno dall'altro
— **è la ragione per cui la struttura la dichiara l'utente** invece di essere
indovinata dal nome del file.

⚠️ Le due convenzioni sono **ambigue fra loro** (`01022026` è il 1° febbraio
letto GGMMAAAA): si decide dal **prefisso del nome**, che è un fatto, non dalla
plausibilità della data, che è un indovinello. C'è un test apposta.

---

## Sviluppo

```bash
uv venv && uv pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q          # 196 test
.venv/bin/python scripts/zip_di_prova.py dist/prova-settembre-2026.zip
.venv/bin/python -m ruff check .
.venv/bin/python -m uploader_turismatica            # la finestra
.venv/bin/python -m uploader_turismatica --controllo
```

## Non in questo giro

Il bottone dentro HostLab (`hostlab://istat?…`). Prima l'app deve funzionare
lanciata a mano.
