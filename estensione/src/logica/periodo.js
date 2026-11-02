// Giorni e mesi come date di calendario: «2026-10-03», mai un istante con un fuso.

export const MESI = [
  "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
  "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
];

const due = (n) => String(n).padStart(2, "0");

export const iso = (anno, mese, giorno) => `${anno}-${due(mese)}-${due(giorno)}`;

export function parti(giorno) {
  const [a, m, g] = giorno.split("-").map(Number);
  return { anno: a, mese: m, giorno: g };
}

/** L'ultimo giorno del mese (numero). */
export const fineMese = (anno, mese) => new Date(Date.UTC(anno, mese, 0)).getUTCDate();

/** Una data di calendario vera? `data` può sforare, e questo lo scopre. */
export function valida(anno, mese, giorno) {
  if (mese < 1 || mese > 12 || giorno < 1) return false;
  return anno >= 1 && giorno <= fineMese(anno, mese);
}

export const ddmmaaaa = (g) => {
  const p = parti(g);
  return `${due(p.giorno)}/${due(p.mese)}/${p.anno}`;
};

export const ddmm = (g) => {
  const p = parti(g);
  return `${due(p.giorno)}/${due(p.mese)}`;
};

export const etichettaMese = (anno, mese) => `${MESI[mese - 1]} ${anno}`;

/** Tutti i giorni fra due estremi inclusi, dello stesso mese o no. */
export function giorniFra(dal, al) {
  const out = [];
  const a = parti(dal);
  let t = Date.UTC(a.anno, a.mese - 1, a.giorno);
  const b = parti(al);
  const fine = Date.UTC(b.anno, b.mese - 1, b.giorno);
  while (t <= fine) {
    const d = new Date(t);
    out.push(iso(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate()));
    t += 86400000;
  }
  return out;
}

/** Oggi dove sta il PC: è il giorno che conta per il gestore, non quello UTC. */
export function oggiLocale(adesso = new Date()) {
  return iso(adesso.getFullYear(), adesso.getMonth() + 1, adesso.getDate());
}
