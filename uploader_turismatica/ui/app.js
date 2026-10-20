/* Istat Uploader — l'interfaccia.
 *
 * Non decide niente: chiede lo stato a Python (api.stato(), ogni 400 ms) e
 * ridisegna la schermata quando cambia. Ogni gesto è una chiamata a un metodo
 * di api.Api. Tutto il testo che arriva da fuori passa da esc().
 */
"use strict";

const app = document.getElementById("app");
let api = null;
let ultimaRev = -1;
let stato = null;
let modaleAperta = false;

const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const giorni = (n) => (n === 1 ? "1 giorno" : `${n} giorni`);

function elencoGiorni(lista) {
  if (!lista.length) return "";
  if (lista.length > 6) return `dal ${lista[0]} al ${lista[lista.length - 1]}`;
  if (lista.length === 1) return String(lista[0]);
  return `${lista.slice(0, -1).join(", ")} e ${lista[lista.length - 1]}`;
}

/* ─── collegamento con Python ─────────────────────────────────────── */

function pronto() {
  api = window.pywebview.api;
  ciclo();
}

if (window.pywebview && window.pywebview.api) pronto();
else window.addEventListener("pywebviewready", pronto, { once: true });

async function ciclo() {
  try {
    const s = await api.stato();
    window.__ui_pronto = true;
    if (s.rev !== ultimaRev || (stato && s.prova !== stato.prova)) {
      ultimaRev = s.rev;
      stato = s;
      disegna();
    } else {
      stato = s;
      aggiornaVerifica();
    }
  } catch (e) {
    console.error(e);
  }
  setTimeout(ciclo, 400);
}

async function chiama(metodo, ...argomenti) {
  const r = await api[metodo](...argomenti);
  if (r && r.errore) mostraModale("Un momento", esc(r.errore), [{ testo: "Ho capito", primario: true }]);
  return r;
}

/* ─── cornice: pillola, fascia, versione ──────────────────────────── */

const CON_FASCIA = new Set(["principale", "abbina", "piano", "lavoro", "esito"]);

function disegnaCornice() {
  document.getElementById("versione").textContent = `v${stato.versione}`;
  const pillola = document.getElementById("pillola");
  const fascia = document.getElementById("fascia");
  const configurata = !["benvenuto", "spid", "quante", "manuale", "riepilogo"].includes(stato.schermata)
    || (stato.schermata === "spid" && stato.dati.perche === "carica");
  pillola.hidden = !configurata;
  pillola.className = `pillola ${stato.prova ? "prova" : "vera"}`;
  pillola.textContent = stato.prova ? "Modalità prova" : "Modalità vera";

  fascia.hidden = !CON_FASCIA.has(stato.schermata);
  fascia.className = `fascia ${stato.prova ? "prova" : "vera"}`;
  const libero = !stato.occupato;
  fascia.innerHTML = stato.prova
    ? `<span>Modalità prova — arrivo fino a «Carica» e mi fermo. Sul portale non carico niente.</span>
       ${libero ? '<button class="bottone piccolo" data-azione="passa-vera">Passa alla modalità vera…</button>' : ""}`
    : `<span>Modalità vera — carico davvero sul portale.</span>
       ${libero ? '<button class="bottone piccolo" data-azione="torna-prova">Torna alla modalità prova</button>' : ""}`;
}

/* ─── schermate ───────────────────────────────────────────────────── */

const SCHERMATE = {
  benvenuto() {
    return `
      <section class="scheda eroe">
        <h1>Carica i movimenti ISTAT su Turismatica, senza farli a mano</h1>
        <p class="intro">Prima colleghiamo il programma al portale: entri con il tuo SPID o la CIE,
          e io leggo quali strutture gestisci e quali giorni hanno già il movimento.</p>
        <ol class="passi">
          <li><span class="numero">1</span><div><strong>Entri su Turismatica</strong><br>
            <span class="piccolo-testo">Si apre Chrome: accedi con SPID o CIE, come fai sempre.</span></div></li>
          <li><span class="numero">2</span><div><strong>Leggo le tue strutture</strong><br>
            <span class="piccolo-testo">Solo lettura: guardo l'elenco e i giorni già caricati. Non premo niente.</span></div></li>
          <li><span class="numero">3</span><div><strong>Controlli e confermi</strong><br>
            <span class="piccolo-testo">Ti mostro cosa ho trovato. Salvo solo dopo il tuo OK.</span></div></li>
        </ol>
        <div class="riga-bottoni">
          <button class="bottone primario grande" data-azione="collega">Collega Turismatica</button>
        </div>
        <p class="rassicura">🔒 Le credenziali le inserisci tu nel browser: il programma non le vede e non le salva.</p>
      </section>`;
  },

  spid(d) {
    if (d.fase === "apro") {
      return `<section class="scheda centrato"><span class="rotella"></span>
        <h2 style="margin-top:18px">Apro Chrome sul portale…</h2>
        <p class="intro">La prima volta può volerci qualche secondo in più.</p></section>`;
    }
    const cosa = d.perche === "carica"
      ? "Appena sei dentro comincio, giorno per giorno."
      : "Appena sei dentro leggo le tue strutture. Solo lettura.";
    return `
      <section class="scheda centrato">
        <div class="icona-grande">🔑</div>
        <h1>Entra con SPID o CIE</h1>
        <p class="intro">Vai sulla finestra di Chrome che si è aperta, premi «Accedi» ed entra come fai
          sempre. Prenditi il tempo che ti serve: non c'è nessuna scadenza. ${cosa}</p>
        <div class="riga-bottoni" style="justify-content:center">
          <button class="bottone primario grande" data-azione="sono-dentro">Sono dentro: vai</button>
          <button class="bottone fantasma" data-azione="annulla">Annulla</button>
        </div>
        <p class="piccolo-testo" style="margin-top:14px">Se mi accorgo da solo che sei entrato, proseguo senza aspettare il bottone.</p>
      </section>`;
  },

  lavoro(d) {
    const barra = d.totale
      ? `<div class="barra"><span style="width:${Math.round((100 * (d.passo || 0)) / d.totale)}%"></span></div>
         <p class="piccolo-testo">${esc(d.passo || 0)} di ${esc(d.totale)}</p>`
      : "";
    return `
      <section class="scheda centrato">
        <span class="rotella"></span>
        <h2 style="margin-top:18px">${esc(d.titolo)}</h2>
        <p class="intro">${esc(d.dettaglio || "")}</p>
        ${barra}
        <p class="piccolo-testo" style="margin-top:12px">Non toccare la finestra di Chrome mentre lavoro.</p>
        <div class="riga-bottoni" style="justify-content:center">
          <button class="bottone fantasma" data-azione="annulla">Fermati</button>
        </div>
      </section>`;
  },

  quante(d) {
    const n = d.trovate.length;
    const elenco = d.trovate.map((s) => `<span class="chip">${esc(s.nome || s.id)}</span>`).join("");
    const opzione = (valore, titolo, testo) => `
      <label class="opzione">
        <input type="radio" name="quante" value="${valore}" ${d.proposta === valore ? "checked" : ""}>
        <div class="titolo-opzione">${titolo}${d.proposta === valore ? '<span class="distintivo">proposta</span>' : ""}</div>
        <div class="piccolo-testo">${testo}</div>
      </label>`;
    return `
      <section class="scheda">
        <h1>${n === 1 ? "Ho trovato una struttura" : `Ho trovato ${n} strutture`}</h1>
        <p class="intro">Sono quelle legate al tuo accesso su Turismatica.</p>
        <div style="margin-top:12px">${elenco}</div>
        <h2 style="margin-top:28px">Gestisci una struttura o più strutture?</h2>
        <div class="opzioni">
          ${opzione("una", "Una struttura", "Nel prossimo passo scegli quale.")}
          ${opzione("piu", "Più strutture", "Le tengo tutte; puoi togliere quelle che non gestisci.")}
        </div>
        <div class="riga-bottoni">
          <button class="bottone primario" data-azione="rispondi-quante">Continua</button>
          <button class="bottone fantasma" data-azione="annulla">Annulla</button>
        </div>
      </section>`;
  },

  manuale(d) {
    const riga = () => `
      <div class="manuale-riga">
        <input type="text" class="m-id" inputmode="numeric" placeholder="Numero, es. 12345">
        <input type="text" class="m-nome" placeholder="Nome della struttura (facoltativo)">
      </div>`;
    return `
      <section class="scheda">
        <h1>Dimmi tu le tue strutture</h1>
        <div class="avviso attenzione" style="margin-top:16px"><span class="segno">!</span><div>${esc(d.messaggio)}</div></div>
        <div class="manuale-righe" id="manuale-righe">${riga()}${riga()}</div>
        <div class="riga-bottoni">
          <button class="bottone fantasma piccolo" data-azione="manuale-aggiungi">+ Un'altra struttura</button>
        </div>
        <div class="riga-bottoni">
          <button class="bottone primario" data-azione="manuale-continua">Continua</button>
          <button class="bottone fantasma" data-azione="annulla">Annulla</button>
          ${d.copia ? '<button class="bottone fantasma spinta" data-azione="apri-registro">Apri la cartella della copia</button>' : ""}
        </div>
      </section>`;
  },

  riepilogo(d) {
    const una = d.quante === "una";
    const schede = d.strutture.map((s, i) => schedaStruttura(s, {
      spunta: una ? "radio" : "checkbox", scelta: una ? i === 0 : true,
    })).join("");
    return `
      <section>
        <h1>${d.aggiornamento ? "Le tue strutture, aggiornate" : "Ecco cosa ho trovato"}</h1>
        <p class="intro">${una
          ? "Scegli la struttura che gestisci con questo programma."
          : "Togli la spunta alle strutture che non vuoi gestire da qui."}
          Salvo solo quando premi <strong>Conferma</strong>.</p>
        ${d.manuale ? '<div class="avviso attenzione" style="margin-top:14px"><span class="segno">!</span><div>Le hai inserite a mano: se un numero fosse sbagliato, qui sotto lo vedi dal messaggio sulla struttura.</div></div>' : ""}
        <div class="strutture">${schede}</div>
        ${legenda()}
        <div class="riga-bottoni">
          <button class="bottone primario grande" data-azione="conferma-strutture">Conferma</button>
          <button class="bottone fantasma" data-azione="annulla-riepilogo">Annulla</button>
        </div>
      </section>`;
  },

  principale(d) {
    const avviso = d.avviso
      ? `<div class="avviso ${esc(d.tipo_avviso)}" style="margin-bottom:18px"><span class="segno">${d.tipo_avviso === "errore" ? "!" : "i"}</span><div>${esc(d.avviso)}</div></div>`
      : "";
    return `
      <section>
        ${avviso}
        <div style="display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap">
          <div><h1>${d.strutture.length === 1 ? "La tua struttura" : "Le tue strutture"}</h1>
            <p class="piccolo-testo" style="margin-top:4px">${d.aggiornata_il ? `Stato letto sul portale il ${esc(d.aggiornata_il)}` : ""}</p></div>
          <button class="bottone piccolo" data-azione="collega">Aggiorna le mie strutture</button>
        </div>
        <div class="zona-zip" id="zona-zip">
          <h2>Trascina qui lo zip dei file ISTAT</h2>
          <p class="piccolo-testo">Quello del mese, scaricato dal tuo gestionale. Riconosco da solo di quale struttura sono i file.</p>
          <div class="riga-bottoni" style="justify-content:center;margin-top:16px">
            <button class="bottone primario" data-azione="scegli-zip">Scegli il file…</button>
          </div>
        </div>
        <div class="strutture">${d.strutture.map((s) => schedaStruttura(s, {})).join("")}</div>
        ${legenda()}
      </section>`;
  },

  abbina(d) {
    const gruppi = d.gruppi.map((g) => `
      <div class="scheda" data-chiave="${esc(g.chiave)}">
        <div class="etichetta">${g.di_prova ? "File di prova" : "File da abbinare"}</div>
        <h3 style="margin-top:6px">«${esc(g.nome_nel_file)}»${g.codice ? ` <span class="distintivo">codice ${esc(g.codice)}</span>` : ""}</h3>
        <p class="piccolo-testo" style="margin-top:4px">${giorni(g.giorni)} · ${esc(g.mesi)}</p>
        ${g.domanda ? `<p style="margin-top:12px">${esc(g.domanda)}</p>` : ""}
        <label class="campo"><span class="etichetta">Struttura</span>
          <select class="a-scelta">
            <option value="">Non caricare questi file</option>
            ${g.proposte.map((p) => `<option value="${esc(p.id)}" ${p.id === g.scelta ? "selected" : ""}>${esc(p.nome)} (n° ${esc(p.id)})</option>`).join("")}
          </select>
        </label>
      </div>`).join("");
    const soloProva = d.gruppi.every((g) => g.di_prova);
    return `
      <section>
        <h1>Di quale struttura sono questi file?</h1>
        <p class="intro">Non lo indovino: quando dai file non è chiaro, chiedo a te.</p>
        <div class="strutture">${gruppi}</div>
        ${soloProva ? "" : '<label class="spunta-riga"><input type="checkbox" id="ricorda" checked> Ricorda la scelta per le prossime volte</label>'}
        <div class="riga-bottoni">
          <button class="bottone primario" data-azione="conferma-abbina">Continua</button>
          <button class="bottone fantasma" data-azione="indietro">Indietro</button>
        </div>
      </section>`;
  },

  piano(d) {
    const voci = d.voci.map((v) => `
      <div class="scheda voce">
        <div class="riquadro-cifra"><div class="etichetta">già presenti</div>
          <div class="cifra ${v.presenti === null ? "ignota" : "ok"}">${v.presenti === null ? "non letto" : esc(v.presenti)}</div></div>
        <div class="riquadro-cifra"><div class="etichetta">da caricare</div>
          <div class="cifra ${v.da_caricare ? "male" : "ok"}">${esc(v.da_caricare)}</div></div>
        <div class="testo-voce"><strong style="color:var(--testo)">${esc(v.testo)}</strong>${v.letto_il ? ` <span class="piccolo-testo">(stato letto il ${esc(v.letto_il)})</span>` : ""}
          ${v.futuri.length ? `<br><span class="piccolo-testo">I file dei giorni ${esc(elencoGiorni(v.futuri))} non li carico: oggi e i giorni futuri non sono ancora chiusi.</span>` : ""}
          ${v.comunicabile ? `<label class="comunica"><input type="checkbox" class="spunta c-comunica" value="${esc(v.chiave)}" data-mese="${esc(v.mese)}" data-struttura="${esc(v.struttura)}">
            <span>Alla fine invia anche la <strong>comunicazione mensile</strong> di ${esc(v.mese)} (entro il ${esc(v.scadenza)}).
            <span class="piccolo-testo">Chiude il mese sul portale: dopo i dati non si modificano più. La invio solo se tutti i giorni risultano caricati.${stato.prova ? " In prova arrivo fino al bottone e non lo premo." : ""}</span></span></label>` : ""}</div>
      </div>`).join("");
    const bottone = d.niente_da_fare
      ? ""
      : stato.prova
        ? '<button class="bottone primario grande" data-azione="avvia">Avvia la prova</button>'
        : '<button class="bottone pericolo grande" data-azione="avvia-vera">Carica davvero…</button>';
    return `
      <section>
        <h1>Prima di cominciare</h1>
        <p class="intro">Ecco cosa farò. Durante il giro ricontrollo ogni giorno sul portale e salto quelli già presenti.</p>
        ${d.di_prova ? '<div class="avviso attenzione" style="margin-top:16px"><span class="segno">!</span><div>Sono i file inventati dello zip di prova: servono solo in modalità prova, e non li carico mai davvero.</div></div>' : ""}
        ${d.niente_da_fare ? '<div class="avviso ok" style="margin-top:16px"><span class="segno">✓</span><div>Niente da fare: i giorni di questi file risultano già tutti sul portale (o il mese è chiuso).</div></div>' : ""}
        <div class="strutture">${voci}</div>
        <div class="riga-bottoni">
          ${bottone}
          <button class="bottone fantasma" data-azione="indietro">Indietro</button>
        </div>
      </section>`;
  },

  esito(d) {
    const righe = d.strutture.map((s) => `
      <div class="scheda voce">
        <div class="riquadro-cifra"><div class="etichetta">${d.prova ? "da caricare" : "caricati"}</div>
          <div class="cifra ok">${esc(d.prova ? s.da_caricare : s.caricati)}</div></div>
        <div class="riquadro-cifra"><div class="etichetta">già presenti</div><div class="cifra">${esc(s.gia)}</div></div>
        <div class="testo-voce"><strong style="color:var(--testo)">${esc(s.nome)}</strong><br>
          ${s.saltata ? `<span style="color:var(--errore)">${esc(s.saltata)}</span>` : ""}
          ${s.non_riusciti.length ? `<span style="color:var(--errore)">Non riusciti: ${esc(s.non_riusciti.join(", "))}</span><br>` : ""}
          ${s.mancanti.length ? `Manca il file di: ${esc(s.mancanti.join(", "))}` : ""}
          ${s.comunicazione ? `<br><span style="color:var(${s.comunicazione_riuscita ? "--ok" : "--errore"})">Comunicazione mensile: ${esc(s.comunicazione)}</span>` : ""}
          ${!s.saltata && !s.non_riusciti.length && !s.mancanti.length && !s.comunicazione ? "Tutto a posto." : ""}</div>
      </div>`).join("");
    return `
      <section>
        <h1>${d.prova ? "Prova finita: non ho caricato niente" : "Fatto"}</h1>
        <p class="intro">${d.prova
          ? "Qui sotto c'è cosa avrei caricato. Se torna, passa alla modalità vera e rifai il giro."
          : "Ecco com'è andata. Il riepilogo si può copiare e mandare."}</p>
        <div class="strutture">${righe}</div>
        <h2 style="margin-top:26px">Riepilogo</h2>
        <pre class="riepilogo" style="margin-top:10px">${esc(d.testo)}</pre>
        <div class="riga-bottoni">
          <button class="bottone primario" data-azione="torna">Torna alle strutture</button>
          <button class="bottone" data-azione="copia-esito">Copia tutto</button>
        </div>
      </section>`;
  },

  errore(d) {
    return `
      <section class="scheda centrato">
        <div class="icona-grande" style="background:var(--errore-tenue);color:var(--errore)">!</div>
        <h1>Mi sono fermato</h1>
        <p class="intro">${esc(d.messaggio)}</p>
        <div class="riga-bottoni" style="justify-content:center">
          <button class="bottone primario" data-azione="${d.ha_configurazione ? "torna" : "collega"}">${d.ha_configurazione ? "Torna alle strutture" : "Riprova"}</button>
          <button class="bottone fantasma" data-azione="apri-dettagli">Apri i dettagli</button>
        </div>
      </section>`;
  },
};

function schedaStruttura(s, { spunta, scelta }) {
  const meta = [s.comune, s.tipologia, `n° ${s.id}`, s.cin ? `CIN ${s.cin}` : ""].filter(Boolean).map(esc).join(" · ");
  const input = spunta
    ? `<input class="spunta" type="${spunta}" name="struttura" value="${esc(s.id)}" ${scelta ? "checked" : ""}>`
    : "";
  return `
    <div class="scheda struttura">
      <label class="struttura-testa">${input}
        <div><div class="struttura-nome">${esc(s.nome)}</div>
          <div class="struttura-meta">${meta}${s.manuale ? " · inserita a mano" : ""}</div></div>
      </label>
      ${s.avviso ? `<div class="avviso attenzione"><span class="segno">!</span><div>${esc(s.avviso)}</div></div>` : ""}
      <div class="mesi">${s.mesi.map(schedaMese).join("")}</div>
    </div>`;
}

function schedaMese(m) {
  let cifra;
  const comunicazione = {
    comunicato: '<div class="piccolo-testo comunicato">✓ comunicazione mensile fatta (mese chiuso)</div>',
    da_comunicare: `<div class="piccolo-testo da-comunicare">Comunicazione mensile da fare, entro il ${esc(m.scadenza)}</div>`,
    scaduta: `<div class="piccolo-testo da-comunicare">Comunicazione mensile non risulta fatta (scadeva il ${esc(m.scadenza)})</div>`,
  }[m.comunicazione] || "";
  if (!m.letto) cifra = '<div class="cifra ignota">Non letto</div>';
  else if (m.comunicazione === "comunicato" && !m.caricati) cifra = '<div class="cifra ok">✓<small>chiuso</small></div>';
  else if (m.mancanti.length) cifra = `<div class="cifra male">${m.mancanti.length}<small>${m.mancanti.length === 1 ? "giorno manca" : "giorni mancano"}</small></div>`;
  else cifra = '<div class="cifra ok">✓<small>tutto caricato</small></div>';
  const celle = m.giorni.map((g) => `<span class="giorno ${esc(g.s)}" title="${esc(g.g)}"></span>`).join("");
  return `
    <div class="mese">
      <div class="mese-testa"><span class="mese-nome">${esc(m.etichetta)}</span>
        <span class="piccolo-testo">${m.letto ? `${esc(m.caricati)} caricati` : ""}</span></div>
      ${cifra}
      ${m.mancanti.length && m.mancanti.length <= 6 ? `<div class="piccolo-testo">Mancano: ${esc(elencoGiorni(m.mancanti))}</div>` : ""}
      ${comunicazione}
      <div class="calendario">${celle}</div>
    </div>`;
}

function comunicazioniScelte() {
  return [...document.querySelectorAll(".c-comunica:checked")];
}

function legenda() {
  return `<div class="legenda">
    <span><i style="background:var(--giorno-caricato)"></i>caricato</span>
    <span><i style="background:var(--giorno-mancante)"></i>manca</span>
    <span><i style="background:var(--giorno-chiuso)"></i>manca, il portale non lo apre ancora</span>
    <span><i style="background:var(--giorno-vuoto)"></i>non letto</span>
    <span><i style="border:1px dashed var(--bordo)"></i>oggi e dopo</span></div>`;
}

function disegna() {
  disegnaCornice();
  const fn = SCHERMATE[stato.schermata] || SCHERMATE.benvenuto;
  app.innerHTML = fn(stato.dati || {});
  if (!modaleAperta) app.scrollTop = 0;
  aggiornaVerifica();
}

/* ─── gesti ───────────────────────────────────────────────────────── */

const AZIONI = {
  "collega": () => chiama("collega"),
  "sono-dentro": () => api.sono_dentro(),
  "annulla": () => api.annulla(),
  "rispondi-quante": () => {
    const scelta = document.querySelector('input[name="quante"]:checked');
    chiama("rispondi_quante", scelta ? scelta.value : "");
  },
  "manuale-aggiungi": () => {
    const contenitore = document.getElementById("manuale-righe");
    contenitore.insertAdjacentHTML("beforeend", contenitore.firstElementChild.outerHTML);
    contenitore.lastElementChild.querySelectorAll("input").forEach((i) => { i.value = ""; });
  },
  "manuale-continua": () => {
    const voci = [...document.querySelectorAll(".manuale-riga")].map((r) => ({
      id: r.querySelector(".m-id").value, nome: r.querySelector(".m-nome").value,
    }));
    chiama("inserisci_a_mano", voci);
  },
  "conferma-strutture": () => {
    const ids = [...document.querySelectorAll('input[name="struttura"]:checked')].map((i) => i.value);
    chiama("conferma_strutture", ids);
  },
  "annulla-riepilogo": () => api.annulla().then(() => api.torna_alla_principale()),
  "scegli-zip": () => chiama("scegli_zip"),
  "conferma-abbina": () => {
    const scelte = {};
    document.querySelectorAll("[data-chiave]").forEach((el) => {
      scelte[el.dataset.chiave] = el.querySelector(".a-scelta").value;
    });
    const ricorda = document.getElementById("ricorda");
    chiama("conferma_abbinamenti", scelte, !!(ricorda && ricorda.checked));
  },
  "indietro": () => api.torna_alla_principale(),
  "torna": () => api.torna_alla_principale(),
  "avvia": () => chiama("avvia", false, comunicazioniScelte().map((c) => c.value)),
  "avvia-vera": () => {
    const comunica = comunicazioniScelte();
    const frase = comunica.length
      ? "<br><br><strong>E alla fine INVIO la comunicazione mensile</strong> di " +
        comunica.map((c) => `${esc(c.dataset.struttura)} (${esc(c.dataset.mese)})`).join(", ") +
        ": dopo, quei mesi non si modificano più."
      : "";
    mostraModale(
      "Carico davvero?",
      `${esc(stato.dati.conferma_vera)}${frase}<br><br>Se un giorno è già sul portale lo salto.`,
      [{ testo: "Sì, carica davvero", pericolo: true, fai: () => chiama("avvia", true, comunica.map((c) => c.value)) },
       { testo: "Annulla" }],
    );
  },
  "passa-vera": () => mostraModale(
    "Passo alla modalità vera?",
    "In modalità vera premo «Carica» davvero, giorno per giorno.<br><br>" +
    "⚠️ Se un giorno è già sul portale lo salto. Ma se il portale lo mostra come non " +
    "caricato e lo carico, il file <strong>sostituisce</strong> quello che c'era — anche " +
    "una correzione fatta a mano.<br><br>Hai già fatto una prova su questo periodo, e l'elenco era giusto?",
    [{ testo: "Sì, passa alla vera", pericolo: true, fai: () => chiama("imposta_prova", false, true) },
     { testo: "Resto in prova" }],
  ),
  "torna-prova": () => chiama("imposta_prova", true, false),
  "apri-dettagli": () => apriDettagli(),
  "apri-registro": () => api.apri_cartella_registro(),
  "copia-esito": (el) => copia(stato.dati.testo || "", el),
  "verifica": () => api.verifica_computer(),
};

document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-azione]");
  if (!el || !AZIONI[el.dataset.azione]) return;
  e.preventDefault();
  AZIONI[el.dataset.azione](el);
});
document.getElementById("apri-dettagli").addEventListener("click", () => apriDettagli());
document.getElementById("chiudi-dettagli").addEventListener("click", () => chiudiDettagli());
document.getElementById("velo").addEventListener("click", () => chiudiDettagli());

/* trascinamento: solo l'evidenza visiva. Il file lo riceve Python, che ne
   conosce il percorso vero (finestra.py). */
let profondita = 0;
document.addEventListener("dragenter", () => { profondita++; document.body.classList.add("trascino"); });
document.addEventListener("dragleave", () => { if (--profondita <= 0) { profondita = 0; document.body.classList.remove("trascino"); } });
document.addEventListener("drop", () => { profondita = 0; document.body.classList.remove("trascino"); });

/* ─── modale, dettagli, copia ─────────────────────────────────────── */

function mostraModale(titolo, html, bottoni) {
  const m = document.getElementById("modale");
  m.innerHTML = `<div class="scheda"><h2>${esc(titolo)}</h2><div>${html}</div>
    <div class="riga-bottoni">${bottoni.map((b, i) => `<button class="bottone ${b.pericolo ? "pericolo" : b.primario ? "primario" : ""}" data-b="${i}">${esc(b.testo)}</button>`).join("")}</div></div>`;
  m.hidden = false;
  modaleAperta = true;
  m.querySelectorAll("[data-b]").forEach((el) => el.addEventListener("click", () => {
    m.hidden = true;
    modaleAperta = false;
    const b = bottoni[Number(el.dataset.b)];
    if (b.fai) b.fai();
  }));
  m.querySelector("[data-b]").focus();
}

async function apriDettagli() {
  const d = await api.dettagli();
  const corpo = document.getElementById("dettagli-corpo");
  corpo.innerHTML = `
    <div><div class="etichetta">Registro</div>
      <p class="percorso" style="margin-top:6px">${esc(d.registro || "non disponibile")}</p>
      <div class="riga-bottoni" style="margin-top:10px">
        <button class="bottone piccolo" data-azione="apri-registro">Apri la cartella</button>
        <button class="bottone piccolo" id="copia-tutto">Copia tutto</button>
      </div></div>
    <div><div class="etichetta">Computer</div>
      <div class="riga-bottoni" style="margin-top:10px"><button class="bottone piccolo" data-azione="verifica">Verifica il computer</button></div>
      <pre class="registro" id="verifica-testo" hidden></pre></div>
    ${d.riepilogo ? `<div><div class="etichetta">Ultimo riepilogo</div><pre class="registro" style="margin-top:6px">${esc(d.riepilogo)}</pre></div>` : ""}
    <div><div class="etichetta">Ultime righe del registro</div>
      <pre class="registro" style="margin-top:6px">${esc(d.righe.join("\n") || "(vuoto)")}</pre></div>`;
  document.getElementById("copia-tutto").addEventListener("click", (e) =>
    copia(`${d.riepilogo ? `${d.riepilogo}\n\n` : ""}${d.righe.join("\n")}`, e.currentTarget));
  document.getElementById("velo").hidden = false;
  document.getElementById("dettagli").hidden = false;
  aggiornaVerifica();
}

function chiudiDettagli() {
  document.getElementById("velo").hidden = true;
  document.getElementById("dettagli").hidden = true;
}

function aggiornaVerifica() {
  const pre = document.getElementById("verifica-testo");
  if (!pre || !stato) return;
  const v = stato.verifica || {};
  pre.hidden = !v.in_corso && !v.testo;
  pre.textContent = v.in_corso ? "Controllo in corso… (Chrome si apre e si chiude da solo)" : (v.testo || "");
}

async function copia(testo, bottone) {
  try {
    await navigator.clipboard.writeText(testo);
  } catch (_) {
    const t = document.createElement("textarea");
    t.value = testo;
    document.body.appendChild(t);
    t.select();
    document.execCommand("copy");
    t.remove();
  }
  if (bottone) {
    const prima = bottone.textContent;
    bottone.textContent = "Copiato ✓";
    setTimeout(() => { bottone.textContent = prima; }, 1600);
  }
}
