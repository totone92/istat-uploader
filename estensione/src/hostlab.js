// Il ritiro del pacchetto da HostLab col gettone monouso (da_hostlab.py). Il server è
// scritto qui, non viene mai da fuori: nessuna pagina può far caricare uno zip di chi vuole.
// Il pacchetto resta in memoria, nella pagina dell'estensione, e non va da nessun'altra parte.

import { DIMENSIONE_MASSIMA_ZIP } from "./logica/sorgente.js";

export const SERVER = "https://hostlab.umbriaround.it";
const PERCORSO = "/turismatica/pacchetto";
const FORMA_GETTONE = /^\d{1,12}\.[A-Za-z0-9_-]{32,64}$/;

export const gettoneValido = (g) => typeof g === "string" && FORMA_GETTONE.test(g);

export class PacchettoNonDisponibile extends Error {}

export async function ritiraPacchetto(gettone) {
  if (!gettoneValido(gettone)) throw new PacchettoNonDisponibile("HostLab ha mandato un gettone non valido: premi di nuovo «Carica su Turismatica».");
  let r;
  try {
    r = await fetch(SERVER + PERCORSO, {
      method: "POST", credentials: "omit", cache: "no-store", referrerPolicy: "no-referrer",
      headers: { Authorization: `Bearer ${gettone}` },
    });
  } catch {
    throw new PacchettoNonDisponibile("Non riesco a parlare con HostLab: controlla la connessione, poi torna in "
      + "HostLab e premi di nuovo «Carica su Turismatica».");
  }
  if (!r.ok) {
    let testo = "";
    try {
      testo = String((await r.json()).errore ?? "");
    } catch {
      // risposta non in JSON: vale il messaggio generale.
    }
    throw new PacchettoNonDisponibile(testo || "HostLab non ha dato il pacchetto. Torna in HostLab e premi di nuovo «Carica su Turismatica».");
  }
  const byte = new Uint8Array(await r.arrayBuffer());
  if (byte.length > DIMENSIONE_MASSIMA_ZIP) throw new PacchettoNonDisponibile("Il pacchetto arrivato è troppo grande: mi fermo.");
  let struttura = r.headers.get("X-Struttura") ?? "";
  try {
    struttura = decodeURIComponent(struttura);
  } catch {
    struttura = "";
  }
  return { byte, struttura, mese: r.headers.get("X-Mese") ?? "" };
}
