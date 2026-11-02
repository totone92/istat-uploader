// La meccanica di Turismatica dentro la scheda del gestore: stessa sequenza di
// portale.py, costata prove sul campo. Non semplificarla senza riprovare dal vivo.
//
// Perché si guida la pagina e non si ripetono le richieste: il portale è JSF, con
// ViewState legato alla vista e una struttura scelta in sessione; ripetere le POST
// vorrebbe dire riscrivere PrimeFaces e rompersi al primo aggiornamento. Si guida
// da fuori, un passo alla volta: una navigazione non perde niente, perché lo stato
// sta nella pagina dell'estensione.
//
// Il login non si automatizza: qui non c'è una riga che provi a entrare.

import { Esito, nuovoEsito, segna } from "./logica/esito.js";
import { caricaGiorno, mancantiDelMese, primoBuco, statoUtilizzabile } from "./logica/giro.js";
import {
  documento, leggiPagina, meseNelDialogo, ripulisci, ripulisciIndirizzo, rigaDel, SCHEDA_APERTO,
  SCHEDA_CHIUSO, strutture, verso,
} from "./logica/lettura.js";
import * as messaggi from "./logica/messaggi.js";
import { ddmmaaaa, etichettaMese, fineMese, giorniFra, parti } from "./logica/periodo.js";
import { MESSAGGIO_ZIP_DI_PROVA } from "./logica/sorgente.js";
import { dormi } from "./tempo.js";

export const BASE = "https://turismatica.regione.umbria.it";
export const PREHOME_URL = `${BASE}/ntojsf/private/prehome.xhtml`;
const movimentiUrl = (id) => `${BASE}/ntojsf/private/OSR/movimento/movimentoospiti.xhtml?idStruttura=${id}`;

const DIALOG = "movimentiTabView:uploadFileDialog";
const CAMPO_FILE = "movimentiTabView:formUploadFile:fileUploadGiornoAperto_input";
const BOTTONE_CARICA = "#movimentiTabView\\:formUploadFile .ui-fileupload-upload:not([disabled])";
const ANNULLA_FILE = "#movimentiTabView\\:formUploadFile .ui-fileupload-cancel:not([disabled])";
const CHIUDI_DIALOG = "#movimentiTabView\\:uploadFileDialog .ui-dialog-titlebar-close";

//: Tre, e non uno: il click è intercettato da sovrapposizioni PrimeFaces.
const TENTATIVI_CARICA = 3;
const PAUSA_FRA_GIORNI = 500;
const ATTESA_PAGINA = 15000;
const ATTESA_TENDINA = 10000;
const ATTESA_SCHEDA = 10000;
const ATTESA_BOTTONE = 5000;
const ATTESA_CONFERMA = 15000;
const ATTESA_USCITA = 2000;
const ATTESA_ELENCO = 20000;
const ATTESA_DOM = 30000;
const MAX_PASSI_MESE = 13;

export class SchedaChiusa extends Error {}

// ─── la scheda ───────────────────────────────────────────────────────────────

const inBase64 = (byte) => {
  let s = "";
  for (let i = 0; i < byte.length; i += 8192) s += String.fromCharCode(...byte.subarray(i, i + 8192));
  return btoa(s);
};

class Scheda {
  constructor() { this.id = null; }

  async creaSeManca(indirizzo) {
    if (this.id !== null) {
      try {
        await chrome.tabs.get(this.id);
        return false;
      } catch {
        this.id = null;
      }
    }
    const io = await chrome.tabs.getCurrent();
    const t = await chrome.tabs.create({ url: indirizzo, active: true, ...(io ? { index: io.index + 1 } : {}) });
    this.id = t.id;
    return true;
  }

  async primoPiano() {
    if (this.id !== null) await chrome.tabs.update(this.id, { active: true }).catch(() => {});
  }

  /** Va all'indirizzo e aspetta che la pagina sia caricata. */
  async vai(indirizzo) {
    await new Promise((fatto, errore) => {
      let partita = false;
      const chiudi = () => {
        chrome.tabs.onUpdated.removeListener(ascolta);
        clearTimeout(scadenza);
      };
      const ascolta = (id, c) => {
        if (id !== this.id) return;
        if (c.status === "loading") partita = true;
        if (partita && c.status === "complete") {
          chiudi();
          fatto();
        }
      };
      const scadenza = setTimeout(() => {
        chiudi();
        fatto();
      }, ATTESA_DOM);
      chrome.tabs.onUpdated.addListener(ascolta);
      chrome.tabs.update(this.id, { url: indirizzo }).catch((e) => {
        chiudi();
        errore(new SchedaChiusa(e.message));
      });
    });
  }

  /** L'indirizzo, o '' fuori dai domini permessi (SPID, pagina d'errore). */
  async indirizzo() {
    try {
      const t = await chrome.tabs.get(this.id);
      return t.url ?? "";
    } catch (e) {
      throw new SchedaChiusa(e.message);
    }
  }

  /** Esegue nella pagina. `MAIN`: serve per parlare con PrimeFaces. */
  async esegui(func, args = [], world = "MAIN") {
    await this.indirizzo();
    const [r] = await chrome.scripting.executeScript({ target: { tabId: this.id }, world, func, args });
    return r?.result;
  }

  /** La pagina com'è adesso; '' se ora non si può leggere (cambio pagina, fuori dominio). */
  async html() {
    try {
      return await this.esegui(() => document.documentElement.outerHTML, [], "ISOLATED") ?? "";
    } catch (e) {
      if (e instanceof SchedaChiusa) throw e;
      return "";
    }
  }

  async testoVisibile() {
    try {
      return await this.esegui(() => (document.body ? document.body.innerText : ""), [], "ISOLATED") ?? "";
    } catch (e) {
      if (e instanceof SchedaChiusa) throw e;
      return "";
    }
  }

  async titolo() {
    try {
      return await this.esegui(() => document.title, [], "ISOLATED") ?? "";
    } catch (e) {
      if (e instanceof SchedaChiusa) throw e;
      return "";
    }
  }

  /** Aspetta che `func` nella pagina dia un valore vero. */
  async finche(func, args, massimo = ATTESA_DOM) {
    const fine = Date.now() + massimo;
    for (;;) {
      let v = null;
      try {
        v = await this.esegui(func, args);
      } catch (e) {
        if (e instanceof SchedaChiusa) throw e;
      }
      if (v) return v;
      if (Date.now() >= fine) return null;
      await dormi(200);
    }
  }
}

// funzioni che girano nella pagina: autonome, niente variabili di qui.
const VISIBILE = (id) => {
  const el = document.getElementById(id);
  if (!el) return false;
  const s = getComputedStyle(el);
  return el.getClientRects().length > 0 && s.visibility !== "hidden" && s.display !== "none";
};
const INVISIBILE = (id) => {
  const el = document.getElementById(id);
  if (!el) return true;
  const s = getComputedStyle(el);
  return !(el.getClientRects().length > 0 && s.visibility !== "hidden" && s.display !== "none");
};
const PREMIBILE = (sel) => {
  const el = document.querySelector(sel);
  return !!el && !el.disabled && !el.classList.contains("ui-state-disabled") && el.getClientRects().length > 0;
};

class Passi {
  constructor(sessione, riapri) {
    this.s = sessione;
    this.riapri = riapri;
  }

  async riga(giorno) {
    return rigaDel(await this.s.pagina(), giorno);
  }

  async apriDialog(giorno) {
    // Dopo il caricamento del giorno prima il portale ricostruisce la tabella, e il
    // bottone passa a questa riga: gli si dà il tempo.
    const p = await this.s.aspettaPagina((q) => !!rigaDel(q, giorno)?.idCarica, ATTESA_BOTTONE);
    const r = p ? rigaDel(p, giorno) : null;
    if (!r?.idCarica) return false;
    // Il dialog si apre da JS: è la chiamata che il bottone vero ha nel suo onclick.
    await this.s.scheda.esegui((bid, u) => {
      window.PrimeFaces.ab({ s: bid, p: bid, u, ps: true, onco() { window.PF("uploadFileDialog").show(); } });
    }, [r.idCarica, DIALOG]);
    if (!await this.s.scheda.finche(VISIBILE, [DIALOG])) throw new Error("il dialog di caricamento non si è aperto");
    return true;
  }

  async scegliFile(file) {
    // Scegliere il file NON carica: il fileUpload del portale aspetta «Carica».
    // Prima deve aver finito PrimeFaces: una risposta in arrivo può rifare il dialog, e con
    // lui il campo, e il file scelto andrebbe perso.
    await this.s.scheda.finche(() => window.PrimeFaces?.ajax?.Queue?.isEmpty?.() ?? true, []);
    const b64 = inBase64(file.byte);
    const ok = await this.s.scheda.finche((id, nome, dati) => {
      const campo = document.getElementById(id);
      if (!campo) return false;
      const byte = Uint8Array.from(atob(dati), (c) => c.charCodeAt(0));
      const trasferimento = new DataTransfer();
      trasferimento.items.add(new File([byte], nome, { type: "text/plain" }));
      campo.files = trasferimento.files;
      campo.dispatchEvent(new Event("change", { bubbles: true }));
      return true;
    }, [CAMPO_FILE, file.nome, b64]);
    if (!ok) throw new Error("il campo del file non c'è");
  }

  async pronto() {
    return !!await this.s.scheda.finche(PREMIBILE, [BOTTONE_CARICA]);
  }

  async conferma() {
    for (let i = 0; i < TENTATIVI_CARICA; i++) {
      try {
        if (await this.s.scheda.finche(PREMIBILE, [BOTTONE_CARICA])) {
          await this.s.scheda.esegui((sel) => { document.querySelector(sel).click(); }, [BOTTONE_CARICA]);
          // La chiusura del dialog dice che «Carica» è partito. Se è entrato lo dice la riga.
          if (await this.s.scheda.finche(INVISIBILE, [DIALOG])) return true;
        }
      } catch (e) {
        if (e instanceof SchedaChiusa) throw e;
      }
      this.s.reg.avviso(`tentativo ${i + 1}/${TENTATIVI_CARICA} su «Carica» fallito`);
      await dormi(1000);
    }
    return false;
  }

  async caricato(giorno) {
    const colSegno = (p) => !!rigaDel(p, giorno)?.caricato;
    if (await this.s.aspettaPagina(colSegno, ATTESA_CONFERMA)) return true;
    // La tabella in pagina può essere rimasta vecchia: la si riapre una volta.
    this.s.reg.info(`${ddmmaaaa(giorno)}: segni non visti, riapro la pagina dei movimenti`);
    await this.riapri();
    return colSegno(await this.s.pagina());
  }

  async annulla() {
    // Prima si toglie il file scelto, poi si chiude: niente resta per il giorno dopo.
    try {
      await this.s.scheda.esegui((a, c) => {
        document.querySelectorAll(a).forEach((el) => el.click());
        document.querySelector(c)?.click();
      }, [ANNULLA_FILE, CHIUDI_DIALOG]);
      await this.s.scheda.finche(INVISIBILE, [DIALOG], 10000);
    } catch (e) {
      if (e instanceof SchedaChiusa) throw e;
    }
  }
}

// ─── la sessione ─────────────────────────────────────────────────────────────

export class SessionePortale {
  constructor(registro) {
    this.reg = registro;
    this.scheda = new Scheda();
  }

  async apri() {
    if (!await this.scheda.creaSeManca(PREHOME_URL)) {
      if (!await this.dentro()) await this.scheda.vai(PREHOME_URL);
    }
    await this.primoPiano();
  }

  primoPiano() { return this.scheda.primoPiano(); }

  /** Una fascia in fondo alla pagina del portale: dice che sta lavorando l'estensione.
   *  Non intercetta i clic e sta fuori dai moduli. Vuota: la toglie. */
  async fascia(testo) {
    try {
      await this.scheda.esegui((t) => {
        const ID = "istat-uploader-fascia";
        let f = document.getElementById(ID);
        if (!t) {
          f?.remove();
          return;
        }
        if (!f) {
          f = document.createElement("div");
          f.id = ID;
          f.style.cssText = "position:fixed;left:0;right:0;bottom:0;z-index:2147483647;pointer-events:none;"
            + "padding:8px 16px;background:#1b1f24;color:#fff;font:600 13px/1.4 system-ui,sans-serif;text-align:center";
          document.documentElement.append(f);
        }
        f.textContent = t;
      }, [testo], "ISOLATED");
    } catch {
      // Una fascia che non si mette non ferma il giro.
    }
  }

  async pagina() {
    const html = await this.scheda.html();
    return leggiPagina(documento(html), html);
  }

  async aspettaPagina(condizione, massimo) {
    const fine = Date.now() + massimo;
    for (;;) {
      const p = await this.pagina();
      if (condizione(p)) return p;
      if (Date.now() >= fine) return null;
      await dormi(500);
    }
  }

  /** Il gestore è entrato? Serve solo a proseguire da sé: il bottone c'è comunque. */
  async dentro() {
    const url = await this.scheda.indirizzo();
    if (!url.includes("/private/")) return false;
    if (!url.includes("prehome")) return true;
    const html = await this.scheda.html();
    return strutture(documento(html), html).length > 0;
  }

  async fuori() {
    const url = await this.scheda.indirizzo();
    if (!url.includes("/private/")) return true;
    const t = (await this.scheda.testoVisibile()).toLowerCase();
    return messaggi.SEGNI_USCITA.some((s) => t.includes(s));
  }

  async scaduta() {
    if (!await this.fuori()) return false;
    await dormi(ATTESA_USCITA);
    return this.fuori();
  }

  async rientraSeUscito(rientra) {
    if (!rientra || !await this.scaduta()) return false;
    this.reg.avviso(`sessione finita, in attesa del rientro — indirizzo: ${ripulisciIndirizzo(await this.scheda.indirizzo())}`);
    await this.scheda.vai(PREHOME_URL).catch((e) => {
      if (e instanceof SchedaChiusa) throw e;
    });
    await rientra();
    return true;
  }

  async diagnosi(nome, cosa) {
    const html = await this.scheda.html();
    if (html) this.reg.copia(`${nome}.html`, ripulisci(html));
    this.reg.avviso(`${cosa} — indirizzo: ${ripulisciIndirizzo(await this.scheda.indirizzo())} · titolo: «${await this.scheda.titolo()}» · copia: ${html ? `${nome}.html` : "non salvata"}`);
  }

  async leggiStrutture() {
    await this.scheda.vai(PREHOME_URL);
    const fine = Date.now() + ATTESA_ELENCO;
    let html = "";
    let trovate = [];
    for (;;) {
      html = await this.scheda.html();
      trovate = strutture(documento(html), html);
      if (trovate.length || Date.now() >= fine) break;
      await dormi(500);
    }
    if (trovate.length) {
      this.reg.info(`strutture lette dal portale: ${trovate.map((s) => s.id).join(", ")}`);
      return trovate;
    }
    await this.diagnosi("pagina-strutture", "elenco delle strutture non letto");
    return [];
  }

  // ─── entrare in una struttura ─────────────────────────────────────────────

  /** Sempre da prehome come il gestore: l'indirizzo diretto da fuori dà «Error». */
  async entraDaPrehome(id) {
    await this.scheda.vai(PREHOME_URL);
    const fine = Date.now() + ATTESA_TENDINA;
    let esito;
    for (;;) {
      try {
        esito = await this.scheda.esegui((voluto) => {
          const sel = [...document.querySelectorAll('select[id$="_input"]')]
            .find((s) => [...s.options].some((o) => o.value === voluto));
          if (!sel) return document.querySelector('select[id$="_input"]') ? "assente" : "senza-elenco";
          const menu = sel.id.slice(0, -"_input".length);
          let fatto = false;
          if (window.PrimeFaces?.widgets) {
            for (const k of Object.keys(window.PrimeFaces.widgets)) {
              const w = window.PrimeFaces.widgets[k];
              if (w && w.id === menu && typeof w.selectValue === "function") {
                w.selectValue(voluto);
                fatto = true;
              }
            }
          }
          if (!fatto) {
            sel.value = voluto;
            sel.dispatchEvent(new Event("change", { bubbles: true }));
          }
          const modulo = sel.closest("form") || document;
          const accedi = [...modulo.querySelectorAll("button")].find((b) => /accedi/i.test(b.textContent || ""));
          if (!accedi) return "senza-accedi";
          accedi.click();
          return "ok";
        }, [id]);
      } catch (e) {
        if (e instanceof SchedaChiusa) throw e;
        esito = "senza-elenco";
      }
      const url = await this.scheda.indirizzo();
      if (esito !== "senza-elenco" || !url.includes("prehome") || Date.now() >= fine) break;
      await dormi(500);
    }
    this.reg.info(`struttura ${id} scelta da prehome: ${esito}`);
    if (esito !== "ok") return false;
    const limite = Date.now() + 20000;
    while ((await this.scheda.indirizzo()).includes("prehome") && Date.now() < limite) await dormi(200);
    const url = await this.scheda.indirizzo();
    this.reg.info(`dopo «Accedi»: ${ripulisciIndirizzo(url)}`);
    const pronta = (p) => p.righe.length > 0 && sullaStruttura(p, id) !== false;
    if (url.includes("movimentoospiti") && await this.aspettaPagina(pronta, ATTESA_PAGINA)) return true;
    // Il portale può atterrare su una sua home: solo adesso l'indirizzo diretto è buono.
    await this.scheda.vai(movimentiUrl(id));
    return !!await this.aspettaPagina(pronta, ATTESA_PAGINA);
  }

  async apriMovimenti(id, struttureNote) {
    await this.entraDaPrehome(id);
    const p = await this.pagina();
    if (p.struttura && !statoUtilizzabile(p.struttura.stato)) return messaggi.strutturaNonAttiva(id, p.struttura.stato);
    if (!p.righe.length) {
      await this.diagnosi(`pagina-movimenti-${id}`, `pagina dei movimenti di ${id} non aperta`);
      return messaggi.percheMovimentiNonAperti(id, {
        url: await this.scheda.indirizzo(), testoPagina: await this.scheda.testoVisibile(), struttureNote,
      });
    }
    if (sullaStruttura(p, id) === false) {
      await this.diagnosi(`pagina-movimenti-${id}`, `pagina dei movimenti di un'altra struttura invece di ${id}`);
      return messaggi.strutturaDiversa(id);
    }
    return null;
  }

  // ─── i mesi ───────────────────────────────────────────────────────────────

  async premi(id) {
    await this.scheda.esegui((x) => { document.getElementById(x).click(); }, [id]);
  }

  /** «si» · «chiuso» (prima dei mesi aperti) · «no». Le frecce vanno solo fra i mesi aperti. */
  async vaiAlMese(voluto) {
    for (let i = 0; i < MAX_PASSI_MESE; i++) {
      const p = await this.pagina();
      const dir = verso(p.mese, voluto);
      if (dir === null) return p.mese !== null ? "si" : "no";
      const b = dir === "indietro" ? p.indietro : p.avanti;
      if (!b) {
        this.reg.avviso(`frecce del mese non trovate (verso ${dir})`);
        return "no";
      }
      if (!b.attivo) return dir === "indietro" ? "chiuso" : "no";
      const prima = p.mese;
      await this.premi(b.id);
      if (!await this.aspettaPagina((q) => q.mese !== null && q.mese !== prima, ATTESA_PAGINA)) {
        this.reg.avviso(`il mese non è cambiato dopo «${dir}»`);
        return "no";
      }
    }
    return verso((await this.pagina()).mese, voluto) === null ? "si" : "no";
  }

  async apriScheda(nome) {
    const p = await this.pagina();
    const indice = p.schede[nome];
    if (indice === undefined) {
      this.reg.avviso(`scheda «${nome}» non trovata`);
      return null;
    }
    if (p.scheda !== nome) {
      try {
        await this.scheda.esegui((i) => {
          if (window.PF && window.PF("tabView")) {
            window.PF("tabView").select(i);
            return;
          }
          document.querySelectorAll("#movimentiTabView .ui-tabs-header")[i].click();
        }, [indice]);
      } catch (e) {
        if (e instanceof SchedaChiusa) throw e;
        this.reg.avviso(`scheda «${nome}» non aperta`);
        return null;
      }
    }
    return this.aspettaPagina((q) => q.scheda === nome && q.righe.length > 0, ATTESA_SCHEDA);
  }

  /** Un mese, dalla pagina dei movimenti già aperta. Sola lettura. */
  async leggiMese(voluto) {
    const { anno, mese } = parti(voluto);
    const delMese = (r) => r.giorno.slice(0, 7) === voluto.slice(0, 7);
    const etichetta = etichettaMese(anno, mese);
    const raggiunto = await this.vaiAlMese(voluto);
    if (raggiunto === "si") {
      const p = await this.pagina();
      return { righe: p.righe.filter(delMese), chiuso: false, invioPossibile: p.invioMensile ? p.invioMensile.attivo : null, problema: null };
    }
    if (raggiunto === "chiuso") {
      let chiuso = await this.apriScheda(SCHEDA_CHIUSO);
      if (chiuso && verso(chiuso.mese, voluto) !== null) {
        await this.vaiAlMese(voluto);
        chiuso = await this.pagina();
      }
      const righe = chiuso ? chiuso.righe.filter(delMese) : [];
      if (!righe.length) {
        await this.diagnosi(`pagina-periodo-chiuso-${voluto.slice(0, 7)}`, `periodo chiuso: giorni di ${etichetta} non letti`);
      }
      await this.apriScheda(SCHEDA_APERTO);
      return righe.length
        ? { righe, chiuso: true, invioPossibile: null, problema: null }
        : { righe: [], chiuso: true, invioPossibile: null, problema: messaggi.meseChiusoNonLetto(etichetta) };
    }
    const mostrato = (await this.pagina()).mese;
    await this.diagnosi(`pagina-mese-${voluto.slice(0, 7)}`, `${etichetta} non raggiunto`);
    const m = mostrato ? parti(mostrato) : null;
    return {
      righe: [], chiuso: false, invioPossibile: null,
      problema: messaggi.meseNonRaggiunto(m ? etichettaMese(m.anno, m.mese) : "un altro mese", etichetta),
    };
  }

  /** `mesi`: primi del mese. Risponde `{mesi: {AAAA-MM: letto}, avviso, struttura}`. */
  async leggiMesi(id, mesi, { struttureNote, rientra = null }) {
    for (;;) {
      const letti = await this.leggiMesiUnaVolta(id, mesi, struttureNote);
      if (!await this.rientraSeUscito(rientra)) return letti;
    }
  }

  async leggiMesiUnaVolta(id, mesi, struttureNote) {
    const out = { mesi: {}, avviso: "", struttura: null };
    const problema = await this.apriMovimenti(id, struttureNote);
    out.struttura = (await this.pagina()).struttura;
    if (problema) {
      out.avviso = problema;
      this.reg.avviso(`struttura ${id}: ${problema}`);
      return out;
    }
    for (const mese of mesi) {
      const letto = await this.leggiMese(mese);
      if (letto.righe.length || letto.chiuso) out.mesi[mese.slice(0, 7)] = letto;
      if (letto.problema) {
        this.reg.avviso(`struttura ${id}, ${mese.slice(0, 7)}: ${letto.problema}`);
        if (!letto.chiuso) out.avviso = letto.problema;
      }
    }
    return out;
  }

  // ─── il caricamento di una struttura ──────────────────────────────────────

  async apriMese(id, primo, struttureNote) {
    const problema = await this.apriMovimenti(id, struttureNote);
    if (problema) return problema;
    const { anno, mese } = parti(primo);
    const etichetta = etichettaMese(anno, mese);
    const raggiunto = await this.vaiAlMese(primo);
    if (raggiunto === "chiuso") return messaggi.meseChiuso(etichetta);
    if (raggiunto === "no") {
      const m = (await this.pagina()).mese;
      const p = m ? parti(m) : null;
      return messaggi.meseNonRaggiunto(p ? etichettaMese(p.anno, p.mese) : "un altro mese", etichetta);
    }
    return null;
  }

  /** Non solleva per i problemi di quella struttura: li mette nell'esito. Solleva
   *  solo per «Fermati» (da `avanzamento`) e per la scheda chiusa. */
  async carica({
    id, etichetta, perGiorno, diProva, periodo, prova, struttureNote, comunica, avanzamento, rientra,
    nonRiconosciuti = [], esito = nuovoEsito(etichetta, id),
  }) {
    const dillo = async (msg, nuovoGiorno = false) => {
      this.reg.info(`[struttura ${id}] ${msg}`);
      await avanzamento(msg, nuovoGiorno);
    };
    esito.nonRiconosciuti = [...nonRiconosciuti];
    if (diProva && !prova) {
      esito.saltata = MESSAGGIO_ZIP_DI_PROVA;
      await dillo(`salto: ${esito.saltata}`);
      return esito;
    }
    if (periodo) await this.caricaGiorni(esito, { id, perGiorno, periodo, prova, struttureNote, dillo, rientra });
    if (comunica && esito.saltata === null) {
      if (Object.values(esito.giorni).some((x) => x === Esito.NON_RIUSCITO || x === Esito.FILE_MANCANTE)) {
        esito.comunicazione = "comunicazione mensile non inviata: prima vanno sistemati i giorni non caricati.";
      } else {
        const p = parti(comunica);
        await dillo(`comunicazione mensile di ${etichettaMese(p.anno, p.mese)}`);
        await this.rientraSeUscito(rientra);
        const [riuscita, frase] = await this.inviaComunicazione(id, comunica, { prova, struttureNote });
        esito.comunicazioneRiuscita = riuscita;
        esito.comunicazione = frase;
      }
    }
    return esito;
  }

  async caricaGiorni(esito, { id, perGiorno, periodo, prova, struttureNote, dillo, rientra }) {
    const apri = () => this.apriMese(id, periodo.dal, struttureNote);
    const fermatiAlBuco = async (giorno) => {
      segna(esito, giorno, Esito.FILE_MANCANTE);
      esito.fermata = messaggi.fileMancanteFermo(giorno);
      this.reg.giorno(id, ddmmaaaa(giorno), Esito.FILE_MANCANTE, "", "");
      await dillo(esito.fermata);
    };
    await dillo("apro la pagina dei movimenti");
    let problema = await apri();
    while (await this.rientraSeUscito(rientra)) problema = await apri();
    if (problema) {
      esito.saltata = problema;
      await dillo(`salto: ${problema}`);
      return;
    }
    const buco = primoBuco((await this.pagina()).righe, perGiorno, periodo.dal);
    if (buco) {
      await fermatiAlBuco(buco);
      return;
    }
    const passi = new Passi(this, apri);
    const ripresa = async () => {
      if (!await this.rientraSeUscito(rientra)) return false;
      for (;;) {
        const pr = await apri();
        if (!pr) break;
        if (!await this.rientraSeUscito(rientra)) {
          esito.saltata = pr;
          await dillo(`salto: ${pr}`);
          break;
        }
      }
      return true;
    };
    const giaDentro = async (giorno) => {
      const r = await passi.riga(giorno);
      if (!r?.caricato) return false;
      segna(esito, giorno, Esito.GIA_CARICATO);
      this.reg.giorno(id, ddmmaaaa(giorno), Esito.GIA_CARICATO, "", "");
      return true;
    };
    for (const giorno of giorniFra(periodo.dal, periodo.al)) {
      await ripresa();
      if (esito.saltata) return;
      const file = perGiorno.get(giorno);
      if (!file) {
        // Senza file, ma forse il portale ce l'ha già: allora non manca niente.
        if (await giaDentro(giorno)) continue;
        // Una riga che non si legge perché siamo stati buttati fuori non è un buco.
        if (await ripresa()) {
          if (esito.saltata) return;
          if (await giaDentro(giorno)) continue;
        }
        await fermatiAlBuco(giorno);
        return;
      }
      await dillo(ddmmaaaa(giorno), true);
      const inCoda = prova && Object.values(esito.giorni).includes(Esito.DA_CARICARE);
      let risultato;
      let errore = "";
      let ritentato = false;
      for (;;) {
        delete esito.motivi[giorno];
        errore = "";
        try {
          risultato = await caricaGiorno(passi, giorno, file, { prova, inCoda, motivi: esito.motivi });
        } catch (e) {
          if (e instanceof SchedaChiusa) throw e;
          risultato = Esito.NON_RIUSCITO;
          errore = `${e?.name ?? "Errore"}: ${String(e?.message ?? e).split("\n")[0].slice(0, 200)}`;
          esito.motivi[giorno] = messaggi.GIORNO_ERRORE;
        }
        // Fallito perché la sessione è finita: non è un giorno fallito, si riprova
        // questo. Non si carica due volte: caricaGiorno rilegge la riga.
        if (risultato !== Esito.NON_RIUSCITO || !await ripresa()) break;
        if (esito.saltata) return;
        ritentato = true;
      }
      if (ritentato && risultato === Esito.GIA_CARICATO && !prova) risultato = Esito.CARICATO;
      segna(esito, giorno, risultato, file.nome);
      this.reg.giorno(id, ddmmaaaa(giorno), risultato, file.nome, errore);
      await dormi(PAUSA_FRA_GIORNI);
    }
  }

  // ─── la comunicazione telematica mensile ──────────────────────────────────

  /** Dopo, i dati del mese non si modificano più: solo a mese concluso, solo con ogni
   *  giorno inserito, solo se il dialogo nomina quel mese. In prova ci si ferma prima. */
  async inviaComunicazione(id, primo, { prova, struttureNote }) {
    const { anno, mese } = parti(primo);
    const etichetta = etichettaMese(anno, mese);
    const problema = await this.apriMovimenti(id, struttureNote);
    if (problema) return [false, problema];
    if (await this.vaiAlMese(primo) !== "si") return [false, `${etichetta} non è fra i mesi aperti: niente da comunicare.`];
    const p = await this.pagina();
    const manca = mancantiDelMese(p.righe, anno, mese, fineMese(anno, mese));
    if (manca.length) {
      return [false, `non invio la comunicazione di ${etichetta}: sul portale mancano ancora ${manca.length} giorni (il primo è il ${manca[0]}).`];
    }
    if (!p.invioMensile?.attivo) {
      return [false, `il portale non permette ancora la comunicazione di ${etichetta} (si fa a mese concluso, entro il 5 del mese dopo).`];
    }
    if (prova) return [true, `comunicazione di ${etichetta} pronta: in modalità vera la invierei.`];
    await this.premi(p.invioMensile.id);
    // Nella pagina ci sono altri tre «Sì, procedi», e uno elimina i movimenti: si
    // prende quello dentro il dialogo della comunicazione, e solo se è aperto.
    const dialogo = await this.scheda.finche(() => {
      for (const d of document.querySelectorAll(".ui-confirm-dialog, .ui-dialog")) {
        const titolo = d.querySelector(".ui-dialog-title")?.textContent ?? "";
        if (!/comunicazione telematica mensile/i.test(titolo)) continue;
        if (!(d.offsetParent !== null || getComputedStyle(d).display !== "none")) continue;
        const bottoni = [...d.querySelectorAll("button")];
        const si = bottoni.find((b) => /s[iì],?\s*procedi/i.test(b.textContent || ""));
        const no = bottoni.find((b) => /no,?\s*annulla/i.test(b.textContent || ""));
        return { testo: d.textContent || "", si: si ? si.id : "", no: no ? no.id : "" };
      }
      return null;
    }, [], 15000);
    if (!dialogo?.si) return [false, `il portale non ha chiesto la conferma per ${etichetta}: non ho inviato niente.`];
    if (meseNelDialogo(dialogo.testo) !== primo) {
      if (dialogo.no) await this.premi(dialogo.no);
      this.reg.avviso(`dialogo della comunicazione per un altro mese, atteso ${primo.slice(0, 7)}`);
      return [false, `il portale proponeva di comunicare un altro mese invece di ${etichetta}: ho annullato.`];
    }
    this.reg.info(`struttura=${id} comunicazione mensile ${primo.slice(0, 7)}: premo «Sì, procedi»`);
    await this.premi(dialogo.si);
    await dormi(2000);
    // La verifica: il mese non è più fra quelli aperti.
    await this.apriMovimenti(id, struttureNote);
    if (await this.vaiAlMese(primo) === "chiuso") {
      this.reg.info(`struttura=${id} comunicazione mensile ${primo.slice(0, 7)}: confermata`);
      return [true, `comunicazione di ${etichetta} inviata.`];
    }
    this.reg.avviso(`struttura=${id} comunicazione mensile ${primo.slice(0, 7)}: non confermata`);
    return [false, `ho premuto «Sì, procedi» per ${etichetta} ma il mese risulta ancora aperto: controlla sul portale nella scheda «Comunicazioni telematiche».`];
  }
}

function sullaStruttura(p, id) {
  if (!p.struttura?.id) return null;
  return p.struttura.id === id;
}
