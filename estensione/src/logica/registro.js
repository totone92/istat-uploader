// Il registro: in memoria finché la scheda è aperta, si scarica con un clic.
// Del file si scrive il nome, che dichiara una data, mai il contenuto; ogni riga
// passa comunque dal filtro di codici fiscali, email, telefoni e token.

import { ripulisciRiga } from "./lettura.js";

const MAX_RIGHE = 5000;
const MAX_COPIE = 5;

export class Registro {
  constructor(ora = () => new Date()) {
    this.ora = ora;
    this.righe = [];
    this.copie = [];
  }

  scrivi(livello, testo) {
    const d = this.ora();
    const p = (n) => String(n).padStart(2, "0");
    const q = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
    this.righe.push(`${q} | ${livello.padEnd(7)} | ${ripulisciRiga(testo)}`);
    if (this.righe.length > MAX_RIGHE) this.righe.shift();
  }

  info(testo) { this.scrivi("INFO", testo); }

  avviso(testo) { this.scrivi("WARNING", testo); }

  /** Una copia ripulita della pagina non letta: si scarica da «Dettagli». */
  copia(nome, html) {
    this.copie.push({ nome, html });
    if (this.copie.length > MAX_COPIE) this.copie.shift();
  }

  giorno(id, giorno, esito, file, errore) {
    const riga = `struttura=${id} giorno=${giorno} esito=${esito} file=${file || "-"}${errore ? ` errore=${errore}` : ""}`;
    if (esito === "non_riuscito") this.avviso(riga);
    else this.info(riga);
  }

  testo() { return this.righe.join("\n"); }
}
