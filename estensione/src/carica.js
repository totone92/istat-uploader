// L'interfaccia: non decide niente, ridisegna da `flusso` e gli passa i gesti. Stessa
// voce dell'uploader (ui/app.js). Tutto il testo che arriva da fuori passa da esc().

import { Flusso, memoriaLocale } from "./flusso.js";
import { gettoneValido, PacchettoNonDisponibile, ritiraPacchetto } from "./hostlab.js";
import { oggiLocale } from "./logica/periodo.js";
import { Registro } from "./logica/registro.js";
import { DIMENSIONE_MASSIMA_ZIP } from "./logica/sorgente.js";
import { SchedaChiusa, SessionePortale } from "./portale.js";
import { dormi } from "./tempo.js";

const app = document.getElementById("app");
const versione = chrome.runtime.getManifest().version;
const registro = new Registro();
registro.info(`avvio | versione=${versione}`);

const archivio = (() => {
  try {
    return window.localStorage;
  } catch {
    return { getItem: () => null, setItem: () => {} };
  }
})();

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const flusso = new Flusso({
  portale: () => new SessionePortale(registro),
  oggi: () => oggiLocale(),
  registro,
  memoria: memoriaLocale(archivio),
  ritira: ritiraPacchetto,
  dormi,
  versione,
  SchedaChiusa,
  PacchettoNonDisponibile,
  inPrimoPiano: async () => {
    const io = await chrome.tabs.getCurrent();
    if (io) await chrome.tabs.update(io.id, { active: true }).catch(() => {});
  },
});

const giorni = (n) => (n === 1 ? "1 giorno" : `${n} giorni`);

const SCHERMATE = {
  benvenuto(d) {
    return `
      <section class="scheda eroe">
        ${d.avviso ? `<div class="avviso errore st2"><span class="segno">!</span><div>${esc(d.avviso)}</div></div>` : ""}
        <h1>Carica i movimenti ISTAT su Turismatica, senza farli a mano</h1>
        <p class="intro">Dentro il tuo browser, dopo il tuo accesso con SPID o CIE. Si parte sempre in prova:
          ti dico cosa caricherei e cosa c'è già, e sul portale non cambia niente.</p>
        <div class="zona-zip" id="zona-zip">
          <h2>Trascina qui lo zip dei file ISTAT</h2>
          <p class="piccolo-testo">Quello del mese, dal tuo gestionale. Se usi HostLab, premi «Carica su Turismatica» nel report ISTAT: arriva da solo.</p>
          <div class="riga-bottoni st1">
            <button class="bottone primario" type="button" data-azione="scegli-zip">Scegli il file…</button>
          </div>
        </div>
        <p class="rassicura">🔒 I file restano in questa scheda per il tempo del caricamento: non vanno a Fortitudo né altrove, se non a Turismatica. SPID e CIE li inserisci tu: l'estensione non li vede.</p>
      </section>`;
  },

  spid(d) {
    if (d.fase === "apro") {
      return `<section class="scheda centrato"><span class="rotella" role="status" aria-label="Sto aprendo il portale"></span>
        <h2 class="st7">Apro il portale in una nuova scheda…</h2></section>`;
    }
    const scaduta = d.perche === "scaduta";
    return `
      <section class="scheda centrato">
        <div class="icona-grande" aria-hidden="true">🔑</div>
        <h1>${scaduta ? "Il portale ti ha fatto uscire" : "Entra con SPID o CIE"}</h1>
        <p class="intro">${scaduta
          ? "La sessione di Turismatica è scaduta e ho messo in pausa il giro: non ho perso niente. Nella scheda di Turismatica entra di nuovo con SPID o CIE. Appena sei dentro riprendo dal giorno dove ero."
          : "Nella scheda di Turismatica che si è aperta, premi «Accedi» ed entra come fai sempre. Prenditi il tempo che ti serve: non c'è nessuna scadenza. Appena sei dentro torno qui, in sola lettura."}</p>
        <div class="riga-bottoni st0">
          <button class="bottone primario grande" type="button" data-azione="sono-dentro">${scaduta ? "Sono dentro: riprendi" : "Sono dentro: vai"}</button>
          <button class="bottone fantasma" type="button" data-azione="annulla">${scaduta ? "Fermati" : "Annulla"}</button>
        </div>
        <p class="piccolo-testo st5">Se mi accorgo da solo che sei entrato, proseguo senza aspettare il bottone.</p>
      </section>`;
  },

  lavoro(d) {
    const barra = d.totale
      ? `<progress class="barra" max="${esc(d.totale)}" value="${esc(d.passo || 0)}" aria-label="Avanzamento"></progress>
         <p class="piccolo-testo">${esc(d.passo || 0)} di ${esc(d.totale)}</p>`
      : "";
    return `
      <section class="scheda centrato">
        <span class="rotella" role="status" aria-label="Sto lavorando"></span>
        <h2 class="st7">${esc(d.titolo)}</h2>
        <p class="intro">${esc(d.dettaglio || "")}</p>
        ${barra}
        <p class="piccolo-testo st4">Non chiudere la scheda di Turismatica mentre lavoro.</p>
        <div class="riga-bottoni st0">
          <button class="bottone fantasma" type="button" data-azione="annulla">Fermati</button>
        </div>
      </section>`;
  },

  manuale(d) {
    const riga = () => `
      <div class="manuale-riga">
        <input type="text" class="m-id" inputmode="numeric" aria-label="Numero della struttura" placeholder="Numero, es. 12345">
        <input type="text" class="m-nome" aria-label="Nome della struttura" placeholder="Nome della struttura (facoltativo)">
      </div>`;
    return `
      <section class="scheda">
        <h1>Dimmi tu le tue strutture</h1>
        <div class="avviso attenzione st6"><span class="segno">!</span><div>${esc(d.messaggio)}</div></div>
        <div class="manuale-righe">${riga()}${riga()}</div>
        <div class="riga-bottoni">
          <button class="bottone primario" type="button" data-azione="manuale-continua">Continua</button>
          <button class="bottone fantasma" type="button" data-azione="annulla">Annulla</button>
        </div>
      </section>`;
  },

  abbina(d) {
    const gruppi = d.gruppi.map((g) => `
      <div class="scheda" data-chiave="${esc(g.chiave)}">
        <div class="etichetta">${g.diProva ? "File di prova" : "File da abbinare"}</div>
        <h3 class="st10">«${esc(g.nomeNelFile)}»${g.codice ? ` <span class="distintivo">codice ${esc(g.codice)}</span>` : ""}</h3>
        <p class="piccolo-testo st9">${giorni(g.giorni)} · ${esc(g.mesi)}</p>
        ${g.domanda ? `<p class="st4">${esc(g.domanda)}</p>` : ""}
        <label class="campo"><span class="etichetta">Struttura</span>
          <select class="a-scelta">
            <option value="">Non caricare questi file</option>
            ${g.proposte.map((p) => `<option value="${esc(p.id)}" ${p.id === g.scelta ? "selected" : ""}>${esc(p.nome)} (n° ${esc(p.id)})</option>`).join("")}
          </select>
        </label>
      </div>`).join("");
    const soloProva = d.gruppi.every((g) => g.diProva);
    return `
      <section>
        <h1>Di quale struttura sono questi file?</h1>
        <p class="intro">Non lo indovino: quando dai file non è chiaro, chiedo a te.</p>
        <div class="strutture">${gruppi}</div>
        ${soloProva ? "" : '<label class="spunta-riga"><input type="checkbox" id="ricorda" checked> Ricorda la scelta per le prossime volte</label>'}
        <div class="riga-bottoni">
          <button class="bottone primario" type="button" data-azione="conferma-abbina">Continua</button>
          <button class="bottone fantasma" type="button" data-azione="annulla">Annulla</button>
        </div>
      </section>`;
  },

  piano(d) {
    const voci = d.voci.map((v) => `
      <div class="scheda voce">
        <div class="riquadro-cifra"><div class="etichetta">già presenti</div>
          <div class="cifra ${v.presenti === null ? "ignota" : "ok"}">${v.presenti === null ? "non letto" : esc(v.presenti)}</div></div>
        <div class="riquadro-cifra"><div class="etichetta">da caricare</div>
          <div class="cifra ${v.daCaricare ? "male" : "ok"}">${esc(v.daCaricare)}</div></div>
        <div class="testo-voce"><strong>${esc(v.testo)}</strong>
          ${v.avviso ? `<br><span class="testo-errore">${esc(v.avviso)}</span>` : ""}
          ${v.futuri.length ? `<br><span class="piccolo-testo">I file dei giorni ${esc(v.futuri.join(", "))} non li carico: oggi e i giorni futuri non sono ancora chiusi.</span>` : ""}
          ${v.comunicabile ? `<label class="comunica"><input type="checkbox" class="spunta c-comunica" value="${esc(v.chiave)}" data-mese="${esc(v.mese)}" data-struttura="${esc(v.struttura)}">
            <span>Alla fine invia anche la <strong>comunicazione mensile</strong> di ${esc(v.mese)} (entro il ${esc(v.scadenza)}).
            <span class="piccolo-testo">Chiude il mese sul portale: dopo i dati non si modificano più. La invio solo se tutti i giorni risultano caricati.${flusso.prova ? " In prova arrivo fino al bottone e non lo premo." : ""}</span></span></label>` : ""}</div>
      </div>`).join("");
    const bottone = d.nienteDaFare ? "" : flusso.prova
      ? '<button class="bottone primario grande" type="button" data-azione="avvia">Avvia la prova</button>'
      : '<button class="bottone pericolo grande" type="button" data-azione="avvia-vera">Carica davvero…</button>';
    return `
      <section>
        <h1>Prima di cominciare</h1>
        <p class="intro">Ecco cosa farò. Durante il giro ricontrollo ogni giorno sul portale e salto quelli già presenti.</p>
        ${d.daHostlab ? `<div class="avviso ok st6"><span class="segno">✓</span><div>Da HostLab: <strong>${esc(d.daHostlab)}</strong>.</div></div>` : ""}
        ${d.diProva ? '<div class="avviso attenzione st6"><span class="segno">!</span><div>Sono i file inventati dello zip di prova: servono solo in modalità prova, e non li carico mai davvero.</div></div>' : ""}
        ${d.nonRiconosciuti ? `<div class="avviso attenzione st6"><span class="segno">!</span><div>${esc(d.nonRiconosciuti)} file nello zip non sono movimenti giornalieri: li ignoro.</div></div>` : ""}
        ${d.nienteDaFare ? '<div class="avviso ok st6"><span class="segno">✓</span><div>Niente da fare: i giorni di questi file risultano già tutti sul portale (o il mese è chiuso).</div></div>' : ""}
        <div class="strutture">${voci}</div>
        <div class="riga-bottoni">
          ${bottone}
          <button class="bottone fantasma" type="button" data-azione="ricomincia">Indietro</button>
        </div>
      </section>`;
  },

  esito(d) {
    const righe = d.strutture.map((s) => `
      <div class="scheda voce">
        <div class="riquadro-cifra"><div class="etichetta">${d.prova ? "da caricare" : "caricati"}</div>
          <div class="cifra ok">${esc(d.prova ? s.daCaricare : s.caricati)}</div></div>
        <div class="riquadro-cifra"><div class="etichetta">già presenti</div><div class="cifra">${esc(s.gia)}</div></div>
        <div class="testo-voce"><strong>${esc(s.nome)}</strong><br>
          ${s.saltata ? `<span class="testo-errore">${esc(s.saltata)}</span>` : ""}
          ${s.nonRiusciti.length ? `<span class="testo-errore">Non riusciti: ${esc(s.nonRiusciti.join(", "))}</span><br>` : ""}
          ${s.motivi.map((m) => `<span class="piccolo-testo">${esc(m)}</span><br>`).join("")}
          ${s.fermata ? esc(s.fermata) : s.mancanti.length ? `Manca il file di: ${esc(s.mancanti.join(", "))}` : ""}
          ${s.nonRiletto ? `<br><span class="testo-errore">${esc(s.nonRiletto)}</span>` : ""}
          ${s.comunicazione ? `<br><span class="${s.comunicazioneRiuscita ? "testo-ok" : "testo-errore"}">Comunicazione mensile: ${esc(s.comunicazione)}</span>` : ""}
          ${!s.saltata && !s.nonRiusciti.length && !s.mancanti.length && !s.comunicazione && !s.nonRiletto ? "Tutto a posto." : ""}</div>
      </div>`).join("");
    const titolo = d.fermato ? "Ti sei fermato qui" : d.prova ? "Prova finita: non ho caricato niente" : "Fatto";
    return `
      <section>
        <h1>${titolo}</h1>
        <p class="intro">${d.prova
          ? "Qui sotto c'è cosa avrei caricato. Se torna, passa alla modalità vera e rifai il giro."
          : "Ecco com'è andata. Il riepilogo si può copiare e mandare."}</p>
        <div class="strutture">${righe}</div>
        <h2 class="st8">Riepilogo</h2>
        <pre class="riepilogo st3">${esc(d.testo)}</pre>
        <div class="riga-bottoni">
          ${d.prova ? '<button class="bottone primario" type="button" data-azione="torna-piano">Torna al piano</button>' : ""}
          <button class="bottone ${d.prova ? "" : "primario"}" type="button" data-azione="ricomincia">${d.prova ? "Ricomincia" : "Fine: togli i file dal browser"}</button>
          <button class="bottone" type="button" data-azione="copia-esito">Copia tutto</button>
          <button class="bottone" type="button" data-azione="scarica-registro">Scarica il registro</button>
        </div>
      </section>`;
  },

  errore(d) {
    return `
      <section class="scheda centrato">
        <div class="icona-grande errore" aria-hidden="true">!</div>
        <h1>Mi sono fermato</h1>
        <p class="intro">${esc(d.messaggio)}</p>
        <div class="riga-bottoni st0">
          <button class="bottone primario" type="button" data-azione="ricomincia">Ricomincia</button>
          <button class="bottone fantasma" type="button" data-azione="scarica-registro">Scarica il registro</button>
        </div>
      </section>`;
  },
};

function disegnaCornice() {
  document.getElementById("versione").textContent = `v${versione}`;
  const pillola = document.getElementById("pillola");
  const fascia = document.getElementById("fascia");
  pillola.className = `pillola ${flusso.prova ? "prova" : "vera"}`;
  pillola.textContent = flusso.prova ? "Modalità prova" : "Modalità vera";
  fascia.className = `fascia ${flusso.prova ? "prova" : "vera"}`;
  const libero = !flusso.occupato || flusso.schermata === "piano";
  fascia.innerHTML = flusso.prova
    ? `<span>Modalità prova — arrivo fino a «Carica» e mi fermo. Sul portale non carico niente.</span>
       ${libero && flusso.schermata === "piano" ? '<button class="bottone piccolo" type="button" data-azione="passa-vera">Passa alla modalità vera…</button>' : ""}`
    : `<span>Modalità vera — carico davvero sul portale.</span>
       ${libero ? '<button class="bottone piccolo" type="button" data-azione="torna-prova">Torna alla modalità prova</button>' : ""}`;
}

let ultimaChiave = "";
function disegna() {
  disegnaCornice();
  // Si ridisegna solo se è cambiato qualcosa: non si perde ciò che il gestore sta scegliendo.
  const chiave = JSON.stringify([flusso.schermata, flusso.dati, flusso.prova]);
  if (chiave === ultimaChiave) return;
  ultimaChiave = chiave;
  app.innerHTML = SCHERMATE[flusso.schermata](flusso.dati);
  app.dataset.schermata = flusso.schermata;
}
flusso.ascolta = disegna;

function modale(titolo, html, bottoni) {
  const m = document.getElementById("modale");
  m.innerHTML = `<div class="scheda"><h2 id="titolo-modale">${esc(titolo)}</h2><div>${html}</div>
    <form method="dialog" class="riga-bottoni">${bottoni.map((b, i) => `<button class="bottone ${b.pericolo ? "pericolo" : b.primario ? "primario" : ""}" value="${i}" ${i === bottoni.length - 1 ? "autofocus" : ""}>${esc(b.testo)}</button>`).join("")}</form></div>`;
  m.addEventListener("close", () => {
    const b = bottoni[Number(m.returnValue)];
    m.returnValue = "";
    if (b?.fai) b.fai();
  }, { once: true });
  m.showModal();
}

const mostraErrore = (r) => {
  if (r?.errore) modale("Un momento", esc(r.errore), [{ testo: "Ho capito", primario: true }]);
};

function scarica(nome, testo, tipo = "text/plain;charset=utf-8") {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([testo], { type: tipo }));
  a.download = nome;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10000);
}

function nomeRegistro() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `istat-uploader-registro-${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}.txt`;
}

async function copia(testo, bottone) {
  await navigator.clipboard.writeText(testo);
  const prima = bottone.textContent;
  bottone.textContent = "Copiato ✓";
  setTimeout(() => { bottone.textContent = prima; }, 1600);
}

function apriDettagli() {
  const corpo = document.getElementById("dettagli-corpo");
  corpo.innerHTML = `
    <div><div class="etichetta">Registro</div>
      <p class="piccolo-testo st10">Senza dati personali: giorni, esiti e nomi dei file. Sta in memoria finché la scheda è aperta.</p>
      <div class="riga-bottoni st3">
        <button class="bottone piccolo" type="button" data-azione="scarica-registro">Scarica il registro</button>
      </div></div>
    ${registro.copie.length ? `<div><div class="etichetta">Pagine non lette</div>
      <p class="piccolo-testo st10">Copie senza dati personali, per chi sistema la lettura.</p>
      <div class="riga-bottoni st3">${registro.copie.map((c, i) => `<button class="bottone piccolo" type="button" data-azione="scarica-copia" data-copia="${i}">${esc(c.nome)}</button>`).join("")}</div></div>` : ""}
    ${flusso.ultimoRiepilogo ? `<div><div class="etichetta">Ultimo riepilogo</div><pre class="registro st10">${esc(flusso.ultimoRiepilogo)}</pre></div>` : ""}
    <div><div class="etichetta">Ultime righe del registro</div>
      <pre class="registro st10">${esc(registro.righe.slice(-200).join("\n") || "(vuoto)")}</pre></div>`;
  document.getElementById("dettagli").showModal();
}

async function prendiFile(file) {
  if (!file) return;
  if (file.size > DIMENSIONE_MASSIMA_ZIP) {
    mostraErrore({ errore: `«${file.name}» è troppo grande per essere uno zip di file ISTAT.` });
    return;
  }
  mostraErrore(await flusso.usaZip(new Uint8Array(await file.arrayBuffer()), file.name));
}

const AZIONI = {
  "scegli-zip": () => document.getElementById("scegli-file").click(),
  "sono-dentro": () => flusso.sonoDentro(),
  annulla: () => flusso.annulla(),
  "manuale-continua": () => {
    const voci = [];
    for (const r of document.querySelectorAll(".manuale-riga")) {
      const id = r.querySelector(".m-id").value.trim();
      const nome = r.querySelector(".m-nome").value.trim();
      if (!id && !nome) continue;
      if (!/^\d+$/.test(id)) {
        mostraErrore({ errore: `«${id || nome}»: il numero della struttura è fatto di sole cifre (lo trovi dopo «idStruttura=»).` });
        return;
      }
      voci.push({ id, nome: nome || `Struttura ${id}` });
    }
    if (!voci.length) mostraErrore({ errore: "Scrivi almeno il numero di una struttura." });
    else flusso.rispondi("manuale", voci);
  },
  "conferma-abbina": () => {
    const scelte = {};
    document.querySelectorAll("[data-chiave]").forEach((el) => { scelte[el.dataset.chiave] = el.querySelector(".a-scelta").value; });
    mostraErrore(flusso.confermaAbbinamenti(scelte, !!document.getElementById("ricorda")?.checked));
  },
  avvia: () => mostraErrore(flusso.avvia({ comunica: comunicazioni().map((c) => c.value) })),
  "avvia-vera": () => {
    const comunica = comunicazioni();
    const frase = comunica.length
      ? `<br><br><strong>E alla fine INVIO la comunicazione mensile</strong> di ${comunica.map((c) => `${esc(c.dataset.struttura)} (${esc(c.dataset.mese)})`).join(", ")}: dopo, quei mesi non si modificano più.`
      : "";
    const valori = comunica.map((c) => c.value);
    modale("Carico davvero?", `${esc(flusso.dati.confermaVera)}${frase}<br><br>Se un giorno è già sul portale lo salto.`, [
      { testo: "Sì, carica davvero", pericolo: true, fai: () => mostraErrore(flusso.avvia({ confermato: true, comunica: valori })) },
      { testo: "Annulla" },
    ]);
  },
  "passa-vera": () => modale("Passo alla modalità vera?",
    "In modalità vera premo «Carica» davvero, giorno per giorno.<br><br>"
    + "⚠️ Se un giorno è già sul portale lo salto. Ma se il portale lo mostra come non "
    + "caricato e lo carico, il file <strong>sostituisce</strong> quello che c'era — anche "
    + "una correzione fatta a mano.<br><br>Hai già fatto una prova su questo periodo, e l'elenco era giusto?", [
      { testo: "Sì, passa alla vera", pericolo: true, fai: () => mostraErrore(flusso.impostaProva(false, true)) },
      { testo: "Resto in prova" },
    ]),
  "torna-prova": () => mostraErrore(flusso.impostaProva(true)),
  "torna-piano": () => flusso.tornaAlPiano(),
  ricomincia: () => flusso.ricomincia(),
  "copia-esito": (el) => copia(flusso.dati.testo || "", el),
  "scarica-registro": () => scarica(nomeRegistro(), `${registro.testo()}\n`),
  "scarica-copia": (el) => {
    const c = registro.copie[Number(el.dataset.copia)];
    if (c) scarica(c.nome, c.html, "text/html;charset=utf-8");
  },
};

const comunicazioni = () => [...document.querySelectorAll(".c-comunica:checked")];

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-azione]");
  if (!el || !AZIONI[el.dataset.azione]) return;
  e.preventDefault();
  AZIONI[el.dataset.azione](el);
});
document.getElementById("apri-dettagli").addEventListener("click", apriDettagli);
document.getElementById("scegli-file").addEventListener("change", (e) => {
  prendiFile(e.target.files[0]);
  e.target.value = "";
});

// Il trascinamento: su tutta la pagina, così uno zip che cade a lato non apre il file.
let profondita = 0;
document.addEventListener("dragenter", (e) => {
  e.preventDefault();
  profondita += 1;
  document.body.classList.add("trascino");
});
document.addEventListener("dragover", (e) => e.preventDefault());
document.addEventListener("dragleave", () => {
  profondita -= 1;
  if (profondita <= 0) {
    profondita = 0;
    document.body.classList.remove("trascino");
  }
});
document.addEventListener("drop", (e) => {
  e.preventDefault();
  profondita = 0;
  document.body.classList.remove("trascino");
  if (flusso.schermata === "benvenuto") prendiFile(e.dataTransfer.files[0]);
});

window.addEventListener("beforeunload", (e) => {
  if (flusso.occupato) e.preventDefault();
});

chrome.runtime.onMessage.addListener((m, _mittente, rispondi) => {
  if (m?.tipo !== "gettone") return false;
  rispondi(gettoneValido(m.gettone) ? flusso.usaGettone(m.gettone) : { ok: false });
  return false;
});

disegna();

// Il gettone arrivato con l'apertura della scheda: si toglie subito dall'indirizzo.
const arrivo = /^#gettone=(.+)$/.exec(location.hash);
if (arrivo) {
  history.replaceState(null, "", location.pathname);
  if (gettoneValido(arrivo[1])) flusso.usaGettone(arrivo[1]);
}

