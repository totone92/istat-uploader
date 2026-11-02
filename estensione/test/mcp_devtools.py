"""Un client minimo del server MCP di Chrome DevTools, via stdio.

È lo stesso server e la stessa configurazione di ``.mcp.json``, ma lo apre il test: installa,
apre e controlla l'estensione in un Chromium con un profilo dedicato, mai uno personale.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

VERSIONE_MCP = "chrome-devtools-mcp@1.12.0"


class Errore(RuntimeError):
    pass


class DevTools:
    def __init__(self, radice: Path, profilo: Path, argomenti: list[str]) -> None:
        shutil.rmtree(profilo, ignore_errors=True)
        comando = [
            "npx", "-y", VERSIONE_MCP, "--categoryExtensions", "--no-usage-statistics",
            "--headless", "--executablePath=/snap/bin/chromium", f"--userDataDir={profilo}",
            "--viewport=1280x800",
            *[f"--chromeArg={a}" for a in argomenti],
        ]
        self.radice = radice
        self.p = subprocess.Popen(comando, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True)
        self.n = 0
        self._rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {"roots": {}},
                                 "clientInfo": {"name": "prove-estensione", "version": "1"}})
        self._scrivi({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    def _scrivi(self, m: dict[str, object]) -> None:
        assert self.p.stdin is not None
        self.p.stdin.write(json.dumps(m) + "\n")
        self.p.stdin.flush()

    def _rpc(self, metodo: str, parametri: dict[str, object]) -> dict[str, object]:
        self.n += 1
        numero = self.n
        self._scrivi({"jsonrpc": "2.0", "id": numero, "method": metodo, "params": parametri})
        assert self.p.stdout is not None
        while True:
            riga = self.p.stdout.readline()
            if not riga:
                raise Errore("il server MCP si è chiuso")
            r = json.loads(riga)
            if r.get("method") == "roots/list":
                self._scrivi({"jsonrpc": "2.0", "id": r["id"], "result": {
                    "roots": [{"uri": self.radice.as_uri(), "name": "repo"}]}})
            elif r.get("id") == numero and "method" not in r:
                return r

    def chiama(self, nome: str, **argomenti: object) -> str:
        r = self._rpc("tools/call", {"name": nome, "arguments": argomenti})
        risultato = r.get("result") or {}
        testo = "\n".join(c.get("text", "") for c in risultato.get("content", []))  # type: ignore[union-attr]
        if risultato.get("isError") or "error" in r:  # type: ignore[union-attr]
            raise Errore(f"{nome}: {testo or r}")
        return testo

    def pagine(self) -> dict[int, str]:
        testo = self.chiama("list_pages")
        out = {}
        for m in re.finditer(r"^(\d+): (.+?)(?: \[selected\])?$", testo, re.M):
            tra_parentesi = re.search(r"\((chrome-extension://\S+)\)$", m[2])
            out[int(m[1])] = tra_parentesi[1] if tra_parentesi else m[2]
        return out

    def valuta(self, pagina: int, funzione: str, *args: object) -> object:
        parametri: dict[str, object] = {"pageId": pagina, "function": funzione}
        testo = self.chiama("evaluate_script", **parametri) if not args else self._con_valori(pagina, funzione, args)
        m = re.search(r"```json\n(.*?)\n```", testo, re.S)
        if m is None:
            raise Errore(f"risposta senza JSON: {testo[:400]}")
        return None if m[1].strip() == "undefined" else json.loads(m[1])

    def _con_valori(self, pagina: int, funzione: str, args: tuple[object, ...]) -> str:
        valori = ", ".join(json.dumps(a) for a in args)
        return self.chiama("evaluate_script", pageId=pagina, function=f"async () => ({funzione})({valori})")

    def aspetta(self, pagina: int, funzione: str, secondi: float = 40.0, che_cosa: str = "") -> object:
        fine = time.monotonic() + secondi
        ultimo: object = None
        while True:
            try:
                ultimo = self.valuta(pagina, funzione)
                if ultimo:
                    return ultimo
            except Errore as e:
                ultimo = str(e)
            if time.monotonic() > fine:
                raise Errore(f"non è successo: {che_cosa or funzione} (ultimo: {ultimo!r})")
            time.sleep(0.25)

    def chiudi(self) -> None:
        self.p.terminate()
        try:
            self.p.wait(10)
        except subprocess.TimeoutExpired:
            self.p.kill()
