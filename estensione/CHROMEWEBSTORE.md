# Chrome Web Store Listing — Istat Uploader per Turismatica

> Last Updated: 2026-11-02

## Store Listing

**Extension Name**

Istat Uploader per Turismatica

**Short Description** (manifest, massimo 132 caratteri)

Carica su Turismatica (Regione Umbria) i movimenti ISTAT del mese, un giorno alla volta, dopo il tuo accesso SPID o CIE.

**Detailed Description**

```
Carica su Turismatica, il portale della Regione Umbria, i file ISTAT giornalieri del mese: un giorno alla volta, dentro il tuo browser, dopo che sei entrato con SPID o CIE.

Per chi gestisce una struttura ricettiva in Umbria e ha già i file ISTAT giornalieri. Invece di caricare a mano trenta file al mese, trascini lo zip e controlli il risultato.

Cosa fa:
• Legge dal portale le tue strutture e i giorni già caricati.
• Abbina i file alla struttura giusta e, se non è certo, chiede a te.
• Ti dice prima cosa caricherà e cosa c'è già.
• Parte sempre in modalità prova: arriva fino al pulsante «Carica» e si ferma, senza cambiare niente sul portale.
• In modalità vera chiede due conferme, salta i giorni già caricati e rilegge ogni riga dopo il caricamento.
• A fine giro dà un riepilogo chiaro di cosa è a posto e cosa resta da fare, e un registro scaricabile senza dati personali.
• Se vuoi, come ultimo passo invia la comunicazione mensile del mese concluso, con una conferma tua.

Come si usa:
1. Premi l'icona dell'estensione e trascina lo zip del mese, oppure premi «Carica su Turismatica» in HostLab.
2. Nella scheda del portale entra con SPID o CIE, come fai sempre.
3. Controlla il piano, avvia la prova e, se l'elenco torna, passa alla modalità vera.

Privacy: i file restano nella memoria della scheda per il tempo del caricamento e vanno solo a Turismatica. Le credenziali SPID e CIE le inserisci tu sul portale: l'estensione non le vede. Nessuna analisi d'uso, nessuna pubblicità.

Non è un servizio della Regione Umbria.
```

**Category**: Productivity (Workflow & Planning)

**Single Purpose**

Caricare sul portale Turismatica della Regione Umbria i file ISTAT giornalieri scelti dal gestore della struttura.

**Primary Language**: Italiano

## Graphics & Assets

| Asset | Dimensions | Status | Filename |
|-------|-----------|--------|----------|
| Store Icon | 128×128 PNG | ✅ Ready | `src/icone/icona-128.png` |
| Screenshot 1 | 1280×800 | ✅ Ready | `scheda-store/1-benvenuto.png` |
| Screenshot 2 | 1280×800 | ✅ Ready | `scheda-store/2-piano.png` |
| Screenshot 3 | 1280×800 | ✅ Ready | `scheda-store/3-esito.png` |
| Small Promo Tile | 440×280 | ⬜ Not created (facoltativa) | |

Le schermate hanno dati inventati (TENANT A) e le rifà il test `test_schermate_per_la_scheda_store`.

## Permissions Justification

| Permission | Type | Justification |
|------------|------|---------------|
| `scripting` | permissions | Serve a guidare la pagina dei movimenti di Turismatica nella scheda aperta dal gestore: legge quali giorni sono già caricati, sceglie la struttura, apre la finestra di caricamento del giorno, inserisce il file scelto dal gestore e preme «Carica» solo in modalità vera, dopo due conferme. Tutto il codice eseguito è dentro il pacchetto. |
| `https://turismatica.regione.umbria.it/*` | host_permissions | È il portale su cui il gestore carica i movimenti. Serve per leggere le pagine dei movimenti, riconoscere quando è entrato con SPID o CIE, e caricare i file del giorno. |
| `https://*.umbriaround.it/*` | host_permissions | Ogni cliente del gestionale HostLab ha il proprio indirizzo su un sottodominio di umbriaround.it, e i clienti nuovi ne ricevono uno nuovo. Il tasto «Carica su Turismatica» di HostLab passa all'estensione un gettone monouso e l'estensione ritira il pacchetto del mese da quello stesso indirizzo. Sulle stesse pagine gira un piccolo script che segnala a HostLab che l'estensione è installata e riceve il gettone: non legge il contenuto della pagina. Il dominio umbriaround.it è del gestionale, e l'accesso è limitato a quello. |

Lo script di contenuto gira solo sui sottodomini di `umbriaround.it`. Nessun permesso facoltativo: oggi non ci sono domini propri dei clienti. Si aggiungerà quando servirà, perché aggiungerne uno facoltativo non disattiva l'estensione a chi l'ha già. **Remote code**: No, tutto il codice è nel pacchetto.

## Privacy & Data Use

**Does the extension collect user data?** Sì per il modulo: tratta dati nel browser dell'utente, non li raccoglie per sé.

| Data Type | Collected? | Transmitted Off-Device? | Purpose | Shared with Third Parties? |
|-----------|-----------|------------------------|---------|---------------------------|
| Personally identifiable info | No | No | | No |
| Health info | No | No | | No |
| Financial info | No | No | | No |
| Authentication info | No: l'accesso SPID/CIE lo fa la persona sul portale; il gettone monouso di HostLab non si conserva | Il gettone solo a HostLab, per il ritiro | Ritiro del pacchetto | No |
| Personal communications | No | No | | No |
| Location | No | No | | No |
| Web history | No | No | | No |
| User activity | No | No | | No |
| Website content | Sì: le pagine dei movimenti, lette in memoria per sapere i giorni caricati; i file ISTAT scelti dal gestore | Solo a Turismatica, su richiesta del gestore e solo in modalità vera | L'unica finalità dell'estensione | No |

Da spuntare nel modulo, tutte vere:
- [x] Data is NOT sold to third parties
- [x] Data is NOT used for purposes unrelated to the extension's core functionality
- [x] Data is NOT used for creditworthiness or lending purposes

## Privacy Policy

**Privacy Policy URL**: ✅ https://totone92.github.io/istat-uploader/ (ramo `gh-pages`; la fonte è `PRIVACY.md`, da ricopiare se cambia).

## Distribution

**Visibility**: Private con trusted testers (i due clienti e Marco); Public a gennaio. Stessa revisione. I passi sono in `PUBBLICAZIONE.md`.
**Regions**: Italia

## Developer Info

**Publisher Name**: ⬜ da decidere con la dichiarazione trader (vedi `PROJECT_STATUS.md`)
**Contact Email**: ⬜ da inserire (è pubblica sulla scheda)
**Support URL / Email**: ⬜
**Homepage URL**: ⬜

## Version History

| Version | Date | Changes | Status |
|---------|------|---------|--------|
| 0.1.1 | 2026-11-02 | Indirizzi dei tenant su umbriaround.it | Draft |
| 0.1.0 | 2026-11-02 | Prima versione: prova e vera, zip a mano e tasto di HostLab, comunicazione mensile (mai inviata allo store) | Draft |

## Review Notes

### Known Issues / Limitations
Per il revisore: serve un accesso SPID o CIE a Turismatica di un gestore reale, che non possiamo fornire. Lo zip si carica e la schermata del login si vede anche senza accesso.

### Rejection History
Nessuna.
