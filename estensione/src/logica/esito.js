// Cos'è successo, detto a un albergatore (esito.py). Il riepilogo dice cosa manca
// ancora da fare. «Non riuscito» non si fonde mai con «già caricato»: sono la
// stessa riga non toccata con significati opposti.

import { ddmm, ddmmaaaa } from "./periodo.js";

export const Esito = Object.freeze({
  CARICATO: "caricato",
  GIA_CARICATO: "gia_caricato",
  FILE_MANCANTE: "file_mancante",
  NON_RIUSCITO: "non_riuscito",
  DA_CARICARE: "da_caricare",
});

export function nuovoEsito(etichetta, id) {
  return {
    etichetta, id, giorni: {}, saltata: null, nonRiconosciuti: [], file: {}, motivi: {},
    fermata: "", statoNonRiletto: "", comunicazione: "", comunicazioneRiuscita: false,
  };
}

export function segna(e, giorno, esito, file = null) {
  e.giorni[giorno] = esito;
  if (file !== null) e.file[giorno] = file;
}

export const elenco = (e, esito) => Object.keys(e.giorni).filter((g) => e.giorni[g] === esito).sort();

export const quanti = (e, esito) => elenco(e, esito).length;

function giorni(date, massimo = 8) {
  if (date.length > massimo) return `${date.length} giorni (dal ${ddmm(date[0])} al ${ddmm(date.at(-1))})`;
  return date.map(ddmm).join(", ");
}

/** `prova` è obbligatorio: un riepilogo di prova letto come uno vero farebbe
 *  credere caricato un mese che non lo è. */
export function riepilogo(esiti, periodo, { prova }) {
  if (typeof prova !== "boolean") throw new TypeError("prova va detto");
  if (!esiti.length) return "Non c'era niente da caricare.";
  const righe = [];
  if (prova) {
    righe.push("MODALITÀ PROVA — NON HO CARICATO NIENTE.",
      "Ecco cosa avrei caricato. Il portale è rimasto com'era.", "");
  }
  righe.push(`Periodo: ${periodo}`, "");
  const daFare = [];
  for (const e of esiti) {
    if (e.saltata) {
      righe.push(`■ ${e.etichetta} — non fatta: ${e.saltata}`, "");
      daFare.push(`${e.etichetta}: ${e.saltata}`);
      continue;
    }
    const fatti = quanti(e, Esito.CARICATO);
    const gia = quanti(e, Esito.GIA_CARICATO);
    const pronti = quanti(e, Esito.DA_CARICARE);
    const pezzi = [];
    if (fatti) pezzi.push(`${fatti} ${fatti === 1 ? "giorno caricato" : "giorni caricati"}`);
    if (pronti) pezzi.push(`${pronti} ${pronti === 1 ? "giorno" : "giorni"} da caricare`);
    if (gia) pezzi.push(`${gia} già c'erano`);
    righe.push(`■ ${e.etichetta} — ${pezzi.length ? pezzi.join(", ") : "niente da fare"}`);
    if (prova) {
      for (const g of elenco(e, Esito.DA_CARICARE)) righe.push(`   · ${ddmmaaaa(g)}  ←  ${e.file[g] ?? "?"}`);
    }
    const mancanti = elenco(e, Esito.FILE_MANCANTE);
    if (mancanti.length) {
      righe.push(e.fermata ? `   · ${e.fermata}` : `   · manca il file di: ${giorni(mancanti)}`);
      daFare.push(`${e.etichetta}: riscarica dal tuo gestionale i giorni mancanti (${giorni(mancanti)}) e rilancia.`);
    }
    const falliti = elenco(e, Esito.NON_RIUSCITO);
    if (falliti.length) {
      righe.push(`   · NON caricati: ${giorni(falliti)}`);
      const perMotivo = new Map();
      for (const g of falliti) {
        if (e.motivi[g]) perMotivo.set(e.motivi[g], [...(perMotivo.get(e.motivi[g]) ?? []), g]);
      }
      for (const [m, gg] of perMotivo) righe.push(`     ${giorni(gg)}: ${m}`);
      daFare.push(`${e.etichetta}: riprova per ${giorni(falliti)}. Se non passa nemmeno al secondo giro, caricali a mano dal portale.`);
    }
    if (e.statoNonRiletto) {
      righe.push(`   · ${e.statoNonRiletto}`);
      daFare.push(`${e.etichetta}: ${e.statoNonRiletto}`);
    }
    if (e.comunicazione) {
      righe.push(`   · ${e.comunicazione}`);
      if (!e.comunicazioneRiuscita) daFare.push(`${e.etichetta}: ${e.comunicazione}`);
    }
    if (e.nonRiconosciuti.length) {
      righe.push(`   · ${e.nonRiconosciuti.length} file nella cartella non sono movimenti giornalieri (li ho ignorati)`);
    }
    righe.push("");
  }
  if (prova) {
    righe.push("Se l'elenco è giusto: passa alla MODALITÀ VERA e rilancia. I giorni che già c'erano li salto anche lì.");
    if (daFare.length) righe.push("");
  }
  if (!daFare.length) {
    if (!prova) righe.push("Tutto a posto: non resta niente da fare.");
  } else {
    righe.push("DA FARE:");
    daFare.forEach((r, i) => righe.push(`  ${i + 1}. ${r}`));
  }
  return righe.join("\n").trim();
}
