// Un giorno, dall'inizio alla fine (portale.carica_giorno). In prova si fa tutto
// tranne `conferma`: la sola differenza fra le due modalità sta qui, in una riga.
// Un giorno già caricato non si tocca in nessuna delle due: ricaricarlo lo
// sostituirebbe. Un dialog chiuso non è un giorno caricato: lo dice la riga riletta.

import { Esito } from "./esito.js";
import { giornoGiaCaricato } from "./lettura.js";
import {
  GIORNO_DIALOG_APERTO, GIORNO_FILE_RIFIUTATO, GIORNO_NON_APERTO, GIORNO_NON_CONFERMATO,
} from "./messaggi.js";

export async function caricaGiorno(passi, giorno, file, { prova, inCoda = false, motivi = null }) {
  if (typeof prova !== "boolean") throw new TypeError("prova va detto: dimenticarlo non deve voler dire caricare");
  const nonRiuscito = (motivo) => {
    if (motivi) motivi[giorno] = motivo;
    return Esito.NON_RIUSCITO;
  };
  const riga = await passi.riga(giorno);
  if (riga && giornoGiaCaricato(riga.celle, riga.classi, riga.titoli)) return Esito.GIA_CARICATO;
  // Il portale apre il caricamento solo sul primo giorno non inserito: in prova i
  // giorni dopo non hanno il bottone, e non è un fallimento.
  if (prova && inCoda) return Esito.DA_CARICARE;
  if (!await passi.apriDialog(giorno)) return nonRiuscito(GIORNO_NON_APERTO);
  await passi.scegliFile(file);
  if (prova) {
    const pronto = await passi.pronto();
    await passi.annulla();
    return pronto ? Esito.DA_CARICARE : nonRiuscito(GIORNO_FILE_RIFIUTATO);
  }
  const chiuso = await passi.conferma();
  if (!chiuso) await passi.annulla();
  if (await passi.caricato(giorno)) return Esito.CARICATO;
  return nonRiuscito(chiuso ? GIORNO_NON_CONFERMATO : GIORNO_DIALOG_APERTO);
}

/** Il primo giorno prima del periodo che il portale non ha e di cui non c'è il file. */
export function primoBuco(righe, perGiorno, primaDi) {
  const ordinate = [...righe].sort((a, b) => (a.giorno < b.giorno ? -1 : 1));
  const r = ordinate.find((x) => x.giorno < primaDi && !x.caricato && !perGiorno.has(x.giorno));
  return r ? r.giorno : null;
}

/** Si può caricare su una struttura in questo stato? Senza etichetta sì: fermarsi
 *  per un'etichetta non letta vorrebbe dire non caricare mai. */
export const statoUtilizzabile = (stato) => !stato || stato.trim().toUpperCase() === "VALIDATA";

/** I giorni del mese che sul portale non risultano inseriti. */
export function mancantiDelMese(righe, anno, mese, fine) {
  const dentro = new Set(righe.filter((r) => r.caricato && r.giorno.startsWith(`${anno}-${String(mese).padStart(2, "0")}-`))
    .map((r) => Number(r.giorno.slice(8))));
  const out = [];
  for (let g = 1; g <= fine; g++) if (!dentro.has(g)) out.push(g);
  return out;
}
