# Estensione Istat Uploader

Prova: caricare il mese su Turismatica dentro il Chrome del gestore, dopo il suo SPID, senza exe.
Si lancia: `python estensione/strumenti/pacchetto.py`, poi `chrome://extensions` → Modalità sviluppatore → «Carica estensione non pacchettizzata» sulla cartella estratta.
È emerso: sul portale vero, con SPID, la modalità prova arriva fino a «Carica» pronto; manca il caricamento vero (vedi `PROJECT_STATUS.md`). Pubblicazione: `PUBBLICAZIONE.md`.

## La prova in modalità sviluppatore

1. Estrai lo zip in una cartella che non cancellerai, e in Chrome apri `chrome://extensions`.
2. Accendi «Modalità sviluppatore» e premi «Carica estensione non pacchettizzata», scegliendo la cartella.
3. Premi l'icona dell'estensione (puzzle → Istat Uploader) e trascina lo zip del mese: parte sempre in prova.

## Com'è fatta

| pezzo | cosa fa |
|---|---|
| `src/carica.html`, `carica.js`, `carica.css` | la scheda dell'estensione: l'interfaccia |
| `src/flusso.js` | il flusso, una schermata per volta (port di `api.py`) |
| `src/portale.js` | la meccanica su Turismatica (port di `portale.py`) |
| `src/logica/` | logica pura: nomi dei file, zip, abbinamento, piano, esito, lettura delle pagine, registro |
| `src/hostlab.js` | il ritiro del pacchetto col gettone |
| `src/ponte-hostlab.js`, `sfondo.js` | il ponte con la pagina di HostLab e il service worker |
| `docs/hostlab-tasto.js` | il codice del tasto, da copiare in HostLab (il banco serve questo stesso file) |

Il Python dell'uploader resta la fonte delle regole: un test confronta le due letture sulle stesse copie.
L'exe non dipende da niente di qui.

## Le prove

```bash
node --test estensione/test/*.mjs                              # logica pura e flusso, senza browser
.venv/bin/python -m pytest estensione/test/test_estensione.py  # Chromium vero, guidato dal server MCP di DevTools
```

I test accendono il banco (`test/banco.py`): finto Turismatica con PrimeFaces 6.2 vero e finto HostLab, in HTTPS
sui loro nomi veri, mappati su 127.0.0.1 da Chromium. Ogni altro nome non si risolve. Le risposte del server JSF
sono scritte da noi: dicono cosa abbiamo capito del portale, non come si comporta.
Profilo dedicato in `dist/profilo-prove`, che i test ricreano.
