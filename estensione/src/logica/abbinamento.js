// Quali file vanno a quale struttura: da soli quando è certo, chiedendo quando
// non lo è. Stesse regole di abbinamento.py, nello stesso ordine: zip di prova
// mai da solo; scelta già confermata; CIN solo se la regola regge su tutte; nome
// uguale a una sola struttura; il resto si chiede. Non si indovina mai.

import { dataDalNome, STRUTTURA_DI_PROVA } from "./sorgente.js";

const ID_NEL_NOME = /^schedine_istat_(.+)_\d{8}\.txt$/i;
const PAROLE_VUOTE = new Set([
  "SRL", "SAS", "SNC", "SPA", "DI", "DEL", "DELLA", "LA", "IL", "LE", "LO",
  "B", "BB", "BNB", "E", "AND", "THE",
]);

export function normalizza(nome) {
  const senzaAccenti = nome.normalize("NFKD").replace(/\p{M}/gu, "");
  return senzaAccenti.replace(/[^A-Za-z0-9]+/g, " ").toUpperCase().trim().split(/\s+/).filter(Boolean).join(" ");
}

const parole = (nome) => new Set(normalizza(nome).split(" ").filter((p) => p && !PAROLE_VUOTE.has(p)));

/** Serve solo a ordinare le proposte: non abbina mai niente da sola. */
export function somiglianza(a, b) {
  const pa = parole(a);
  const pb = parole(b);
  if (!pa.size || !pb.size) return 0;
  const comuni = [...pa].filter((p) => pb.has(p)).length;
  return comuni / (pa.size + pb.size - comuni);
}

/** Il nome della struttura nella prima riga del file ('' se illeggibile). */
export function intestazioneFile(byte) {
  const inizio = byte.subarray(0, 300);
  let fine = inizio.indexOf(10);
  if (fine < 0) fine = inizio.length;
  if (fine > 0 && inizio[fine - 1] === 13) fine -= 1;
  const riga = inizio.subarray(0, fine);
  for (const codifica of ["utf-8", "windows-1252"]) {
    try {
      return new TextDecoder(codifica, { fatal: true }).decode(riga).trim();
    } catch {
      // la prossima
    }
  }
  return "";
}

export function idDalNome(nomeFile) {
  const m = ID_NEL_NOME.exec(nomeFile.trim());
  return m ? m[1] : null;
}

export const chiaveGruppo = (g) => `${normalizza(g.nomeNelFile)}|${g.idNelNome ?? ""}`;

export function chiaviAlias(g) {
  const out = [];
  if (g.idNelNome) out.push(`id:${g.idNelNome}`);
  if (g.nomeNelFile) out.push(`nome:${normalizza(g.nomeNelFile)}`);
  return out;
}

/** Divide i file per (nome nella prima riga, id nel nome). */
export function raggruppa(file, { marcatoreProva }) {
  const gruppi = new Map();
  for (const f of file) {
    const giorno = dataDalNome(f.nome);
    if (giorno === null) continue;
    const nome = intestazioneFile(f.byte);
    const ident = idDalNome(f.nome);
    const k = `${normalizza(nome)}\u0000${ident ?? ""}`;
    if (!gruppi.has(k)) gruppi.set(k, { nomeNelFile: nome, idNelNome: ident, perGiorno: new Map(), diProva: false });
    const g = gruppi.get(k);
    if (!g.perGiorno.has(giorno)) g.perGiorno.set(giorno, f);
    if (nome.startsWith(STRUTTURA_DI_PROVA)) g.diProva = true;
  }
  const tutti = [...gruppi.values()];
  for (const g of tutti) g.diProva = g.diProva || marcatoreProva;
  const ordine = (g) => `${g.nomeNelFile}\u0000${g.idNelNome ?? ""}`;
  return tutti.sort((a, b) => (ordine(a) < ordine(b) ? -1 : ordine(a) > ordine(b) ? 1 : 0));
}

export const giorniDelGruppo = (g) => [...g.perGiorno.keys()].sort();

const codice = (t) => t.toUpperCase().replace(/[^A-Z0-9]/g, "");

/** Il CIN di OGNI struttura finisce con il suo numero Turismatica? Una regola vista
 *  su un campione si usa solo se la lettura la conferma su tutte. */
export function cinAffidabile(strutture) {
  if (!strutture.length) return false;
  return strutture.every((s) => {
    const cin = codice(s.cin || "");
    return s.id.length <= 6 && /^\d+$/.test(s.id) && cin.length >= 6 && cin.slice(-6) === s.id.padStart(6, "0");
  });
}

/** `strutture`: [{id, nome, cin}] · `alias`: chiave → numero Turismatica. */
export function abbina(gruppi, strutture, alias) {
  const ids = new Set(strutture.map((s) => s.id));
  const perCin = new Map(cinAffidabile(strutture) ? strutture.map((s) => [codice(s.cin), s.id]) : []);
  const risultato = gruppi.map((g) => {
    // sort di JS è stabile come quello di Python: a parità resta l'ordine del portale.
    const proposte = [...strutture]
      .map((s) => [s.id, somiglianza(g.nomeNelFile, s.nome)])
      .sort((a, b) => b[1] - a[1])
      .map(([id]) => id);
    if (g.diProva) {
      return {
        gruppo: g, id: null, motivo: "prova", proposte,
        domanda: "Sono i file inventati dello zip di prova: non sono di nessuna "
          + "tua struttura. Puoi abbinarli a una delle tue solo per vedere "
          + "il giro in modalità prova.",
      };
    }
    const ricordato = chiaviAlias(g).map((k) => alias[k]).find((v) => ids.has(v));
    if (ricordato !== undefined) return { gruppo: g, id: ricordato, motivo: "ricordato", proposte: [], domanda: "" };
    const dalCin = perCin.get(codice(g.idNelNome ?? ""));
    if (dalCin !== undefined) return { gruppo: g, id: dalCin, motivo: "cin", proposte: [], domanda: "" };
    const uguali = strutture.filter((s) => normalizza(s.nome) === normalizza(g.nomeNelFile));
    if (uguali.length === 1 && normalizza(g.nomeNelFile)) {
      return { gruppo: g, id: uguali[0].id, motivo: "nome", proposte: [], domanda: "" };
    }
    return {
      gruppo: g, id: null, motivo: "da_chiedere", proposte,
      domanda: `Nei file c'è scritto «${g.nomeNelFile || "nessun nome"}»`
        + (g.idNelNome ? ` (codice ${g.idNelNome})` : "")
        + ": a quale delle tue strutture appartengono?",
    };
  });
  // Due gruppi sulla stessa struttura: un automatismo caricherebbe un mese sopra l'altro.
  const contati = new Map();
  for (const a of risultato) if (a.id !== null) contati.set(a.id, (contati.get(a.id) ?? 0) + 1);
  for (const a of risultato) {
    if (a.id !== null && contati.get(a.id) > 1) {
      a.proposte = [a.id, ...strutture.map((s) => s.id).filter((i) => i !== a.id)];
      a.id = null;
      a.motivo = "da_chiedere";
      a.domanda = "Più gruppi di file sembrano della stessa struttura: dimmi tu "
        + `a quale va «${a.gruppo.nomeNelFile || "questo gruppo"}».`;
    }
  }
  return risultato;
}
