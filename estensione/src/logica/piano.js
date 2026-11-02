// Lo stato dei giorni sul portale e il piano prima di caricare (piano.py).
// Il piano è una previsione: durante il giro ogni giorno si rilegge prima di toccarlo.

import { etichettaMese, fineMese, iso, parti } from "./periodo.js";

export const StatoGiorno = Object.freeze({
  CARICATO: "caricato",
  DA_FARE: "da_fare",
  NON_APERTO: "non_aperto",
});

export const chiaveMese = (anno, mese) => `${String(anno).padStart(4, "0")}-${String(mese).padStart(2, "0")}`;

/** Il 5 del mese dopo. */
export const scadenzaComunicazione = (anno, mese) => iso(mese === 12 ? anno + 1 : anno, mese % 12 + 1, 5);

function ultimoGiornoUtile(anno, mese, oggi) {
  const o = parti(oggi);
  if (anno < o.anno || (anno === o.anno && mese < o.mese)) return fineMese(anno, mese);
  if (anno > o.anno || (anno === o.anno && mese > o.mese)) return 0;
  return o.giorno - 1;
}

/** `righe`: [{giorno, caricato, pulsante}]. Un mese chiuso porta i giorni come sono. */
export function statoDalleRighe(righe, { anno, mese, chiuso = false, invioPossibile = null }) {
  const giorni = {};
  for (const r of righe) {
    const p = parti(r.giorno);
    if (p.anno !== anno || p.mese !== mese) continue;
    giorni[p.giorno] = r.caricato ? StatoGiorno.CARICATO : r.pulsante ? StatoGiorno.DA_FARE : StatoGiorno.NON_APERTO;
  }
  return { anno, mese, giorni, chiuso, invioPossibile };
}

const numeri = (ogg) => Object.keys(ogg).map(Number).sort((a, b) => a - b);

export const caricati = (stato) => numeri(stato.giorni).filter((g) => stato.giorni[g] === StatoGiorno.CARICATO);

/** I giorni passati che sul portale non ci sono. Un mese chiuso non ne ha. */
export function mancanti(stato, oggi) {
  if (stato.chiuso) return [];
  const ultimo = ultimoGiornoUtile(stato.anno, stato.mese, oggi);
  const out = [];
  for (let g = 1; g <= ultimo; g++) {
    const s = stato.giorni[g];
    if (s === StatoGiorno.DA_FARE || s === StatoGiorno.NON_APERTO) out.push(g);
  }
  return out;
}

/** «12 e 19» · «3, 4 e 9» · oltre `massimo`: «dal 3 al 28 (14 giorni)». */
export function elencoGiorni(giorni, massimo = 6) {
  if (!giorni.length) return "";
  if (giorni.length > massimo) return `dal ${giorni[0]} al ${giorni.at(-1)} (${giorni.length} giorni)`;
  if (giorni.length === 1) return String(giorni[0]);
  return `${giorni.slice(0, -1).join(", ")} e ${giorni.at(-1)}`;
}

const contaGiorni = (n) => (n === 1 ? "1 giorno" : `${n} giorni`);

export function testoVoce(v) {
  const mese = etichettaMese(v.anno, v.mese);
  const Mese = mese[0].toUpperCase() + mese.slice(1);
  if (v.chiuso) {
    return `${Mese}, ${v.nome}: il mese è già chiuso sul portale (comunicazione `
      + "mensile fatta). Non si carica più niente.";
  }
  if (v.presenti === null) {
    return `${Mese}, ${v.nome}: ${contaGiorni(v.daCaricare.length)} nei file. `
      + "Lo stato sul portale non l'ho ancora letto: lo controllo giorno "
      + "per giorno durante il giro, e salto quelli già presenti.";
  }
  const pezzi = [`${contaGiorni(v.presenti.length)} già presenti`];
  if (v.daCaricare.length) pezzi.push(`${v.daCaricare.length} da caricare (${elencoGiorni(v.daCaricare)})`);
  else pezzi.push("niente da caricare");
  let testo = `${Mese}, ${v.nome}: ${pezzi.join(", ")}.`;
  if (v.senzaFile.length) {
    testo += ` Sul portale mancano anche ${elencoGiorni(v.senzaFile)}, ma nello zip non c'è il file.`;
  }
  return testo;
}

/** I giorni da percorrere sul portale, dal primo all'ultimo da caricare. */
export function periodoVoce(v) {
  if (!v.daCaricare.length) return null;
  return { dal: iso(v.anno, v.mese, v.daCaricare[0]), al: iso(v.anno, v.mese, v.daCaricare.at(-1)) };
}

/** `abbinati`: [{id, nome, giorni}]; `stati`: id → chiave AAAA-MM → stato letto. */
export function costruisci(abbinati, stati, oggi) {
  const voci = [];
  for (const { id, nome, giorni } of abbinati) {
    const perMese = new Map();
    for (const g of giorni) {
      const p = parti(g);
      const k = chiaveMese(p.anno, p.mese);
      if (!perMese.has(k)) perMese.set(k, { anno: p.anno, mese: p.mese, conFile: [] });
      perMese.get(k).conFile.push(p.giorno);
    }
    for (const k of [...perMese.keys()].sort()) {
      const { anno, mese, conFile } = perMese.get(k);
      conFile.sort((a, b) => a - b);
      const ultimo = ultimoGiornoUtile(anno, mese, oggi);
      const utili = conFile.filter((g) => g <= ultimo);
      const futuri = conFile.filter((g) => g > ultimo);
      const stato = stati[id]?.[k];
      const fine = fineMese(anno, mese);
      const o = parti(oggi);
      const concluso = anno < o.anno || (anno === o.anno && mese < o.mese);
      const neiTermini = concluso && oggi <= scadenzaComunicazione(anno, mese);
      const tutti = (presenti) => {
        for (let g = 1; g <= fine; g++) if (!presenti.has(g)) return false;
        return true;
      };
      const base = { id, nome, anno, mese, conFile, futuri };
      if (stato?.chiuso) {
        voci.push({ ...base, presenti: caricati(stato), daCaricare: [], senzaFile: [], chiuso: true, comunicabile: false });
        continue;
      }
      if (!stato || !Object.keys(stato.giorni).length) {
        voci.push({
          ...base, presenti: null, daCaricare: utili, senzaFile: [], chiuso: false,
          comunicabile: neiTermini && tutti(new Set(conFile)),
        });
        continue;
      }
      const presenti = caricati(stato);
      const giaDentro = new Set(presenti);
      const daCaricare = utili.filter((g) => !giaDentro.has(g));
      const coiFile = new Set(conFile);
      voci.push({
        ...base, presenti, daCaricare, chiuso: false,
        senzaFile: mancanti(stato, oggi).filter((g) => !coiFile.has(g)),
        comunicabile: neiTermini && tutti(new Set([...presenti, ...daCaricare])),
      });
    }
  }
  return voci;
}
