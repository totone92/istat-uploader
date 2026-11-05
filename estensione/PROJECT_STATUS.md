# Stato dell'estensione (5 novembre 2026)

Ramo `estensione-chrome` su GitHub, versione 0.1.1. Non fonderlo in `main` senza Marco: rifarebbe la build dell'exe.
Privacy policy: https://totone92.github.io/istat-uploader/ (ramo `gh-pages`). Passi delle dashboard: `PUBBLICAZIONE.md`.

## Dove riprendere

- **Direzione del 5/11**: niente exe ai clienti e Web Store rinviato. Marco installa l'estensione a mano
  («non pacchettizzata») sui PC dei clienti: zip `dist/IstatUploader-<versione>.zip` da
  `strumenti/pacchetto.py`, guida e aggiornamento in `INSTALLAZIONE-A-MANO.md`. Una versione nuova va
  estratta sempre nella stessa cartella, o cambia l'id e si perdono gli abbinamenti.
- **La prova in modalità prova è andata** sul portale vero il 2/11 (v0.1.0): SPID, 8 strutture lette, ingresso da
  prehome, dialog aperto e file accettato fino a «Carica» pronto. **Manca la modalità vera**, su un mese solo.
  Se qualcosa non va: «Dettagli» → «Scarica il registro», più le copie ripulite delle pagine non lette.
- **HostLab**: la modifica al tasto è in `HOSTLAB.md`, per la sessione serale.
- **Server MCP di DevTools in sessione**: è in `.mcp.json` nella radice del repo. Una sessione già aperta non lo
  carica: riavviare Claude Code dalla radice del repo, approvare il server, e accendere il banco con
  `.venv/bin/python estensione/test/banco.py` se si vuole guardare. Chromium in quella configurazione raggiunge
  solo il banco, mai i siti veri. I test non ne hanno bisogno: aprono lo stesso server da soli.

## Cosa è provato e cosa no

Provato su Chromium 156, con PrimeFaces 6.2 vero e **risposte del server JSF scritte da noi**: lettura, prova,
vera con i byte dei file (nei nomi di beb, generati con CIN e senza CIN), sessione scaduta, zip, gettone, comunicazione mensile.
Non provato sul portale vero: il caricamento e la sua conferma, i giorni dopo il primo, frecce dei mesi accese, scheda «Movimento periodo chiuso», comunicazione.
Non provato su Chrome di marca, Edge, Windows e Mac: stesso motore, ma nessun giro fatto lì.

## Web Store: cosa è stato verificato alle fonti (2/11/2026)

- **Quota**: una tantum, obbligatoria. Le pagine ufficiali non dicono l'importo; 5 $ è la cifra riferita da un utente, la dashboard mostra quella vera.
- **Trader**: la dichiarazione è obbligatoria e la decide chi pubblica, Google non risponde sul caso singolo.
  Conta lo scopo (attività, mestiere, professione), non la partita IVA: le pagine lette non la chiedono, e può
  esserlo anche una persona fisica. Al trader chiedono nome legale, telefono verificato via SMS e indirizzo, e
  **li pubblicano in fondo alla scheda**. Da non-trader i clienti vengono informati che non hanno i diritti
  dei consumatori. Le pagine non dicono cosa succede a chi dichiara il falso né se la pubblicazione privata cambi l'obbligo.
- **Prova con due clienti**: `Private`, con i tester nell'account (senza un massimo dichiarato, Workspace non serve). Stessa revisione.
- **Revisione**: «within a few days», fino a qualche settimana; oltre tre settimane si scrive al supporto. Privacy policy: serve, con link nel campo apposito.
- **Edge Add-ons**: gratis, `Hidden` come modalità nascosta, certificazione fino a 7 giorni lavorativi, privacy
  policy richiesta; niente su trader o DSA nelle pagine lette. Individual/Company non si cambia dopo.
  Da Edge si può anche installare dal Chrome Web Store, ma non l'ho verificato alla fonte.
