// Cosa dire al gestore quando qualcosa non va: cosa è successo e cosa fare (messaggi.py).

import { ddmmaaaa } from "./periodo.js";

export const strutturaNonTua = (id) => `La struttura ${id} non è fra quelle del tuo account `
  + "Turismatica. Controlla il numero, oppure rientra con lo SPID di chi gestisce quella struttura.";

export const uscitoDalPortale = () => "Il portale ti ha fatto uscire (la sessione è scaduta). Riprova: ti "
  + "chiederò di entrare di nuovo con SPID o CIE.";

export const fileMancanteFermo = (giorno) => `Manca il file del ${ddmmaaaa(giorno)}: i giorni dopo restano fermi `
  + "finché non c'è quello.";

export const GIORNO_NON_APERTO = "il portale non apre questo giorno (di solito manca ancora quello prima).";
export const GIORNO_FILE_RIFIUTATO = "il portale non ha accettato il file scelto.";
export const GIORNO_DIALOG_APERTO = "ho premuto «Carica» ma il portale non ha chiuso la finestra, e il giorno non "
  + "risulta caricato.";
export const GIORNO_NON_CONFERMATO = "ho premuto «Carica» e la finestra si è chiusa, ma riletta la riga il giorno "
  + "non risulta caricato.";
export const GIORNO_SMENTITO = "riletto il mese a fine giro, sul portale questo giorno non risulta caricato.";
export const GIORNO_ERRORE = "il portale ha dato un errore su questo giorno (il dettaglio è nel registro).";

export const statoNonRiletto = (mese) => `non sono riuscito a rileggere ${mese} a fine giro. `
  + "Riapri il portale e guarda il mese nella pagina dei movimenti.";

export const strutturaNonAttiva = (id, stato) => `Sul portale la struttura ${id} risulta «${stato.toLowerCase()}»: `
  + "i movimenti non si possono caricare. Se è un errore, va sistemato con la Regione.";

export const movimentiNonAperti = (id) => `Il portale non ha aperto la pagina dei movimenti della struttura ${id}. `
  + "Riprova fra qualche minuto; se succede ancora, scarica il registro da «Dettagli» e mandalo.";

export const meseNonRaggiunto = (mostrato, voluto) => `Il portale mostra ${mostrato} e non sono riuscito a passare a ${voluto}. `
  + `Apri tu ${voluto} sul portale, nella pagina dei movimenti, poi riprova: il portale ricorda l'ultimo mese aperto.`;

export const strutturaDiversa = (id) => `Ho chiesto al portale la struttura ${id} ma ne ha aperta `
  + "un'altra, anche passando dalla scelta della struttura. Non carico niente per non sbagliare "
  + "struttura: scarica il registro da «Dettagli» e mandalo.";

export const meseChiuso = (mese) => `${mese} è già chiuso sul portale (la comunicazione mensile è fatta): `
  + "i movimenti non si possono più caricare né cambiare.";

export const meseChiusoNonLetto = (mese) => `${mese} non è più fra i mesi aperti del portale (risulta chiuso), ma non `
  + "sono riuscito a leggerne i giorni nella scheda «Movimento periodo chiuso». Non serve fare "
  + "niente: un mese chiuso non si carica più.";

export const STRUTTURE_NON_LETTE = "Sono entrato nel portale ma non trovo nessuna struttura. Può darsi che al "
  + "tuo codice fiscale non ne risulti nessuna, oppure che non sia riuscito a leggere la pagina. Se ne "
  + "hai, scrivi qui sotto il numero di ognuna: lo trovi nell'indirizzo della pagina dei movimenti, dopo "
  + "«idStruttura=». Se non ne hai, premi Annulla: non è successo niente. Ho preparato una copia della "
  + "pagina senza dati personali: la scarichi da «Dettagli» e la mandi a chi ti assiste.";

export const zipNonValido = (dettaglio) => `${dettaglio} Scegli lo zip dei file ISTAT del mese.`;

export const nessunFileIstat = (nome) => `In «${nome}» non ho trovato file ISTAT giornalieri `
  + "(schedine_istat_…_AAAAMMGG.txt oppure GGMMAAAA.txt). È lo zip giusto?";

export const SEGNI_USCITA = ["accedi con spid", "entra con spid", "sessione scaduta", "sessione è scaduta"];

const SEGNI_NEGATO = ["non autorizzat", "accesso negato", "non abilitat", "non hai i permessi",
  "struttura non trovata", "errore 403", "forbidden"];
const URL_USCITA = ["login", "spid", "/idp", "logout"];

export function percheMovimentiNonAperti(id, { url, testoPagina, struttureNote }) {
  const testo = testoPagina.toLowerCase();
  if (struttureNote.size && !struttureNote.has(id)) return strutturaNonTua(id);
  if (SEGNI_NEGATO.some((s) => testo.includes(s))) return strutturaNonTua(id);
  if (URL_USCITA.some((s) => url.toLowerCase().includes(s)) || SEGNI_USCITA.some((s) => testo.includes(s))) {
    return uscitoDalPortale();
  }
  return movimentiNonAperti(id);
}
