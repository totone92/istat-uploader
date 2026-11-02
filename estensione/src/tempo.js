// Le pause del giro. Mentre lavora, in primo piano c'è la scheda del portale e questa
// è nascosta: Chrome rallenta i timer delle schede nascoste fino a uno al minuto. Un
// worker dedicato non subisce questo limite, e con otto strutture la differenza è il giro.

let lavoratore = null;
let prossimo = 0;
const attese = new Map();

function avvia() {
  lavoratore = new Worker(new URL("./timer.js", import.meta.url));
  lavoratore.addEventListener("message", ({ data }) => {
    attese.get(data)?.();
    attese.delete(data);
  });
}

export function dormi(ms) {
  if (typeof Worker === "undefined") return new Promise((fatto) => { setTimeout(fatto, ms); });
  if (!lavoratore) avvia();
  return new Promise((fatto) => {
    prossimo += 1;
    attese.set(prossimo, fatto);
    lavoratore.postMessage({ id: prossimo, ms });
  });
}
