# Istat Uploader: installazione a mano su Chrome (Windows)

Per ora l'estensione non passa dal Chrome Web Store: la installa Marco sul PC del gestore come
«estensione non pacchettizzata». Serve lo zip `IstatUploader-<versione>.zip`
(`python estensione/strumenti/pacchetto.py` lo mette in `dist/`).

## Installare (una volta per PC)

1. **Cartella.** Tasto destro sullo zip → «Estrai tutto…» → come destinazione scrivi
   `C:\Users\<nome utente>` (senza «IstatUploader»: la cartella è già dentro lo zip).
   Risultato: `C:\Users\<nome utente>\IstatUploader\manifest.json`.
   Mai in Download, sul Desktop o in Documenti: li svuota chi fa pulizia, e Desktop e Documenti
   spesso li sincronizza OneDrive, che può lasciare i file solo in cloud. Se la cartella sparisce,
   l'estensione smette di funzionare e va reinstallata.
2. **Modalità sviluppatore.** In Chrome apri `chrome://extensions` e accendi «Modalità
   sviluppatore» in alto a destra.
3. **Carica.** «Carica estensione non pacchettizzata» → scegli la cartella `IstatUploader`
   (quella con dentro `manifest.json`) → «Seleziona cartella». Compare la scheda «Istat Uploader
   per Turismatica», accesa.
4. **Fissala nella barra.** Icona del puzzle in alto a destra → puntina accanto a «Istat
   Uploader per Turismatica». Si apre col clic sull'icona, e il tasto «Carica su Turismatica» di
   HostLab la trova da solo.
5. **Prova.** Clic sull'icona: si apre la pagina «Trascina qui lo zip». Si parte sempre in
   modalità prova.

La Modalità sviluppatore resta accesa: se si spegne, l'estensione non pacchettizzata si disattiva.

## L'avviso di Chrome all'avvio

Le versioni vecchie di Chrome, all'apertura, mostravano un fumetto «Disattiva le estensioni in
modalità sviluppatore». Le fonti che ho trovato dicono che non compare più, ma non c'è una pagina
ufficiale che lo confermi. Se compare: si chiude con la **X**, mai «Disattiva». Se qualcuno l'ha
già premuto: `chrome://extensions` → riaccendi l'interruttore della scheda. Abbinamenti e
impostazioni non si perdono.

## Aggiornare a una versione nuova (senza reinstallare)

1. Chiudi la pagina dell'estensione, se è aperta (non durante un caricamento).
2. «Estrai tutto…» del nuovo `IstatUploader-<versione>.zip` **nella stessa destinazione**
   `C:\Users\<nome utente>` → «Sostituisci i file nella destinazione».
3. `chrome://extensions` → sulla scheda dell'estensione premi la freccia circolare «Ricarica».
   Il numero di versione sulla scheda deve essere quello nuovo.

Stessa cartella = stesso id: restano la puntina nella barra e gli abbinamenti salvati, e HostLab
la trova come prima. Spostarla o rinominarla equivale a reinstallarla da zero.
