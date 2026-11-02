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
3. **`POST /turismatica/pacchetto`**: l'estensione lo chiama sull'indirizzo del tenant che ha premuto il tasto, con `Authorization: Bearer <gettone>`, senza cookie, con
   `Origin: chrome-extension://<id>`. Il browser non applica CORS perché il dominio è nei permessi; se il server
   filtra per `Origin` o CSRF, questa rotta deve lasciarla passare. Restano `X-Struttura`, `X-Mese` e il corpo JSON
   `{"errore": …}` di adesso. Zip entro 5 MB.
4. **CSP e domini**: se il report ha una CSP, deve permettere il modulo del tasto. L'estensione copre tutti i
   sottodomini di `umbriaround.it`, presenti e futuri. Un cliente con dominio proprio oggi non è coperto: quando
   arriverà si aggiunge un permesso facoltativo, senza disattivare l'estensione a chi l'ha già.
5. **Il ripiego exe è da sistemare**: l'exe ritira il pacchetto da `hostlab.umbriaround.it`, scritto nel suo codice
   (`da_hostlab.py`, `SERVER`). Se quell'indirizzo è ritirato, dal tasto di HostLab l'exe non funziona più: o resta
   attivo un indirizzo per l'exe, o va pubblicata una versione nuova, o il riquadro non lo propone.
