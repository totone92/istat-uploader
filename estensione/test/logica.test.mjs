// La logica pura, senza browser: node --test estensione/test/
// Il DOM e il portale li provano i test in Chromium (test_estensione.py).

import assert from "node:assert/strict";
import { test } from "node:test";
import { deflateRawSync } from "node:zlib";

import { Flusso, memoriaLocale } from "../src/flusso.js";
import { serverValido } from "../src/hostlab.js";
import {
  abbina, cinAffidabile, idDalNome, intestazioneFile, normalizza, raggruppa,
} from "../src/logica/abbinamento.js";
import { Esito, nuovoEsito, riepilogo, segna } from "../src/logica/esito.js";
import { caricaGiorno, primoBuco } from "../src/logica/giro.js";
import { costruisci, elencoGiorni, statoDalleRighe, testoVoce } from "../src/logica/piano.js";
import { Registro } from "../src/logica/registro.js";
import { dataDalNome, leggiZip, nonRiconosciuti, SorgenteNonValida } from "../src/logica/sorgente.js";

function zip(voci, { metodo = 8 } = {}) {
  const locali = [];
  const centrale = [];
  let dove = 0;
  for (const [nome, testo] of voci) {
    const n = Buffer.from(nome);
    const dati = Buffer.from(testo);
    const c = metodo === 8 ? deflateRawSync(dati) : dati;
    const l = Buffer.alloc(30);
    l.writeUInt32LE(0x04034b50, 0);
    l.writeUInt16LE(metodo, 8);
    l.writeUInt32LE(c.length, 18);
    l.writeUInt32LE(dati.length, 22);
    l.writeUInt16LE(n.length, 26);
    locali.push(l, n, c);
    const g = Buffer.alloc(46);
    g.writeUInt32LE(0x02014b50, 0);
    g.writeUInt16LE(metodo, 10);
    g.writeUInt32LE(c.length, 20);
    g.writeUInt32LE(dati.length, 24);
    g.writeUInt16LE(n.length, 28);
    g.writeUInt32LE(dove, 42);
    centrale.push(g, n);
    dove += l.length + n.length + c.length;
  }
  const cd = Buffer.concat(centrale);
  const fine = Buffer.alloc(22);
  fine.writeUInt32LE(0x06054b50, 0);
  fine.writeUInt16LE(voci.length, 8);
  fine.writeUInt16LE(voci.length, 10);
  fine.writeUInt32LE(cd.length, 12);
  fine.writeUInt32LE(dove, 16);
  return new Uint8Array(Buffer.concat([...locali, cd, fine]));
}

const riga = (nome) => new TextEncoder().encode(`${nome.padEnd(255)}\r\ncontenuto`);

test("la data si legge dal nome, e decide il prefisso", () => {
  assert.equal(dataDalNome("schedine_istat_123_20261003.txt"), "2026-10-03");
  assert.equal(dataDalNome("schedine_istat_123_20261003.TXT"), "2026-10-03");
  assert.equal(dataDalNome("01022026.txt"), "2026-02-01");
  assert.equal(dataDalNome("schedine_istat_x_20261345.txt"), null);
  assert.equal(dataDalNome("31022026.txt"), null);
  assert.equal(dataDalNome("foto_20261003.txt"), null);
});

test("lo zip: solo .txt, a qualunque profondità, senza risalire", async () => {
  const f = await leggiZip(zip([
    ["a/b/01102026.txt", "uno"], ["../../02102026.txt", "due"], ["foto.jpg", "no"], ["c/", ""],
  ]));
  assert.deepEqual(f.map((x) => x.nome), ["01102026.txt", "02102026.txt"]);
  assert.equal(new TextDecoder().decode(f[0].byte), "uno");
  const senza = await leggiZip(zip([["01102026.txt", "tale e quale"]], { metodo: 0 }));
  assert.equal(new TextDecoder().decode(senza[0].byte), "tale e quale");
});

test("lo zip storto o gonfiato si ferma con un messaggio", async () => {
  await assert.rejects(leggiZip(new TextEncoder().encode("non sono uno zip"), "x.zip"), SorgenteNonValida);
  await assert.rejects(leggiZip(zip([["01102026.txt", "a".repeat(2 * 1024 * 1024)]])), /troppo grande/);
});

test("i file non riconosciuti si dicono", () => {
  const f = [{ nome: "PROVA.txt" }, { nome: "appunti.txt" }, { nome: "01102026.txt" }];
  assert.deepEqual(nonRiconosciuti(f), ["appunti.txt"]);
});

test("il nome nel file, in utf-8 o cp1252", () => {
  assert.equal(intestazioneFile(riga("TENANT A")), "TENANT A");
  assert.equal(intestazioneFile(new Uint8Array([0x43, 0x61, 0x66, 0xe8, 0x20, 0x0d, 0x0a, 0x41])), "Cafè");
  assert.equal(normalizza("Càsa  l'Ulivo S.r.l."), "CASA L ULIVO S R L");
  assert.equal(idDalNome("schedine_istat_IT054_20261003.txt"), "IT054");
});

// I nomi che arrivano davvero: scaricati da beb (id beb numerico, tenant con beb), generati
// da HostLab per chi non ha beb (CIN, o «hostlab» senza CIN), e quelli dello script originale.
const FORMATI = {
  beb: (g) => `schedine_istat_99001_202610${g}.txt`,
  generato_cin: (g) => `schedine_istat_IT054039B403012345_202610${g}.txt`,
  generato_senza_cin: (g) => `schedine_istat_hostlab_202610${g}.txt`,
  script_originale: (g) => `${g}102026.txt`,
};
const ATTESO = { beb: "nome", generato_cin: "cin", generato_senza_cin: "nome", script_originale: "nome" };

for (const [formato, nomeFile] of Object.entries(FORMATI)) {
  test(`un mese intero nel formato ${formato}: ogni giorno al suo posto, una struttura sola`, async () => {
    const giorni = Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, "0"));
    const file = await leggiZip(zip(giorni.map((g) => [`istat/${nomeFile(g)}`, `${"TENANT A".padEnd(255)}\r\n\r\ngiorno ${g}`])));
    assert.deepEqual(nonRiconosciuti(file), []);
    const gr = raggruppa(file, { marcatoreProva: false });
    assert.equal(gr.length, 1);
    assert.deepEqual([...gr[0].perGiorno.keys()].sort(), giorni.map((g) => `2026-10-${g}`));
    const [a] = abbina(gr, TRE, {});
    assert.equal(a.id, "12345");
    assert.equal(a.motivo, ATTESO[formato]);
  });
}

const gruppi = (nome, codice = "X1") => raggruppa([
  { nome: `schedine_istat_${codice}_20261001.txt`, byte: riga(nome) },
  { nome: `schedine_istat_${codice}_20261002.txt`, byte: riga(nome) },
], { marcatoreProva: false });

const TRE = [
  { id: "12345", nome: "TENANT A", cin: "IT054039B403012345" },
  { id: "12341", nome: "TENANT B", cin: "IT054039B403012341" },
  { id: "12340", nome: "TENANT C", cin: "IT054039B403012340" },
];

test("abbinamento: nome uguale, CIN se regge su tutte, ricordato; sennò si chiede", () => {
  assert.equal(abbina(gruppi("Tenant A"), TRE, {})[0].id, "12345");
  assert.equal(abbina(gruppi("altro", "IT054039B403012341"), TRE, {})[0].motivo, "cin");
  const senzaCin = TRE.map((s, i) => (i ? s : { ...s, cin: "" }));
  assert.equal(cinAffidabile(senzaCin), false);
  assert.equal(abbina(gruppi("altro", "IT054039B403012341"), senzaCin, {})[0].id, null);
  assert.equal(abbina(gruppi("altro"), TRE, { "id:X1": "12340" })[0].motivo, "ricordato");
  assert.equal(abbina(gruppi("altro"), TRE, {})[0].motivo, "da_chiedere");
  const prova = raggruppa([{ nome: "schedine_istat_P_20261001.txt", byte: riga("STRUTTURA DI PROVA") }], { marcatoreProva: false });
  assert.equal(abbina(prova, TRE, {})[0].id, null);
  assert.equal(abbina(prova, TRE, { "id:P": "12345" })[0].motivo, "prova");
});

test("due gruppi sulla stessa struttura si chiedono entrambi", () => {
  const due = [...gruppi("Tenant A", "X1"), ...gruppi("Tenant A", "X2")];
  assert.deepEqual(abbina(due, TRE, {}).map((a) => a.id), [null, null]);
});

test("il piano in una frase", () => {
  const stato = statoDalleRighe(
    Array.from({ length: 31 }, (_, i) => ({
      giorno: `2026-10-${String(i + 1).padStart(2, "0")}`, caricato: i < 28, pulsante: i === 28,
    })),
    { anno: 2026, mese: 10 },
  );
  const giorni = ["2026-10-29", "2026-10-30"];
  const [v] = costruisci([{ id: "1", nome: "TENANT A", giorni }], { 1: { "2026-10": stato } }, "2026-11-03");
  assert.deepEqual(v.daCaricare, [29, 30]);
  assert.deepEqual(v.senzaFile, [31]);
  assert.equal(testoVoce(v), "Ottobre 2026, TENANT A: 28 giorni già presenti, 2 da caricare (29 e 30). Sul portale mancano anche 31, ma nello zip non c'è il file.");
  assert.equal(elencoGiorni([1, 2, 3, 4, 5, 6, 7]), "dal 1 al 7 (7 giorni)");
});

test("oggi e il futuro non si caricano; il mese chiuso nemmeno", () => {
  const [v] = costruisci([{ id: "1", nome: "A", giorni: ["2026-11-01", "2026-11-02", "2026-11-03"] }], {}, "2026-11-02");
  assert.deepEqual(v.daCaricare, [1]);
  assert.deepEqual(v.futuri, [2, 3]);
  const [c] = costruisci([{ id: "1", nome: "A", giorni: ["2026-10-01"] }],
    { 1: { "2026-10": { anno: 2026, mese: 10, giorni: {}, chiuso: true } } }, "2026-11-02");
  assert.equal(c.chiuso, true);
  assert.deepEqual(c.daCaricare, []);
});

test("la comunicazione si propone solo entro il 5 e con tutti i giorni", () => {
  const tutti = Array.from({ length: 31 }, (_, i) => `2026-10-${String(i + 1).padStart(2, "0")}`);
  const voce = (oggi, giorni = tutti) => costruisci([{ id: "1", nome: "A", giorni }], {}, oggi)[0].comunicabile;
  assert.equal(voce("2026-11-05"), true);
  assert.equal(voce("2026-11-06"), false);
  assert.equal(voce("2026-11-02", tutti.slice(1)), false);
  assert.equal(voce("2026-10-31"), false);
});

class PassiFinti {
  constructor(riga = null, { pronto = true, caricato = true } = {}) {
    Object.assign(this, { rigaData: riga, prontoDato: pronto, caricatoDato: caricato, fatti: [] });
  }

  async riga() { return this.rigaData; }

  async apriDialog() { this.fatti.push("apri"); return true; }

  async scegliFile() { this.fatti.push("scegli"); }

  async pronto() { this.fatti.push("pronto"); return this.prontoDato; }

  async conferma() { this.fatti.push("CONFERMA"); return true; }

  async caricato() { this.fatti.push("rileggi"); return this.caricatoDato; }

  async annulla() { this.fatti.push("annulla"); }
}

test("in prova non si preme mai «Carica», e prova non ha default", async () => {
  const p = new PassiFinti();
  assert.equal(await caricaGiorno(p, "2026-10-01", {}, { prova: true }), Esito.DA_CARICARE);
  assert.deepEqual(p.fatti, ["apri", "scegli", "pronto", "annulla"]);
  await assert.rejects(caricaGiorno(new PassiFinti(), "2026-10-01", {}, {}), TypeError);
});

test("un giorno già caricato non si tocca in nessuna modalità", async () => {
  const dentro = { celle: ["", "01/10/2026", "3", "1", "0", "3", "2"], classi: [], titoli: [] };
  for (const prova of [true, false]) {
    const p = new PassiFinti(dentro);
    assert.equal(await caricaGiorno(p, "2026-10-01", {}, { prova }), Esito.GIA_CARICATO);
    assert.deepEqual(p.fatti, []);
  }
});

test("caricato lo dice la riga riletta, non il dialog chiuso", async () => {
  const motivi = {};
  const p = new PassiFinti(null, { caricato: false });
  assert.equal(await caricaGiorno(p, "2026-10-01", {}, { prova: false, motivi }), Esito.NON_RIUSCITO);
  assert.match(motivi["2026-10-01"], /riletta la riga/);
  assert.deepEqual(p.fatti, ["apri", "scegli", "CONFERMA", "rileggi"]);
});

test("il primo buco è prima del periodo", () => {
  const righe = [
    { giorno: "2026-10-01", caricato: true }, { giorno: "2026-10-02", caricato: false }, { giorno: "2026-10-03", caricato: false },
  ];
  assert.equal(primoBuco(righe, new Map([["2026-10-03", {}]]), "2026-10-03"), "2026-10-02");
  assert.equal(primoBuco(righe, new Map([["2026-10-02", {}]]), "2026-10-03"), null);
});

test("il riepilogo di prova lo dice, e quello vero dice cosa resta", () => {
  const e = nuovoEsito("TENANT A", "1");
  segna(e, "2026-10-01", Esito.DA_CARICARE, "01102026.txt");
  segna(e, "2026-10-02", Esito.GIA_CARICATO);
  const prova = riepilogo([e], "ottobre 2026", { prova: true });
  assert.match(prova, /^MODALITÀ PROVA — NON HO CARICATO NIENTE/);
  assert.match(prova, /01\/10\/2026 {2}← {2}01102026\.txt/);
  const v = nuovoEsito("TENANT B", "2");
  segna(v, "2026-10-03", Esito.NON_RIUSCITO);
  v.motivi["2026-10-03"] = "il portale non apre questo giorno";
  const vera = riepilogo([v], "ottobre 2026", { prova: false });
  assert.match(vera, /NON caricati: 03\/10/);
  assert.match(vera, /DA FARE:/);
  assert.throws(() => riepilogo([e], "x", {}), TypeError);
});

test("il registro filtra ciò che non deve restare", () => {
  const r = new Registro(() => new Date(2026, 10, 2, 9, 30, 1));
  r.info("mail mario@example.com cf RSSMRA80A01H501U tel 3331234567");
  assert.match(r.testo(), /^2026-11-02 09:30:01 \| INFO {4}\|/);
  assert.doesNotMatch(r.testo(), /mario@|RSSMRA|3331234567/);
});

// ─── il flusso, con un portale finto ─────────────────────────────────────

const delMese = (fino) => ({
  righe: Array.from({ length: 31 }, (_, i) => ({
    giorno: `2026-10-${String(i + 1).padStart(2, "0")}`, caricato: i < fino, idCarica: i === fino ? "b" : "",
  })),
  chiuso: false, invioPossibile: false, problema: null,
});

class PortaleFinto {
  constructor({ strutture = TRE, presenti = 29 } = {}) {
    Object.assign(this, { strutture, presenti, caricamenti: [], dentroOra: true, letti: [] });
  }

  async apri() {}

  async primoPiano() {}

  async fascia() {}

  async dentro() { return this.dentroOra; }

  async leggiStrutture() { return this.strutture.map(({ id, nome }) => ({ id, nome })); }

  async leggiMesi(id, mesi) {
    this.letti.push([id, mesi]);
    return {
      mesi: Object.fromEntries(mesi.map((m) => [m.slice(0, 7), delMese(this.presenti)])),
      avviso: "", struttura: this.strutture.find((s) => s.id === id),
    };
  }

  async carica(a) {
    this.caricamenti.push({ prova: a.prova, comunica: a.comunica, periodo: a.periodo });
    await a.avanzamento("30/10/2026", true);
    segna(a.esito, "2026-10-30", a.prova ? Esito.DA_CARICARE : Esito.CARICATO, "f.txt");
    if (!a.prova) this.presenti = 31;
    return a.esito;
  }
}

function flusso(portale, memoria = { strutture: [], alias: {} }, oggi = "2026-11-02") {
  const archivio = new Map();
  const m = memoriaLocale({
    getItem: (k) => archivio.get(k) ?? null, setItem: (k, v) => archivio.set(k, v),
  });
  m.scrivi(memoria);
  return new Flusso({
    portale: () => portale, oggi: () => oggi, registro: new Registro(), memoria: m,
    ritira: async () => { throw new Error("no"); }, dormi: async () => {},
  });
}

const zipOttobre = (dal = 30, al = 31, nome = "TENANT A") => zip(
  Array.from({ length: al - dal + 1 }, (_, i) => [`schedine_istat_X1_202610${dal + i}.txt`, `${nome.padEnd(255)}\r\nz`]),
);

const fine = async (f) => { await f.corrente; };

test("si parte in prova, e la vera vuole due conferme", async () => {
  const p = new PortaleFinto();
  const f = flusso(p);
  assert.equal(f.prova, true);
  await f.usaZip(zipOttobre(), "m.zip");
  await fine(f);
  assert.equal(f.schermata, "piano");
  assert.deepEqual(f.impostaProva(false), { errore: "Per la modalità vera serve la conferma." });
  assert.equal(f.prova, true);
  f.avvia();
  await fine(f);
  assert.equal(f.schermata, "esito");
  assert.equal(p.caricamenti[0].prova, true);
  assert.match(f.dati.testo, /NON HO CARICATO NIENTE/);
  f.tornaAlPiano();
  assert.deepEqual(f.impostaProva(false, true), { ok: true });
  assert.deepEqual(f.avvia(), { errore: "Per caricare davvero serve la conferma." });
  f.avvia({ confermato: true });
  await fine(f);
  assert.equal(p.caricamenti[1].prova, false);
  assert.match(f.dati.testo, /1 giorno caricato/);
});

test("alla fine i file escono dalla memoria", async () => {
  const f = flusso(new PortaleFinto());
  await f.usaZip(zipOttobre(), "m.zip");
  await fine(f);
  assert.ok(f.file.length);
  f.ricomincia();
  assert.deepEqual(f.file, []);
  assert.deepEqual(f.piano, []);
});

test("in locale restano numeri e abbinamenti, mai i file", async () => {
  const archivio = new Map();
  const m = memoriaLocale({ getItem: (k) => archivio.get(k) ?? null, setItem: (k, v) => archivio.set(k, v) });
  const f = new Flusso({
    portale: () => new PortaleFinto(), oggi: () => "2026-11-02", registro: new Registro(), memoria: m,
    ritira: async () => null, dormi: async () => {},
  });
  await f.usaZip(zipOttobre(30, 31, "STRANO"), "m.zip");
  for (let i = 0; i < 100 && f.schermata !== "abbina"; i++) await new Promise((r) => { setTimeout(r, 1); });
  const k = f.dati.gruppi[0].chiave;
  assert.deepEqual(f.confermaAbbinamenti({ [k]: "12345" }, true), { ok: true });
  await fine(f);
  const salvato = [...archivio.values()].join();
  assert.match(salvato, /"id:X1":"12345"/);
  assert.doesNotMatch(salvato, /\\r|\bz\b/);
});

test("un secondo gettone durante un giro si rifiuta", async () => {
  const f = flusso(new PortaleFinto());
  await f.usaZip(zipOttobre(), "m.zip");
  assert.deepEqual(f.usaGettone("1.x"), { ok: false, occupato: true });
  await fine(f);
});

test("la memoria rovinata non blocca", () => {
  const m = memoriaLocale({ getItem: () => "{rotta", setItem() { throw new Error("piena"); } });
  assert.deepEqual(m.leggi(), { strutture: [], alias: {} });
  m.scrivi({ strutture: [], alias: {} });
});

test("il gestore può fermarsi durante l'attesa del login", async () => {
  const p = new PortaleFinto();
  p.dentroOra = false;
  const f = flusso(p);
  f.dormi = () => new Promise((r) => { setTimeout(r, 1); });
  await f.usaZip(zipOttobre(), "m.zip");
  for (let i = 0; i < 200 && f.schermata !== "spid"; i++) await new Promise((r) => { setTimeout(r, 1); });
  f.annulla();
  await fine(f);
  assert.equal(f.schermata, "benvenuto");
  assert.deepEqual(f.file, []);
});

test("il server del pacchetto sta solo sui sottodomini di umbriaround.it", () => {
  assert.equal(serverValido("https://tenanta.umbriaround.it"), true);
  assert.equal(serverValido("https://a.b.umbriaround.it"), true);
  for (const s of ["http://tenanta.umbriaround.it", "https://umbriaround.it", "https://umbriaround.it.male.example",
    "https://maleumbriaround.it", "https://tenanta.umbriaround.it/x", "https://tenanta.umbriaround.it:8443", null]) {
    assert.equal(serverValido(s), false, String(s));
  }
});
