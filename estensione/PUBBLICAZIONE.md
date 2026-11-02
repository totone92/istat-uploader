# Pubblicazione: i passi nelle dashboard

Versione 0.1.1. Zip: `istat-uploader-estensione-0.1.1.zip`. Schermate: `scheda-store/`. Le voci segnate **[tu]** le sai solo tu.
Nomi dei campi presi dalla documentazione di Google e Microsoft, verificata il 2/11/2026: la dashboard può chiamarli in modo leggermente diverso.

## Prima dell'invio

1. Fai un giro **in modalità vera** su un mese solo. La prova del 2/11 è arrivata fino a «Carica» pronto sul portale vero, ma il caricamento vero non è ancora stato visto: se serve correggere, è meglio farlo prima della revisione.
2. Controlla che `privacy@fortitudolab.it` riceva davvero la posta: è pubblicata nella privacy policy.

## Chrome Web Store, visibilità privata

### 1. Account (una volta sola)

Da https://chrome.google.com/webstore/devconsole, con l'account Google che vuoi tenere: l'email dello sviluppatore non si cambia più.

| Campo | Valore |
|---|---|
| Quota di registrazione | una tantum: l'importo lo mostra la dashboard |
| Publisher name | **[tu]** |
| Contact email | **[tu]**, da verificare |
| Trader / Non-trader | **[tu]**: vedi «Operatore commerciale» qui sotto |
| Trusted tester accounts | **[tu]** `email-cliente-1, email-cliente-2, email-tua`: account Google, separati da virgola, niente indirizzi di gruppo |

### 2. Carica lo zip

**Items → New item →** `istat-uploader-estensione-0.1.1.zip`. Nome, versione e descrizione breve arrivano dal manifest.

### 3. Store listing

| Campo | Valore |
|---|---|
| Description | il blocco qui sotto |
| Category | Productivity (se chiede una sottocategoria: Workflow & Planning) |
| Language | Italian |
| Store icon | `src/icone/icona-128.png` |
| Screenshots | `1-benvenuto.png`, `2-piano.png`, `3-esito.png` |
| Homepage URL | lascia vuoto |
| Support URL | lascia vuoto |
| Mature content | No |

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

### 4. Privacy

**Single purpose description**

```
Caricare sul portale Turismatica della Regione Umbria i file ISTAT giornalieri scelti dal gestore della struttura.
```

**Permissions justification**

`scripting`

```
Serve a guidare la pagina dei movimenti di Turismatica nella scheda aperta dal gestore: legge quali giorni sono già caricati, sceglie la struttura, apre la finestra di caricamento del giorno, inserisce il file scelto dal gestore e preme «Carica» solo in modalità vera, dopo due conferme. Tutto il codice eseguito è dentro il pacchetto.
```

Host `https://turismatica.regione.umbria.it/*`

```
È il portale su cui il gestore carica i movimenti. Serve per leggere le pagine dei movimenti, riconoscere quando è entrato con SPID o CIE, e caricare i file del giorno.
```

Host `https://*.umbriaround.it/*`

```
Ogni cliente del gestionale HostLab ha il proprio indirizzo su un sottodominio di umbriaround.it, e i clienti nuovi ne ricevono uno nuovo. Il tasto «Carica su Turismatica» di HostLab passa all'estensione un gettone monouso e l'estensione ritira il pacchetto del mese da quello stesso indirizzo. Sulle stesse pagine gira un piccolo script che segnala a HostLab che l'estensione è installata e riceve il gettone: non legge il contenuto della pagina. Il dominio umbriaround.it è del gestionale, e l'accesso è limitato a quello.
```

**Are you using remote code?** No, I am not using remote code.

**Data usage**: spunta solo **Website content**. Tutte le altre no. Poi le tre certificazioni: non vendo i dati a terzi; non li uso per finalità estranee alla funzione unica; non li uso per valutare il merito creditizio.

**Privacy policy URL**

```
https://totone92.github.io/istat-uploader/
```

### 5. Distribution

| Campo | Valore |
|---|---|
| Payments | Free |
| Visibility | **Private**, con **Only trusted testers from the current publisher settings** |
| Regions | Italy |

### 6. Invio

**Submit for review.** Se la dashboard chiede istruzioni per il revisore:

```
Per entrare su Turismatica serve un accesso SPID o CIE di un gestore: non possiamo fornirne uno. Senza accesso si vedono la schermata iniziale, il caricamento dello zip e il passaggio alla pagina di login del portale. L'estensione parte sempre in modalità prova e non cambia niente sul portale senza due conferme.
```

Spunta la pubblicazione automatica a fine revisione. Se la togli, hai 30 giorni per pubblicare, poi torna bozza.

### 7. Dopo la pubblicazione

Manda ai tester l'indirizzo della scheda: devono avere aperto Chrome con l'account Google indicato. Comunicami l'indirizzo, serve al riquadro del tasto di HostLab.

### A gennaio, con la partita IVA

Aggiorna il trader se serve, poi **Distribution → Visibility → Public** e ripubblica. L'id dell'estensione non cambia.

## Operatore commerciale: cosa dicono le fonti

- La dichiarazione è **per account** ed è obbligatoria per tutti, anche con la sola scheda privata.
- Conta lo scopo (attività o professione), non la partita IVA, e la decisione è tua: Google non risponde sul caso singolo.
- Da trader servono nome legale, telefono verificabile via SMS, indirizzo e un profilo pagamenti.
- Google scrive che questi dati sono «posted publicly» in fondo alla scheda e **non dice se con la scheda privata li vedono solo i tester**. Dato che una scheda privata la possono aprire solo loro, è probabile, ma è una deduzione mia. Metti comunque un indirizzo che accetti di rendere pubblico.
- Lo stato si può cambiare dopo. Prima di dichiararti non-trader per un servizio ai clienti, senti il commercialista.

## Edge Add-ons, modalità nascosta (seconda via)

Da https://partner.microsoft.com/dashboard/microsoftedge. Gratuito. **Individual/Company e il paese non si cambiano dopo**: scegli **[tu]**.

1. **Create new extension** → carica lo stesso zip.
2. **Availability**: Visibility **Hidden**; Markets **Change markets** → solo Italy.
3. **Properties**: Category **Productivity**; Website vuoto; Support contact `privacy@fortitudolab.it`; Mature content no.
4. **Privacy**: stessi testi di Chrome per Single Purpose Description e Permission justification; «Are you using remote code?» **No**; Data usage come sopra; Privacy Policy URL `https://totone92.github.io/istat-uploader/`.
5. **Store listings**, lingua italiano: Extension name `Istat Uploader per Turismatica`; Description il blocco di Chrome (minimo 250 caratteri, è più lungo); logo `icona-128.png` (il minimo accettato; 300×300 è il consigliato); le tre schermate; Search terms vuoto.
6. **Publish**, in «Notes for certification» lo stesso testo per il revisore.
7. Certificazione fino a 7 giorni lavorativi. Poi manda ai clienti l'indirizzo della scheda: su Edge non c'è un elenco di tester, chi ha il link installa.

Nota: su Edge l'estensione ha un id diverso. Il tasto di HostLab non ne risente, perché non usa l'id.
