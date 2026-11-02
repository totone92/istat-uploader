// Il ritiro del pacchetto da HostLab col gettone monouso (da_hostlab.py). Il server è
// l'indirizzo del tenant che ha premuto il tasto, garantito dal browser, e deve stare su
// umbriaround.it: nessun'altra pagina può far caricare uno zip di chi vuole.
// Il pacchetto resta in memoria, nella pagina dell'estensione, e non va da nessun'altra parte.

import { DIMENSIONE_MASSIMA_ZIP } from "./logica/sorgente.js";

const FORMA_SERVER = /^https:\/\/(?:[a-z0-9-]+\.)+umbriaround\.it$/;
const PERCORSO = "/turismatica/pacchetto";
const FORMA_GETTONE = /^\d{1,12}\.[A-Za-z0-9_-]{32,64}$/;

export const gettoneValido = (g) => typeof g === "string" && FORMA_GETTONE.test(g);

export const serverValido = (s) => typeof s === "string" && FORMA_SERVER.test(s);

export class PacchettoNonDisponibile extends Error {}

export async function ritiraPacchetto(gettone, server) {
  if (!gettoneValido(gettone) || !serverValido(server)) throw new PacchettoNonDisponibile("HostLab ha mandato un gettone non valido: premi di nuovo «Carica su Turismatica».");
  let r;
  try {
    r = await fetch(server + PERCORSO, {
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
