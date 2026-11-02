// Apre la scheda dell'estensione: dall'icona, o col gettone arrivato da HostLab.
// Niente stato qui: il service worker può morire in ogni momento, e il lavoro sta tutto
// nella scheda. Il gettone arriva solo dal ponte, e il ponte gira solo su HostLab.

const PAGINA = "carica.html";
const SERVER_HOSTLAB = "https://hostlab.umbriaround.it";
const FORMA_GETTONE = /^\d{1,12}\.[A-Za-z0-9_-]{32,64}$/;

async function schedaAperta() {
  const [c] = await chrome.runtime.getContexts({
    contextTypes: ["TAB"], documentUrls: [chrome.runtime.getURL(PAGINA)],
  });
  return c ?? null;
}

async function apri(gettone, vicino) {
  const aperta = await schedaAperta();
  if (aperta) {
    const risposta = gettone
      ? await chrome.runtime.sendMessage({ tipo: "gettone", gettone }).catch(() => ({ ok: false }))
      : { ok: true };
    await chrome.tabs.update(aperta.tabId, { active: true });
    await chrome.windows.update(aperta.windowId, { focused: true }).catch(() => {});
    return risposta;
  }
  const url = chrome.runtime.getURL(PAGINA) + (gettone ? `#gettone=${gettone}` : "");
  // Accanto alla scheda di partenza se si può: la posizione non vale un'apertura mancata.
  try {
    await chrome.tabs.create({ url, ...(vicino ? { index: vicino.index + 1, windowId: vicino.windowId } : {}) });
  } catch {
    await chrome.tabs.create({ url });
  }
  return { ok: true };
}

chrome.action.onClicked.addListener((tab) => {
  apri(null, tab).catch((e) => console.error(e));
});

chrome.runtime.onMessage.addListener((messaggio, mittente, rispondi) => {
  if (messaggio?.tipo !== "carica") return false;
  if (mittente.id !== chrome.runtime.id || mittente.origin !== SERVER_HOSTLAB
    || !FORMA_GETTONE.test(messaggio.gettone ?? "")) {
    rispondi({ ok: false, errore: "non valido" });
    return false;
  }
  (async () => {
    try {
      rispondi(await apri(messaggio.gettone, mittente.tab));
    } catch (e) {
      console.error(e);
      rispondi({ ok: false, errore: "non aperta" });
    }
  })();
  return true;
});
