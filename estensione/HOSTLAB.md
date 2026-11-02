# Per la sessione serale di HostLab

Il repository di HostLab non è stato letto né toccato: i punti 3 e 4 sono da verificare lì.

1. **Il tasto.** Copia `docs/hostlab-tasto.js` nel report ISTAT e collegalo a «Carica su Turismatica»:

   ```js
   import { caricaSuTurismatica } from "./hostlab-tasto.js";
   tasto.addEventListener("click", () => caricaSuTurismatica({
     creaGettone,      // la chiamata di oggi, che risponde col gettone monouso
     proponi({ conExe }) { /* il riquadro del punto 2 */ },
     avvisa(testo) { /* messaggio a chi ha premuto */ },
   }));
   ```

   Se l'estensione c'è, `<html data-istat-uploader="…">` è già lì; il gettone si chiede dopo, gli si manda con
   `postMessage`, e lei si apre e ritira il pacchetto. Non serve conoscere il suo id, diverso fra Chrome, Edge e prove.
2. **Il riquadro se manca**: «Installa l'estensione» con il link al Web Store (lo avrai dopo la pubblicazione) e,
   sotto, «Oppure usa il programma per Windows», che chiama `conExe()`: apre `hostlab-turismatica://carica/<gettone>`
   come oggi. Su browser che non sono Chrome o Edge resta solo il programma, e il link al Web Store non si mostra.
3. **`POST /turismatica/pacchetto`**: l'estensione lo chiama con `Authorization: Bearer <gettone>`, senza cookie, con
   `Origin: chrome-extension://<id>`. Il browser non applica CORS perché il dominio è nei permessi; se il server
   filtra per `Origin` o CSRF, questa rotta deve lasciarla passare. Restano `X-Struttura`, `X-Mese` e il corpo JSON
   `{"errore": …}` di adesso. Zip entro 5 MB.
4. **CSP e domini**: se il report ha una CSP, deve permettere il modulo del tasto. Se HostLab gira anche su domini
   diversi da `hostlab.umbriaround.it` (tenant con dominio proprio), dimmelo: vanno nel manifest, e la versione
   nuova chiede di nuovo il permesso a chi l'ha installata.
5. **Non toccare** la rotta dell'exe: resta il ripiego.
