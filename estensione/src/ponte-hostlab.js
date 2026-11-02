// Il ponte con HostLab, solo su quella pagina. Dice che l'estensione c'è (un attributo su
// <html>, così HostLab non deve sapere il suo id, diverso fra Chrome, Edge e prove) e passa
// il gettone al service worker. Non legge niente della pagina.

document.documentElement.dataset.istatUploader = chrome.runtime.getManifest().version;

window.addEventListener("message", async (evento) => {
  if (evento.source !== window || evento.origin !== location.origin) return;
  const { tipo, gettone } = evento.data ?? {};
  if (tipo !== "istat-uploader:carica") return;
  let risposta;
  try {
    risposta = await chrome.runtime.sendMessage({ tipo: "carica", gettone });
  } catch {
    risposta = { ok: false, errore: "non raggiungibile" };
  }
  window.postMessage({ tipo: "istat-uploader:risposta", ...risposta }, location.origin);
});
