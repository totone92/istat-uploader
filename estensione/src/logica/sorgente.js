// Lo zip dei .txt, letto in memoria: niente su disco, niente fuori dal browser.
//
// La data si legge dal NOME del file, come nell'uploader (sorgente.py): due
// convenzioni ambigue fra loro, e decide il prefisso, non la plausibilità.

import { iso, valida } from "./periodo.js";

const HOSTLAB = /^schedine_istat_.*_(\d{8})\.txt$/i;
const OTTO_CIFRE = /^(\d{8})\.txt$/i;

export const MARCATORE_PROVA = "PROVA.txt";
export const STRUTTURA_DI_PROVA = "STRUTTURA DI PROVA";
export const MESSAGGIO_ZIP_DI_PROVA = "Questo è lo zip di prova: serve solo in modalità prova.";

//: Un mese sono 31 file da pochi kB; otto strutture, un paio di centinaia.
export const DIMENSIONE_MASSIMA_ZIP = 5 * 1024 * 1024;
const DIMENSIONE_MASSIMA_FILE = 1024 * 1024;
const DIMENSIONE_MASSIMA_TOTALE = 64 * 1024 * 1024;
const VOCI_MASSIME = 5000;

export function dataDalNome(nome) {
  const pulito = nome.trim();
  let m = HOSTLAB.exec(pulito);
  if (m) {
    const c = m[1];
    return daCifre(+c.slice(0, 4), +c.slice(4, 6), +c.slice(6, 8));
  }
  m = OTTO_CIFRE.exec(pulito);
  if (m) {
    const c = m[1];
    return daCifre(+c.slice(4, 8), +c.slice(2, 4), +c.slice(0, 2));
  }
  return null;
}

const daCifre = (a, m, g) => (valida(a, m, g) ? iso(a, m, g) : null);

export class SorgenteNonValida extends Error {}

const nonSiApre = (nome) => new SorgenteNonValida(
  `«${nome}» non si apre: il file è danneggiato o non è uno zip.`);

async function sgonfia(compressi, massimo) {
  const flusso = new Blob([compressi]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  const pezzi = [];
  let totale = 0;
  for await (const pezzo of flusso) {
    totale += pezzo.length;
    // Si conta mentre si sgonfia: uno zip gonfiato ad arte si ferma qui.
    if (totale > massimo) throw new SorgenteNonValida("Un file dentro lo zip è troppo grande: mi fermo.");
    pezzi.push(pezzo);
  }
  const out = new Uint8Array(totale);
  let dove = 0;
  for (const p of pezzi) {
    out.set(p, dove);
    dove += p.length;
  }
  return out;
}

/** I .txt dello zip, a qualunque profondità: `[{nome, byte}]`. Del percorso resta
 *  solo il nome finale: Windows ricomprime dentro una cartella, e un «../» non vale. */
export async function leggiZip(byte, nomeZip = "lo zip") {
  if (byte.length > DIMENSIONE_MASSIMA_ZIP) {
    throw new SorgenteNonValida(`«${nomeZip}» è troppo grande per essere uno zip di file ISTAT.`);
  }
  const vista = new DataView(byte.buffer, byte.byteOffset, byte.byteLength);
  let fine = -1;
  for (let i = byte.length - 22; i >= 0 && i >= byte.length - 22 - 65535; i--) {
    if (vista.getUint32(i, true) === 0x06054b50) {
      fine = i;
      break;
    }
  }
  if (fine < 0) throw nonSiApre(nomeZip);
  const voci = vista.getUint16(fine + 10, true);
  if (voci > VOCI_MASSIME) throw new SorgenteNonValida(`«${nomeZip}» contiene troppi file.`);
  let dove = vista.getUint32(fine + 16, true);
  const testo = new TextDecoder();
  const visti = new Set();
  const out = [];
  let totale = 0;
  for (let n = 0; n < voci; n++) {
    if (dove + 46 > byte.length || vista.getUint32(dove, true) !== 0x02014b50) throw nonSiApre(nomeZip);
    const opzioni = vista.getUint16(dove + 8, true);
    const metodo = vista.getUint16(dove + 10, true);
    const compresso = vista.getUint32(dove + 20, true);
    const lungNome = vista.getUint16(dove + 28, true);
    const lungExtra = vista.getUint16(dove + 30, true);
    const lungCommento = vista.getUint16(dove + 32, true);
    const locale = vista.getUint32(dove + 42, true);
    const percorso = testo.decode(byte.subarray(dove + 46, dove + 46 + lungNome));
    dove += 46 + lungNome + lungExtra + lungCommento;
    const nome = percorso.split(/[\\/]/).pop();
    if (!nome || !nome.toLowerCase().endsWith(".txt") || visti.has(nome)) continue;
    if (opzioni & 1) throw new SorgenteNonValida(`«${nomeZip}» è protetto da password.`);
    if (locale + 30 > byte.length || vista.getUint32(locale, true) !== 0x04034b50) throw nonSiApre(nomeZip);
    const inizio = locale + 30 + vista.getUint16(locale + 26, true) + vista.getUint16(locale + 28, true);
    const dati = byte.subarray(inizio, inizio + compresso);
    let contenuto;
    if (metodo === 0) contenuto = dati.slice();
    else if (metodo === 8) {
      try {
        contenuto = await sgonfia(dati, DIMENSIONE_MASSIMA_FILE);
      } catch (e) {
        if (e instanceof SorgenteNonValida) throw e;
        throw nonSiApre(nomeZip);
      }
    } else throw nonSiApre(nomeZip);
    if (contenuto.length > DIMENSIONE_MASSIMA_FILE) {
      throw new SorgenteNonValida("Un file dentro lo zip è troppo grande: mi fermo.");
    }
    totale += contenuto.length;
    if (totale > DIMENSIONE_MASSIMA_TOTALE) {
      throw new SorgenteNonValida(`«${nomeZip}» si estrae in troppi dati: mi fermo.`);
    }
    visti.add(nome);
    out.push({ nome, byte: contenuto });
  }
  return out.sort((a, b) => (a.nome < b.nome ? -1 : a.nome > b.nome ? 1 : 0));
}

export const haMarcatore = (file) => file.some((f) => f.nome.toLowerCase() === MARCATORE_PROVA.toLowerCase());

/** I nomi che non dichiarano una data: «cartella sbagliata», da dire e non da tacere. */
export const nonRiconosciuti = (file) => file
  .filter((f) => f.nome.toLowerCase() !== MARCATORE_PROVA.toLowerCase() && dataDalNome(f.nome) === null)
  .map((f) => f.nome);
