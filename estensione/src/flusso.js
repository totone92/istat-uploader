// Il flusso, una schermata per volta, senza interfaccia e senza browser (api.py): i
// test lo provano con un portale finto. Ogni cosa del portale passa da `portale()`.
//
//   benvenuto → (zip a mano o gettone di HostLab) → spid → lavoro → abbina se serve
//   → lavoro → piano → lavoro → esito
//
// Si parte SEMPRE in prova: è il valore iniziale, e la vera non si accende senza
// `confermato`. I dati degli ospiti stanno in `this.file`, in memoria: `dimentica()`
// li toglie, e chiudere la scheda fa lo stesso. In locale restano solo numeri e nomi
// delle strutture e gli abbinamenti confermati.

import {
  abbina, chiaveGruppo, chiaviAlias, giorniDelGruppo, raggruppa,
} from "./logica/abbinamento.js";
import {
  Esito, elenco, nuovoEsito, quanti, riepilogo, segna,
} from "./logica/esito.js";
import * as messaggi from "./logica/messaggi.js";
import { etichettaMese, iso, MESI } from "./logica/periodo.js";
import {
  costruisci, periodoVoce, scadenzaComunicazione, StatoGiorno, statoDalleRighe, testoVoce,
} from "./logica/piano.js";
import {
  haMarcatore, leggiZip, MESSAGGIO_ZIP_DI_PROVA, nonRiconosciuti, SorgenteNonValida,
} from "./logica/sorgente.js";

const ATTESA_LOGIN = 1000;

class Annullato extends Error {}

const chiaveVoce = (v) => `${v.id}|${String(v.anno).padStart(4, "0")}-${String(v.mese).padStart(2, "0")}`;

export class Flusso {
  constructor({
    portale, oggi, registro, memoria, ritira, dormi, versione = "", SchedaChiusa = class extends Error {},
    PacchettoNonDisponibile = class extends Error {}, inPrimoPiano = async () => {},
  }) {
    Object.assign(this, { portale, oggi, reg: registro, memoria, ritira, dormi, versione, SchedaChiusa, PacchettoNonDisponibile, inPrimoPiano });
    this.schermata = "benvenuto";
    this.dati = {};
    this.prova = true;
    this.occupato = false;
    this.ascolta = () => {};
    this.conf = memoria.leggi();
    this.dimentica();
    this.sessione = null;
    this.annullato = false;
    this.attesa = null;
    this.segnaleDentro = false;
    this.ultimoRiepilogo = "";
  }

  mostra(schermata, dati = {}) {
    this.schermata = schermata;
    this.dati = dati;
    this.ascolta();
    if (["benvenuto", "abbina", "manuale", "piano", "esito", "errore"].includes(schermata)) {
      this.inPrimoPiano();
      this.sessione?.fascia("");
    }
  }

  /** Toglie dalla memoria i file e tutto ciò che ne deriva. */
  dimentica() {
    this.file = [];
    this.gruppi = [];
    this.abbinamenti = [];
    this.piano = [];
    this.stati = {};
    this.strutture = [];
    this.note = new Set();
    this.etichettaPacchetto = "";
    this.scartati = [];
  }

  salvaConf() {
    this.memoria.scrivi(this.conf);
  }

  // ─── lo zip ─────────────────────────────────────────────────────────────

  async usaZip(byte, nome) {
    if (this.occupato) return { errore: "Sto lavorando: aspetta la fine del giro." };
    return this.lavora(() => this.giroZip(byte, nome));
  }

  async giroZip(byte, nome) {
    this.dimentica();
    let file;
    try {
      file = await leggiZip(byte, nome);
    } catch (e) {
      if (!(e instanceof SorgenteNonValida)) throw e;
      this.mostra("benvenuto", { avviso: messaggi.zipNonValido(e.message) });
      return;
    }
    await this.prendi(file, nome);
  }

  async prendi(file, nome) {
    const gruppi = raggruppa(file, { marcatoreProva: haMarcatore(file) });
    if (!gruppi.length) {
      this.mostra("benvenuto", { avviso: messaggi.nessunFileIstat(nome) });
      return;
    }
    if (gruppi.some((g) => g.diProva) && !this.prova) {
      this.mostra("benvenuto", { avviso: MESSAGGIO_ZIP_DI_PROVA });
      return;
    }
    this.file = file;
    this.gruppi = gruppi;
    this.scartati = nonRiconosciuti(file);
    this.reg.info(`zip: ${gruppi.length} gruppi di file, ${file.length} file`);
    await this.prepara();
  }

  // ─── il pacchetto di HostLab ────────────────────────────────────────────

  /** Il gettone arrivato dal tasto. Durante un giro si rifiuta: se poi scade, HostLab lo dice. */
  usaGettone(gettone) {
    if (this.occupato) return { ok: false, occupato: true };
    this.lavora(() => this.giroPacchetto(gettone));
    return { ok: true };
  }

  async giroPacchetto(gettone) {
    this.dimentica();
    this.mostra("lavoro", { titolo: "Ritiro il mese da HostLab", dettaglio: "Un momento: poi ti mostro cosa farò." });
    let p;
    try {
      p = await this.ritira(gettone);
    } catch (e) {
      if (!(e instanceof this.PacchettoNonDisponibile)) throw e;
      this.reg.avviso("pacchetto non ritirato");
      this.mostra("errore", { messaggio: e.message });
      return;
    }
    this.reg.info(`pacchetto ritirato | mese=${p.mese} | ${p.byte.length} byte`);
    let file;
    try {
      file = await leggiZip(p.byte, "il pacchetto di HostLab");
    } catch (e) {
      if (!(e instanceof SorgenteNonValida)) throw e;
      this.mostra("errore", { messaggio: e.message });
      return;
    }
    const m = /^(\d{4})-(\d{2})$/.exec(p.mese);
    await this.prendi(file, "il pacchetto di HostLab");
    this.etichettaPacchetto = [p.struttura, m ? `${MESI[+m[2] - 1]} ${m[1]}` : ""].filter(Boolean).join(" · ");
    if (this.schermata === "piano") this.mostraPiano();
  }

  // ─── entrare e leggere ──────────────────────────────────────────────────

  async entra() {
    this.sessione ??= this.portale();
    this.segnaleDentro = false;
    this.mostra("spid", { perche: "carica", fase: "apro" });
    await this.sessione.apri();
    this.dati = { perche: "carica", fase: "aspetto" };
    this.ascolta();
    await this.aspettaDentro();
  }

  rientro(titolo) {
    return async () => {
      this.segnaleDentro = false;
      this.mostra("spid", { perche: "scaduta", fase: "aspetto" });
      await this.sessione.primoPiano();
      await this.aspettaDentro();
      this.reg.info("rientrato dopo la sessione finita");
      this.mostra("lavoro", { titolo, dettaglio: "Sei rientrato: riprendo da dov'ero." });
    };
  }

  async aspettaDentro() {
    while (!this.annullato) {
      if (this.segnaleDentro || await this.sessione.dentro()) return;
      await this.dormi(ATTESA_LOGIN);
    }
    throw new Annullato();
  }

  sonoDentro() { this.segnaleDentro = true; }

  domanda(schermata, dati) {
    return new Promise((fatto) => {
      this.attesa = { schermata, fatto };
      this.mostra(schermata, dati);
    });
  }

  rispondi(schermata, risposta) {
    if (this.attesa?.schermata !== schermata) return { errore: "Questa domanda non è più aperta." };
    const { fatto } = this.attesa;
    this.attesa = null;
    fatto(risposta);
    return { ok: true };
  }

  annulla() {
    this.annullato = true;
    if (this.attesa) {
      const { fatto } = this.attesa;
      this.attesa = null;
      fatto(null);
    }
  }

  strutturaNota(id) { return this.strutture.find((s) => s.id === id); }

  async prepara() {
    await this.entra();
    this.mostra("lavoro", { titolo: "Leggo le tue strutture sul portale", dettaglio: "Solo lettura: non tocco niente." });
    let trovate = await this.sessione.leggiStrutture();
    let manuale = false;
    if (!trovate.length) {
      const voci = await this.domanda("manuale", { messaggio: messaggi.STRUTTURE_NON_LETTE });
      if (voci === null) throw new Annullato();
      trovate = voci;
      manuale = true;
    }
    this.note = manuale ? new Set() : new Set(trovate.map((s) => s.id));
    const ricordate = new Map(this.conf.strutture.map((s) => [s.id, s]));
    this.strutture = trovate.map((s) => ({
      id: s.id, nome: s.nome || ricordate.get(s.id)?.nome || `Struttura ${s.id}`, cin: s.cin || ricordate.get(s.id)?.cin || "",
    }));
    this.conf.strutture = this.strutture.map((s) => ({ ...s }));
    this.salvaConf();

    let ab = abbina(this.gruppi, this.strutture, this.conf.alias);
    // Il CIN serve solo se qualcosa resta da decidere, e sta nella pagina di ogni
    // struttura: si va a leggerlo una volta, poi resta ricordato.
    if (ab.some((a) => a.id === null && a.motivo !== "prova") && this.strutture.some((s) => !s.cin)) {
      let i = 0;
      const senza = this.strutture.filter((s) => !s.cin);
      for (const s of senza) {
        if (this.annullato) throw new Annullato();
        i += 1;
        this.mostra("lavoro", { titolo: "Leggo i codici delle strutture", dettaglio: s.nome, passo: i, totale: senza.length });
        const l = await this.sessione.leggiMesi(s.id, [], { struttureNote: this.note, rientra: this.rientro("Leggo i codici delle strutture") });
        if (l.struttura?.cin && [s.id, ""].includes(l.struttura.id)) s.cin = l.struttura.cin;
      }
      this.conf.strutture = this.strutture.map((s) => ({ ...s }));
      this.salvaConf();
      ab = abbina(this.gruppi, this.strutture, this.conf.alias);
    }
    this.abbinamenti = ab;
    let scelte = Object.fromEntries(ab.map((a) => [chiaveGruppo(a.gruppo), a.id ?? ""]));
    if (ab.some((a) => a.id === null)) {
      const risposta = await this.domanda("abbina", this.vistaAbbina());
      if (risposta === null) throw new Annullato();
      scelte = risposta;
    }
    await this.leggiStati(scelte);
  }

  vistaAbbina() {
    const nomi = new Map(this.strutture.map((s) => [s.id, s.nome]));
    const una = this.strutture.length === 1;
    return {
      gruppi: this.abbinamenti.map((a) => {
        const g = a.gruppo;
        const mesi = [...new Set(giorniDelGruppo(g).map((d) => d.slice(0, 7)))]
          .map((k) => etichettaMese(+k.slice(0, 4), +k.slice(5))).join(", ");
        const proposte = a.proposte.length ? a.proposte : [...nomi.keys()];
        return {
          chiave: chiaveGruppo(g), nomeNelFile: g.nomeNelFile || "(nessun nome nel file)", codice: g.idNelNome ?? "",
          giorni: g.perGiorno.size, mesi, diProva: g.diProva, domanda: a.domanda,
          scelta: a.id ?? (proposte.length && (una || g.diProva) ? proposte[0] : ""),
          proposte: proposte.map((id) => ({ id, nome: nomi.get(id) ?? id })),
        };
      }),
    };
  }

  /** Il «Continua» sugli abbinamenti. */
  confermaAbbinamenti(scelte, ricorda) {
    if (this.attesa?.schermata !== "abbina") return { errore: "Non c'è niente da abbinare." };
    const ids = new Set(this.strutture.map((s) => s.id));
    const finali = {};
    for (const a of this.abbinamenti) {
      const k = chiaveGruppo(a.gruppo);
      const scelta = (scelte[k] ?? "").trim();
      if (scelta && !ids.has(scelta)) return { errore: "Scegli una delle tue strutture." };
      if (scelta && a.gruppo.diProva && !this.prova) return { errore: MESSAGGIO_ZIP_DI_PROVA };
      finali[k] = scelta;
    }
    const usati = Object.values(finali).filter(Boolean);
    if (!usati.length) return { errore: "Abbina almeno un gruppo di file a una struttura." };
    if (usati.length !== new Set(usati).size) {
      return { errore: "Due gruppi di file non possono andare sulla stessa struttura: uno dei due è di un'altra." };
    }
    if (ricorda) {
      for (const a of this.abbinamenti) {
        const k = chiaveGruppo(a.gruppo);
        if (a.gruppo.diProva || !finali[k]) continue; // lo zip di prova non si ricorda mai
        for (const c of chiaviAlias(a.gruppo)) this.conf.alias[c] = finali[k];
      }
      this.salvaConf();
    }
    return this.rispondi("abbina", finali);
  }

  async leggiStati(scelte) {
    this.scelte = scelte;
    const coinvolte = this.abbinamenti.filter((a) => scelte[chiaveGruppo(a.gruppo)]);
    let i = 0;
    for (const a of coinvolte) {
      if (this.annullato) throw new Annullato();
      i += 1;
      const id = scelte[chiaveGruppo(a.gruppo)];
      const s = this.strutturaNota(id);
      const titolo = "Guardo quali giorni ci sono già";
      this.mostra("lavoro", { titolo, dettaglio: s.nome, passo: i, totale: coinvolte.length });
      const mesi = [...new Set(giorniDelGruppo(a.gruppo).map((d) => `${d.slice(0, 7)}-01`))];
      const letti = await this.sessione.leggiMesi(id, mesi, { struttureNote: this.note, rientra: this.rientro(titolo) });
      this.acquisisci(id, letti);
      if (letti.avviso) this.avvisi[id] = letti.avviso;
    }
    this.costruisciPiano();
  }

  get avvisi() {
    this._avvisi ??= {};
    return this._avvisi;
  }

  acquisisci(id, letti) {
    this.stati[id] ??= {};
    for (const [k, l] of Object.entries(letti.mesi)) {
      this.stati[id][k] = statoDalleRighe(
        l.righe.map((r) => ({ giorno: r.giorno, caricato: r.caricato, pulsante: !!r.idCarica })),
        { anno: +k.slice(0, 4), mese: +k.slice(5), chiuso: l.chiuso, invioPossibile: l.invioPossibile },
      );
    }
  }

  costruisciPiano() {
    this.piano = [];
    for (const a of this.abbinamenti) {
      const id = this.scelte[chiaveGruppo(a.gruppo)];
      const s = id ? this.strutturaNota(id) : null;
      if (!s) continue;
      for (const v of costruisci([{ id, nome: s.nome, giorni: giorniDelGruppo(a.gruppo) }], this.stati, this.oggi())) {
        this.piano.push({ voce: v, gruppo: a.gruppo });
      }
    }
    this.mostraPiano();
  }

  mostraPiano() {
    const voci = this.piano.map((p) => p.voce);
    this.mostra("piano", {
      voci: voci.map((v) => ({
        testo: testoVoce(v), struttura: v.nome, mese: etichettaMese(v.anno, v.mese),
        presenti: v.presenti === null ? null : v.presenti.length,
        daCaricare: v.daCaricare.length, futuri: v.futuri, chiuso: v.chiuso,
        chiave: chiaveVoce(v), comunicabile: v.comunicabile,
        scadenza: scadenzaComunicazione(v.anno, v.mese).slice(5).split("-").reverse().join("/"),
        avviso: this.avvisi[v.id] ?? "",
      })),
      nienteDaFare: !voci.some((v) => v.daCaricare.length || v.comunicabile),
      diProva: this.piano.some((p) => p.gruppo.diProva),
      daHostlab: this.etichettaPacchetto,
      nonRiconosciuti: this.scartati.length,
      confermaVera: this.fraseConferma(voci),
    });
  }

  fraseConferma(voci) {
    const pezzi = voci.filter((v) => v.daCaricare.length)
      .map((v) => `${v.nome}: ${etichettaMese(v.anno, v.mese)}, ${v.daCaricare.length} giorni`);
    if (!pezzi.length) return "Non carico nessun giorno: sono già tutti sul portale.";
    return `Carico DAVVERO sul portale — ${pezzi.join("; ")}.`;
  }

  // ─── modalità e giro ────────────────────────────────────────────────────

  impostaProva(prova, confermato = false) {
    if (this.occupato) return { errore: "Sto lavorando: cambia modalità a giro finito." };
    if (!prova && !confermato) return { errore: "Per la modalità vera serve la conferma." };
    this.prova = !!prova;
    this.reg.info(`modalità: ${prova ? "prova" : "VERA"}`);
    if (this.schermata === "piano") this.mostraPiano();
    else this.ascolta();
    return { ok: true };
  }

  avvia({ confermato = false, comunica = [] } = {}) {
    if (this.schermata !== "piano" || !this.piano.length) return { errore: "Non c'è un piano da eseguire." };
    if (!this.prova && !confermato) return { errore: "Per caricare davvero serve la conferma." };
    if (!this.prova && this.piano.some((p) => p.gruppo.diProva)) return { errore: MESSAGGIO_ZIP_DI_PROVA };
    const chieste = new Set(comunica);
    const possibili = new Set(this.piano.filter((p) => p.voce.comunicabile).map((p) => chiaveVoce(p.voce)));
    if ([...chieste].some((c) => !possibili.has(c))) {
      return { errore: "La comunicazione mensile si può chiedere solo per un mese concluso, entro il 5 del mese dopo, con tutti i giorni." };
    }
    if (!this.piano.some((p) => p.voce.daCaricare.length) && !chieste.size) return { errore: "Non c'è niente da caricare." };
    const prova = this.prova;
    return this.lavora(() => this.giroCarica(prova, chieste));
  }

  async giroCarica(prova, comunica) {
    const esiti = [];
    const voci = this.piano.filter((p) => periodoVoce(p.voce) || comunica.has(chiaveVoce(p.voce)));
    const totale = voci.reduce((n, p) => n + p.voce.daCaricare.length, 0);
    const toccate = [];
    let fatti = 0;
    this.reg.info(`giro: inizio | versione=${this.versione} | modalità=${prova ? "prova" : "VERA"} | ${voci.map((p) => `${p.voce.id} ${etichettaMese(p.voce.anno, p.voce.mese)}`).join(" ; ")}`);
    const verbo = prova ? "Provo" : "Carico";
    const modo = prova ? "PROVA" : "VERA";
    try {
      await this.entra();
      // In primo piano il portale: è così che è stato provato sul campo, e Chrome
      // rallenta e congela le schede nascoste.
      await this.sessione.primoPiano();
      for (const { voce: v, gruppo } of voci) {
        if (this.annullato) break;
        toccate.push(v);
        const titolo = `${verbo} ${v.nome}`;
        const mese = etichettaMese(v.anno, v.mese);
        const esito = nuovoEsito(v.nome, v.id);
        esiti.push(esito);
        // Ciò che c'era già lo si dice anche alla fine, non solo nel piano.
        for (const g of v.presenti ?? []) segna(esito, iso(v.anno, v.mese, g), Esito.GIA_CARICATO);
        await this.sessione.carica({
          id: v.id, etichetta: v.nome, perGiorno: gruppo.perGiorno, diProva: gruppo.diProva,
          periodo: periodoVoce(v), prova, struttureNote: this.note,
          comunica: comunica.has(chiaveVoce(v)) ? `${chiaveVoce(v).split("|")[1]}-01` : null,
          nonRiconosciuti: this.scartati, esito,
          rientra: this.rientro(titolo),
          avanzamento: async (msg, nuovoGiorno) => {
            // «Fermati»: fra un giorno e l'altro, mai a metà di uno.
            if (this.annullato) throw new Annullato();
            if (nuovoGiorno) fatti += 1;
            this.mostra("lavoro", { titolo, dettaglio: `${mese} — ${msg}`, passo: Math.min(fatti, totale), totale, prova });
            await this.sessione.fascia(`Istat Uploader · modalità ${modo} · ${v.nome} · ${Math.min(fatti, totale)} di ${totale} — non chiudere questa scheda. Per fermarti torna sulla scheda «Istat Uploader».`);
          },
        });
      }
      if (!prova) await this.rileggi(toccate, esiti, true);
    } catch (e) {
      if (!(e instanceof Annullato)) throw e;
      this.annullato = false;
      this.reg.info("giro fermato dal gestore");
      // I giorni entrati fin qui sul portale ci restano: si dice cosa risulta.
      if (!prova && toccate.length) {
        this.annullato = false;
        await this.rileggi(toccate, esiti, false);
      }
      this.mostraEsito(esiti, voci, prova, true);
      return;
    }
    this.mostraEsito(esiti, voci, prova, false);
  }

  mostraEsito(esiti, voci, prova, fermato) {
    const mesi = [...new Set(voci.map((p) => etichettaMese(p.voce.anno, p.voce.mese)))].sort();
    const testo = riepilogo(esiti, mesi.join(" e "), { prova });
    this.ultimoRiepilogo = testo;
    this.reg.info(`giro: fine | modalità=${prova ? "prova" : "VERA"} | ${esiti.map((e) => `${e.id}: ${e.saltata ? "saltata" : Object.values(Esito).filter((k) => quanti(e, k)).map((k) => `${k}=${quanti(e, k)}`).join(", ")}`).join(" ; ")}`);
    this.mostra("esito", {
      prova, fermato, testo,
      strutture: esiti.map((e) => ({
        nome: e.etichetta, saltata: e.saltata ?? "",
        caricati: quanti(e, Esito.CARICATO), daCaricare: quanti(e, Esito.DA_CARICARE), gia: quanti(e, Esito.GIA_CARICATO),
        nonRiusciti: elenco(e, Esito.NON_RIUSCITO).map((g) => g.slice(8)),
        motivi: [...new Set(Object.values(e.motivi))],
        mancanti: elenco(e, Esito.FILE_MANCANTE).map((g) => g.slice(8)),
        fermata: e.fermata, nonRiletto: e.statoNonRiletto,
        comunicazione: e.comunicazione, comunicazioneRiuscita: e.comunicazioneRiuscita,
      })),
    });
  }

  /** A fine giro ha ragione il portale: se la lettura smentisce l'esito, vale la lettura. */
  async rileggi(toccate, esiti, conRientro) {
    const perStruttura = new Map();
    for (const v of toccate) {
      if (!perStruttura.has(v.id)) perStruttura.set(v.id, new Set());
      perStruttura.get(v.id).add(`${chiaveVoce(v).split("|")[1]}-01`);
    }
    for (const [id, mesi] of perStruttura) {
      const titolo = `Rileggo ${this.strutturaNota(id)?.nome ?? id} sul portale`;
      this.mostra("lavoro", { titolo, dettaglio: "Controllo che i giorni ci siano davvero." });
      let letti = { mesi: {}, avviso: "" };
      try {
        letti = await this.sessione.leggiMesi(id, [...mesi].sort(), {
          struttureNote: this.note, rientra: conRientro ? this.rientro(titolo) : null,
        });
      } catch (e) {
        if (e instanceof Annullato || e instanceof this.SchedaChiusa) throw e;
        this.reg.avviso(`rilettura della struttura ${id}: ${e?.name}`);
      }
      this.acquisisci(id, letti);
      for (const e of esiti.filter((x) => x.id === id)) this.confronta(e, mesi);
    }
  }

  confronta(e, mesi) {
    for (const primo of [...mesi].sort()) {
      const k = primo.slice(0, 7);
      const stato = this.stati[e.id]?.[k];
      const riletto = stato && (Object.keys(stato.giorni).length || stato.chiuso);
      if (!riletto) {
        e.statoNonRiletto = messaggi.statoNonRiletto(etichettaMese(+k.slice(0, 4), +k.slice(5)));
        continue;
      }
      if (stato.chiuso && !Object.keys(stato.giorni).length) continue;
      for (const g of Object.keys(e.giorni).filter((x) => x.startsWith(k))) {
        const sulPortale = stato.giorni[+g.slice(8)] === StatoGiorno.CARICATO;
        if (e.giorni[g] === Esito.CARICATO && !sulPortale) {
          this.reg.avviso(`struttura=${e.id} giorno=${g}: esito caricato, smentito dalla rilettura`);
          segna(e, g, Esito.NON_RIUSCITO);
          e.motivi[g] = messaggi.GIORNO_SMENTITO;
        } else if (e.giorni[g] === Esito.NON_RIUSCITO && sulPortale) {
          this.reg.avviso(`struttura=${e.id} giorno=${g}: esito non riuscito, ma sul portale c'è`);
          segna(e, g, Esito.CARICATO);
          delete e.motivi[g];
        }
      }
    }
  }

  /** Dopo una prova si torna al piano con gli stessi file: un gettone vale una volta. */
  tornaAlPiano() {
    if (this.occupato || !this.piano.length) return;
    this.mostraPiano();
  }

  /** Ricomincia: dei file non resta niente. */
  ricomincia() {
    if (this.occupato) {
      if (this.schermata === "lavoro") return;
      this.annulla();
    }
    this.dimentica();
    this._avvisi = {};
    // Un mese nuovo si riparte in prova, anche se quello prima è andato in vera.
    this.prova = true;
    this.mostra("benvenuto");
  }

  // ─── interni ────────────────────────────────────────────────────────────

  lavora(giro) {
    if (this.occupato) return { errore: "Sto già lavorando." };
    this.occupato = true;
    this.annullato = false;
    this.corrente = (async () => {
      try {
        await giro();
      } catch (e) {
        if (e instanceof Annullato) {
          this.annullato = false;
          this.dimentica();
          this.mostra("benvenuto", { avviso: "Fermato. Non ho caricato niente." });
        } else if (e instanceof this.SchedaChiusa) {
          this.reg.avviso("scheda del portale chiusa a metà");
          this.mostra("errore", { messaggio: "Hai chiuso la scheda di Turismatica e mi sono fermato. I giorni già caricati restano sul portale: ricomincia, salto quelli che ci sono." });
        } else {
          this.reg.avviso(`giro interrotto: ${e?.name}: ${String(e?.message).slice(0, 200)}`);
          this.mostra("errore", { messaggio: "Qualcosa è andato storto e mi sono fermato. Scarica il registro da «Dettagli» e mandalo a chi ti assiste." });
        }
      } finally {
        this.occupato = false;
        this.ascolta();
      }
    })();
    return { ok: true };
  }
}

/** La memoria locale: solo strutture e abbinamenti, mai i file. Se il browser non la
 *  dà, si lavora lo stesso: il gestore ricontrolla gli abbinamenti la prossima volta. */
export const memoriaLocale = (archivio, chiave = "istat-uploader") => ({
  leggi() {
    try {
      const v = JSON.parse(archivio.getItem(chiave));
      if (v && Array.isArray(v.strutture) && v.alias) return v;
    } catch {
      // vuota o rovinata: si riparte.
    }
    return { strutture: [], alias: {} };
  },
  scrivi(conf) {
    try {
      archivio.setItem(chiave, JSON.stringify({
        strutture: conf.strutture.map(({ id, nome, cin }) => ({ id, nome, cin })), alias: conf.alias,
      }));
    } catch {
      // vedi sopra
    }
  },
});

