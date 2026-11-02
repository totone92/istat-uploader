// Le pagine del portale lette dal loro HTML — logica pura, stesse regole di
// pagina_movimenti.py e riconoscimento.py, che restano la fonte: un test le
// confronta sulle stesse copie. Prende un Document (DOMParser): gli script della
// pagina non girano qui, e niente del portale entra nella pagina dell'estensione.

import { iso, valida, MESI } from "./periodo.js";

export const SCHEDA_APERTO = "movimento periodo aperto";
export const SCHEDA_CHIUSO = "movimento periodo chiuso";
const INVIO_MENSILE = "invia comunicazione telematica mensile";
const ETICHETTA_REFLOW = "ui-column-title";
const DATA = /^\s*(\d{2})\/(\d{2})\/(\d{4})\s*$/;
const FORMA = ["presenze notte precedente", "arrivi", "partenze", "presenze", "unità occupate"];

export const documento = (html) => new DOMParser().parseFromString(html, "text/html");

const spazi = (t) => t.split(/\s+/).filter(Boolean).join(" ");

/** Il testo del nodo, spazi normalizzati, senza script/style. */
export function testo(n, senzaClasse = "") {
  const pezzi = [];
  const visita = (x) => {
    for (const f of x.childNodes) {
      if (f.nodeType === 3) pezzi.push(f.data);
      else if (f.nodeType === 1) {
        const tag = f.localName;
        if (tag === "script" || tag === "style") continue;
        if (senzaClasse && f.classList.contains(senzaClasse)) continue;
        visita(f);
      }
    }
  };
  visita(n);
  return spazi(pezzi.join(" "));
}

/** Il movimento c'è già? Il pulsante NON lo dice: resta anche dopo, per sostituire. */
export function giornoGiaCaricato(celle, classi, titoli = []) {
  const testi = [...celle, ...titoli];
  if (testi.some((t) => t.toLowerCase().includes("file caricato"))) return true;
  if (classi.some((c) => c.includes("fa-file"))) return true;
  const daFare = classi.some((c) => c.includes("fa-angle-double-down"));
  const valori = celle.slice(3, 7).map((c) => c.trim());
  return valori.length === 4 && valori.every((v) => /^\d+$/.test(v)) && !daFare;
}

const attivo = (n) => !n.hasAttribute("disabled") && !n.classList.contains("ui-state-disabled");

function colonne(tabella) {
  const out = {};
  if (!tabella) return out;
  for (const riga of tabella.querySelectorAll("tr")) {
    const celle = [...riga.children].filter((c) => c.localName === "th" || c.localName === "td");
    if (!celle.length || !celle.every((c) => c.localName === "th")) continue;
    celle.forEach((c, i) => {
      const nome = (c.getAttribute("aria-label") || testo(c)).trim().toLowerCase();
      if (nome && !(nome in out)) out[nome] = i;
    });
    return out;
  }
  return out;
}

function riga(tr, cols) {
  const celle = [...tr.children].filter((c) => c.localName === "td");
  const testi = celle.map((c) => testo(c, ETICHETTA_REFLOW));
  let posData = cols.data;
  if (posData === undefined || posData >= testi.length || !DATA.test(testi[posData])) {
    posData = testi.findIndex((t) => DATA.test(t));
  }
  if (posData < 0 || posData === undefined) return null;
  const m = DATA.exec(testi[posData]);
  if (!valida(+m[3], +m[2], +m[1])) return null;
  const dataTesto = `${m[1]}/${m[2]}/${m[3]}`;
  const forma = FORMA.every((k) => k in cols)
    ? ["", dataTesto, ...FORMA.map((k) => (cols[k] < testi.length ? testi[cols[k]] : ""))]
    : ["", dataTesto, ...testi.slice(posData + 1, posData + 6), "", "", "", "", ""].slice(0, 7);
  const discendenti = [...tr.querySelectorAll("*")];
  const classi = discendenti.map((d) => d.getAttribute("class") || "").filter((c) => c.includes("fa-"));
  const titoli = discendenti.map((d) => d.getAttribute("title")).filter(Boolean);
  const carica = discendenti.find((d) => d.localName === "button"
    && [...d.querySelectorAll("*")].some((x) => (x.getAttribute("class") || "").includes("fa-upload")));
  return {
    giorno: iso(+m[3], +m[2], +m[1]),
    celle: forma, classi, titoli,
    idCarica: carica ? carica.id : "",
    caricato: giornoGiaCaricato(forma, classi, titoli),
  };
}

function righe(pannello) {
  for (const corpo of pannello.querySelectorAll("tbody")) {
    const cols = colonne(corpo.closest("table"));
    const out = [...corpo.children].filter((t) => t.localName === "tr").map((t) => riga(t, cols)).filter(Boolean);
    if (out.length) return out;
  }
  return [];
}

function bottoneMese(pannello, verso) {
  const icona = verso === "indietro" ? "fa-arrow-left" : "fa-arrow-right";
  const trovati = [...pannello.querySelectorAll("button.monthButtonText, button.monthButtonNoText")]
    .filter((b) => b.querySelector(`[class*="${icona}"]`));
  if (!trovati.length) return null;
  // Il bottone col testo prima: l'altro è il gemello per schermi stretti.
  trovati.sort((a, b) => a.classList.contains("monthButtonText") === b.classList.contains("monthButtonText")
    ? 0 : a.classList.contains("monthButtonText") ? -1 : 1);
  const scelto = trovati.find(attivo) ?? trovati[0];
  return { id: scelto.id, attivo: attivo(scelto) };
}

function titoloMese(pannello) {
  for (const n of pannello.querySelectorAll(".ui-panel-content")) {
    const m = /^\s*([A-Za-z]+)\s+(\d{4})\s*$/.exec(testo(n));
    if (m && MESI.includes(m[1].toLowerCase())) return iso(+m[2], MESI.indexOf(m[1].toLowerCase()) + 1, 1);
  }
  return null;
}

function invio(pannello) {
  const b = [...pannello.querySelectorAll("button")].find((x) => testo(x).toLowerCase().includes(INVIO_MENSILE));
  return b ? { id: b.id, attivo: attivo(b) } : null;
}

/** La pagina dei movimenti: struttura, schede, righe, frecce, invio mensile. */
export function leggiPagina(doc, html) {
  let scheda = "";
  const schede = {};
  for (const li of doc.querySelectorAll("li.ui-tabs-header")) {
    const t = testo(li).toLowerCase();
    const n = Number.parseInt(li.getAttribute("data-index") ?? "", 10);
    if (!Number.isInteger(n)) continue;
    schede[t] = n;
    if (li.getAttribute("aria-selected") === "true" || li.classList.contains("ui-state-active")) scheda = t;
  }
  const pannello = doc.querySelector('.ui-tabs-panel[aria-hidden="false"]') ?? doc;
  const r = righe(pannello);
  const titolo = titoloMese(pannello);
  return {
    struttura: intestazione(doc, html),
    scheda, schede,
    righe: r,
    indietro: bottoneMese(pannello, "indietro"),
    avanti: bottoneMese(pannello, "avanti"),
    invioMensile: invio(pannello),
    titoloMese: titolo,
    mese: r.length ? `${r[0].giorno.slice(0, 7)}-01` : titolo,
  };
}

export const rigaDel = (p, giorno) => p.righe.find((r) => r.giorno === giorno) ?? null;

/** Da che parte andare: indietro, avanti, o null (ci siamo, o non si sa). */
export function verso(mostrato, voluto) {
  if (mostrato === null || mostrato.slice(0, 7) === voluto.slice(0, 7)) return null;
  return voluto.slice(0, 7) < mostrato.slice(0, 7) ? "indietro" : "avanti";
}

/** Il mese che il dialogo di conferma dice di comunicare. */
export function meseNelDialogo(t) {
  const m = /per il mese\s+([A-Za-z]+)\s+(\d{4})/i.exec(t);
  if (!m || !MESI.includes(m[1].toLowerCase())) return null;
  return iso(+m[2], MESI.indexOf(m[1].toLowerCase()) + 1, 1);
}

const ID_STRUTTURA = /idStruttura['"]?\s*(?:,\s*value\s*)?[=:,]\s*['"]?(\d{2,9})/gi;
const ETICHETTA_CIR = /\bCIR\b|identificativo regionale/i;
const ETICHETTA_CIN = /\bCIN\b|identificativo nazionale/i;
const CODICE = /^[A-Z0-9]{8,20}$/;
const ID_DELLA_PAGINA = /dettagliostruttura\.xhtml\?idStruttura=(\d{2,9})|par_STRU%3D(\d{2,9})|movimentoospiti\.xhtml\?idStruttura=(\d{2,9})/g;

function idDellaPagina(html) {
  const trovati = new Set([...html.matchAll(ID_DELLA_PAGINA)].map((m) => m[1] || m[2] || m[3]));
  return trovati.size === 1 ? [...trovati][0] : "";
}

/** La struttura aperta nella pagina dei movimenti, o null. */
export function intestazione(doc, html) {
  const blocco = doc.querySelector(".nomestruttura");
  if (!blocco) return null;
  const s = { id: "", nome: "", comune: "", tipologia: "", stato: "", cir: "", cin: "" };
  const resto = [];
  let attesa = "";
  for (const l of blocco.querySelectorAll("label")) {
    const t = testo(l);
    if (!t) continue;
    if (attesa) {
      const c = t.replaceAll(" ", "").toUpperCase();
      if (CODICE.test(c)) s[attesa] = c;
      attesa = "";
    } else if (ETICHETTA_CIN.test(t)) attesa = "cin";
    else if (ETICHETTA_CIR.test(t)) attesa = "cir";
    else if (/^comune\s*:/i.test(t)) s.comune = t.slice(t.indexOf(":") + 1).trim();
    else if (t.startsWith("(") && t.endsWith(")")) s.tipologia = t.slice(1, -1).split(" - ")[0].trim();
    else resto.push(t);
  }
  s.nome = resto.find((t) => t.toLowerCase() !== "movimento ospiti") ?? "";
  const stato = doc.querySelector(".stato");
  if (stato) {
    const classi = [...stato.classList];
    s.stato = (testo(stato) || classi.at(-1)).trim().toUpperCase();
  }
  s.id = idDellaPagina(html);
  return s;
}

function selectDiStrutture(sel) {
  if (`${sel.id} ${sel.getAttribute("name") ?? ""}`.toLowerCase().includes("strutt")) return true;
  if (!sel.id.endsWith("_input")) return false;
  const modulo = sel.closest("form") ?? sel.closest("body");
  if (!modulo) return false;
  return [...modulo.querySelectorAll("h1,h2,h3")].some((d) => testo(d).toLowerCase().includes("struttur"));
}

const togliId = (t, id) => t.replace(new RegExp(`^\\s*\\(?${id}\\)?\\s*[-–:|]?\\s*|\\s*[-–(]?\\s*${id}\\)?\\s*$`, "g"), "").trim();

/** Le strutture che la pagina mostra: la tendina di prehome, o la pagina di una sola. */
export function strutture(doc, html) {
  const trovate = new Map();
  const tieni = (s) => {
    const v = trovate.get(s.id);
    if (!v || (!v.nome && s.nome)) trovate.set(s.id, s);
  };
  for (const n of doc.querySelectorAll("*")) {
    if (n.localName === "select" && selectDiStrutture(n)) {
      for (const o of n.querySelectorAll("option")) {
        const v = (o.getAttribute("value") ?? "").trim();
        if (/^\d+$/.test(v) && Number(v) > 0) tieni({ id: v, nome: togliId(testo(o), v) });
      }
      continue;
    }
    for (const a of n.attributes) {
      for (const m of a.value.matchAll(ID_STRUTTURA)) {
        const pr = testo(n);
        tieni({ id: m[1], nome: pr && !/^\d+$/.test(pr) ? togliId(pr.slice(0, 120), m[1]) : "" });
      }
    }
  }
  const t = intestazione(doc, html);
  if (t?.id) trovate.set(t.id, t);
  return [...trovate.values()].sort((a, b) => {
    const x = a.nome.toLowerCase();
    const y = b.nome.toLowerCase();
    return x < y ? -1 : x > y ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
}

// ─── la copia senza dati personali ───────────────────────────────────────────

const CF = /\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b/gi;
const EMAIL = /[\w.+-]+@[\w-]+(\.[\w-]+)+/g;
const TELEFONO = /(?<![\w/=])\+?\d[\d .-]{7,}\d(?![\w])/g;
const TOKEN = /(?=[A-Za-z0-9+/_=-]*\d)(?=[A-Za-z0-9+/_=-]*[A-Za-z])[A-Za-z0-9+/_=-]{32,}/g;
const SESSIONE = /;jsessionid=[^?#"'\s]*/gi;
const RISERVATI = /([?&](?:token|code|state|samlresponse|relaystate|sessionid|jsessionid|ticket)=)[^&#"'\s]*/gi;
const CLASSI_PERSONA = /utente|user|nominativ|profil|account|benvenut|anagrafic|titolare|gestore|referente|legale|operatore|login-name|username/;
const COLONNE_PERSONA = /titolare|gestore|referente|responsabil|legale|proprietar|cognome|nominativ|codice fiscale|e-?mail|pec|telefon|cellulare|nato|nascita/i;
const BENVENUTO = /(benvenut[oa]|ciao|salve)\s*,?\s*[^<\n]{0,60}/gi;
const RIMOSSO = "[RIMOSSO]";

function ripulisciTesto(t) {
  return t.replace(CF, "[CODICE FISCALE RIMOSSO]")
    .replace(EMAIL, "[EMAIL RIMOSSA]")
    .replace(TELEFONO, (m) => ([...m].filter((c) => /\d/.test(c)).length >= 9 ? "[TELEFONO RIMOSSO]" : m))
    // Il nome di un file ISTAT è lungo come un token, ma dichiara una data: resta.
    .replace(TOKEN, (m, dove, tutto) => (tutto.startsWith(".txt", dove + m.length) ? m : "[TOKEN RIMOSSO]"))
    .replace(BENVENUTO, (_m, g) => `${g} ${RIMOSSO}`);
}

/** Una riga del registro o un titolo: senza codici fiscali, email, telefoni, token. */
export const ripulisciRiga = ripulisciTesto;

/** Un indirizzo per il registro: senza sessione, token, parametri riservati. */
export function ripulisciIndirizzo(url) {
  const u = url.replace(SESSIONE, "").replace(RISERVATI, `$1${RIMOSSO}`).replace(CF, "[CODICE FISCALE RIMOSSO]");
  return u.replace(/[^/?&=;#:]+/g, (m) => (new RegExp(`^(?:${TOKEN.source})$`).test(m) ? "[TOKEN RIMOSSO]" : m));
}

/** La pagina senza dati personali, per chi sistema la lettura: la forma resta. */
export function ripulisci(html) {
  const doc = documento(html);
  for (const n of doc.querySelectorAll("*")) {
    for (const a of [...n.attributes]) {
      let v = a.value.replace(SESSIONE, "").replace(RISERVATI, `$1${RIMOSSO}`);
      if (["value", "title", "alt", "placeholder", "aria-label", "content"].includes(a.name) || a.name.startsWith("data-")) {
        v = ripulisciTesto(v);
      }
      v = v.replace(CF, "[CODICE FISCALE RIMOSSO]");
      if (!["class", "id", "name", "for", "style", "role", "type"].includes(a.name)) v = v.replace(TOKEN, "[TOKEN RIMOSSO]");
      a.value = v;
    }
    const tag = n.localName;
    if (tag === "input" || tag === "textarea") {
      if (n.hasAttribute("value")) n.setAttribute("value", RIMOSSO);
      if (tag === "textarea") n.textContent = RIMOSSO;
    } else if (tag === "script" || tag === "noscript") {
      if (n.textContent) n.textContent = "/* contenuto rimosso */";
    } else if (!["html", "body", "form"].includes(tag)
      && CLASSI_PERSONA.test(`${n.getAttribute("class") ?? ""} ${n.id}`.toLowerCase())) {
      n.textContent = RIMOSSO;
    }
  }
  for (const tabella of doc.querySelectorAll("table")) {
    let personali = [];
    for (const tr of tabella.querySelectorAll("tr")) {
      const celle = [...tr.children];
      if (celle.length && celle.every((c) => c.localName === "th")) {
        personali = celle.map((c, i) => (COLONNE_PERSONA.test(testo(c)) ? i : -1)).filter((i) => i >= 0);
        break;
      }
    }
    if (!personali.length) continue;
    for (const tr of tabella.querySelectorAll("tr")) {
      [...tr.children].forEach((c, i) => {
        if (personali.includes(i) && c.localName === "td") c.textContent = RIMOSSO;
      });
    }
  }
  const camminatore = doc.createTreeWalker(doc.documentElement, NodeFilter.SHOW_TEXT);
  while (camminatore.nextNode()) camminatore.currentNode.data = ripulisciTesto(camminatore.currentNode.data);
  return `<!-- copia ripulita da Istat Uploader: senza dati personali -->\n${doc.documentElement.outerHTML}`;
}
