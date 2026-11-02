// Il tasto «Carica su Turismatica» di HostLab con l'estensione. Questo è il pezzo da copiare
// nel report ISTAT: il finto HostLab delle prove serve questo stesso file, quindi è il codice
// provato. Non serve conoscere l'id dell'estensione: se c'è, il suo attributo è già su <html>.
//
//   creaGettone()   la chiamata che HostLab fa già oggi, e risponde col gettone monouso
//   proponi({ conExe }) mostra la proposta: installa l'estensione, o usa il programma
//   avvisa(testo)   un messaggio a chi ha premuto il tasto
//
// Il gettone si chiede dopo aver visto se l'estensione c'è: vale una volta e due minuti.

const ATTESA_RISPOSTA_MS = 5000;

function mandaAllEstensione(gettone) {
  return new Promise((risolvi) => {
    const fine = setTimeout(() => {
      window.removeEventListener("message", ascolta);
      risolvi({ ok: false, errore: "nessuna risposta" });
    }, ATTESA_RISPOSTA_MS);
    function ascolta(evento) {
      if (evento.source !== window || evento.origin !== location.origin) return;
      if (evento.data?.tipo !== "istat-uploader:risposta") return;
      clearTimeout(fine);
      window.removeEventListener("message", ascolta);
      risolvi(evento.data);
    }
    window.addEventListener("message", ascolta);
    window.postMessage({ tipo: "istat-uploader:carica", gettone }, location.origin);
  });
}

export function apriConExe(gettone) {
  location.href = `hostlab-turismatica://carica/${gettone}`;
}

export async function caricaSuTurismatica({ creaGettone, proponi, avvisa }) {
  if (!document.documentElement.dataset.istatUploader) {
    proponi({ conExe: async () => apriConExe(await creaGettone()) });
    return "proposta";
  }
  const gettone = await creaGettone();
  const risposta = await mandaAllEstensione(gettone);
  if (risposta.ok) return "estensione";
  if (risposta.occupato) {
    avvisa("L'estensione sta già caricando: aspetta che finisca, poi premi di nuovo.");
    return "occupata";
  }
  // Estensione disattivata a metà o in aggiornamento: il gettone è buono, vale il programma.
  proponi({ conExe: async () => apriConExe(gettone) });
  return "proposta";
}
