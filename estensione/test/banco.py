"""Il banco di prova: finto Turismatica e finto HostLab sui loro nomi veri.

Un solo server HTTPS su 127.0.0.1, e Chromium che ci manda i due domini del manifest
(``--host-resolver-rules``): così si prova l'estensione **così com'è**, con i permessi e gli
indirizzi scritti nel suo codice, senza interruttori di prova. Ogni altro nome non si risolve.

Turismatica sono le copie vere (``tests/fixtures/turismatica``) con PrimeFaces 6.2 vero; le
risposte del server JSF sono **scritte da noi** come le abbiamo capite: è il limite del banco.

    python estensione/test/banco.py    # acceso a mano, per guardarci col server MCP
"""
from __future__ import annotations

import io
import json
import re
import ssl
import subprocess
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RADICE = Path(__file__).resolve().parents[2]
ESTENSIONE = RADICE / "estensione"
FIXTURE = RADICE / "tests" / "fixtures"
PRIMEFACES = FIXTURE / "primefaces-6.2"
DIST = RADICE / "dist" / "banco"
PORTA = 18443
TURISMATICA = "turismatica.regione.umbria.it"
HOSTLAB = "hostlab.umbriaround.it"
STRUTTURE = {"12345": "TENANT A", "12341": "TENANT B", "12340": "TENANT C"}
SOSTITUZIONI = ("CASA LAVANDA", "Casa Lavanda")
ARGOMENTI_CHROMIUM = [
    f"--host-resolver-rules=MAP {TURISMATICA} 127.0.0.1:{PORTA}, MAP {HOSTLAB} 127.0.0.1:{PORTA}, "
    "MAP * ~NOTFOUND, EXCLUDE 127.0.0.1",
    "--ignore-certificate-errors",
    "--no-sandbox",
]
GETTONE_BUONO = "7." + "a" * 43


def contenuto_giorno(nome: str, giorno: int) -> bytes:
    """Un file inventato. La «è» in cp1252 serve a vedere se i byte arrivano intatti."""
    return (nome.ljust(255).encode("cp1252") + f"\r\n\r\nGiorno {giorno} è inventato\r\n".encode("cp1252"))


def zip_del_mese(nome: str = "TENANT A", codice: str = "IT054039B403012345", dal: int = 1, al: int = 31) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for g in range(dal, al + 1):
            z.writestr(f"cartella/schedine_istat_{codice}_202610{g:02d}.txt", contenuto_giorno(nome, g))
    return buf.getvalue()


def _pagina_portale() -> dict[str, str]:
    html = (FIXTURE / "turismatica" / "movimenti.html").read_text(encoding="utf-8")
    i = html.index('id="movimentiTabView:tblMovimenti_data"')
    apertura = html.index(">", i) + 1
    chiusura = html.index("</tbody>", apertura)
    righe = re.findall(r'<tr data-ri=.*?</tr>', html[apertura:chiusura], re.S)
    return {
        "html": html, "apertura": str(apertura), "chiusura": str(chiusura),
        "aperta": righe[0], "chiusa": righe[1],
    }


_P = _pagina_portale()
_PREHOME = (FIXTURE / "turismatica" / "prehome.html").read_text(encoding="utf-8")


def _riga(modello: str, indice: int, giorno: int, mese: int = 10, anno: int = 2026) -> str:
    # Il numero di riga nei modelli è 0 per l'aperta e 1 per la chiusa.
    r = re.sub(r"tblMovimenti:\d+:", f"tblMovimenti:{indice}:", modello)
    r = re.sub(r"tblMovimenti_\d+_", f"tblMovimenti_{indice}_", r)
    r = re.sub(r'data-ri="\d+"', f'data-ri="{indice}"', r)
    return re.sub(r"\d\d/\d\d/\d{4}", f"{giorno:02d}/{mese:02d}/{anno}", r, count=1)


def _riga_caricata(indice: int, giorno: int, file: str) -> str:
    r = _riga(_P["aperta"], indice, giorno)
    valori = iter(("3", "1", "1", "3", "2"))
    r = re.sub(r'(<td role="gridcell" class="textRight">)[^<]*(</td>)',
               lambda m: f"{m[1]}{next(valori)}{m[2]}", r)
    # Via la doppia freccia, dentro l'icona del documento e la scritta del portale.
    r = re.sub(r'<button[^>]*title="nessun nuovo movimento.*?</button>(<script.*?</script>)?', "", r, flags=re.S)
    icona = (f'<button type="button" title="File caricato: {file}" class="ui-button">'
             '<span class="fa fa-file-text-o"></span></button>')
    return r.replace("</tr>", f'<td role="gridcell">{icona}</td></tr>')


class Banco:
    def __init__(self) -> None:
        self.dentro = False
        self.scelta = ""
        #: id → {giorno → nome file} già sul portale, per ottobre 2026.
        self.caricati: dict[str, dict[int, str]] = {i: {} for i in STRUTTURE}
        self.chiusi: set[str] = set()
        self.apertura_dialog: int | None = None
        #: Quanti caricamenti reggere prima di far scadere la sessione.
        self.scade_dopo: int | None = None
        self.caricamenti: list[dict[str, object]] = []
        self.ritiri: list[dict[str, object]] = []
        self.richieste: list[tuple[str, str, str]] = []
        self.gettoni: set[str] = set()
        self.pacchetto = zip_del_mese()
        self._server: ThreadingHTTPServer | None = None

    # ── ciclo di vita ───────────────────────────────────────────────

    def accendi(self) -> None:
        DIST.mkdir(parents=True, exist_ok=True)
        cert = DIST / "banco.pem"
        if not cert.exists():
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "3650",
                "-keyout", cert, "-out", cert, "-subj", "/CN=banco-di-prova",
                "-addext", f"subjectAltName=DNS:{TURISMATICA},DNS:{HOSTLAB}",
            ], check=True, capture_output=True)
        banco = self

        class Gestore(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_: object) -> None:
                pass

            def _rispondi(self, stato: int, tipo: str, corpo: bytes, intest: dict[str, str] | None = None) -> None:
                self.send_response(stato)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                for k, v in (intest or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(corpo)

            def _gira(self, metodo: str) -> None:
                host = (self.headers.get("Host") or "").split(":")[0]
                banco.richieste.append((metodo, host, self.path))
                corpo = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                fn = banco.hostlab if host == HOSTLAB else banco.turismatica
                self._rispondi(*fn(metodo, self.path, self.headers, corpo))

            def do_GET(self) -> None:  # noqa: N802
                self._gira("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._gira("POST")

        contesto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        contesto.load_cert_chain(cert)
        self._server = ThreadingHTTPServer(("127.0.0.1", PORTA), Gestore)
        self._server.socket = contesto.wrap_socket(self._server.socket, server_side=True)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def spegni(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()

    def azzera(self) -> None:
        self.dentro = False
        self.scelta = ""
        self.caricati = {i: {} for i in STRUTTURE}
        self.chiusi = set()
        self.scade_dopo = None
        self.caricamenti.clear()
        self.ritiri.clear()
        self.gettoni.clear()
        self.pacchetto = zip_del_mese()

    # ── HostLab ─────────────────────────────────────────────────────

    def hostlab(self, metodo: str, percorso: str, intest: object, _corpo: bytes):
        u = urlparse(percorso).path
        if u == "/turismatica/pacchetto" and metodo == "POST":
            autorizza = intest.get("Authorization", "")  # type: ignore[attr-defined]
            gettone = autorizza.removeprefix("Bearer ")
            self.ritiri.append({"gettone": gettone, "cookie": intest.get("Cookie"),  # type: ignore[attr-defined]
                                "origine": intest.get("Origin")})  # type: ignore[attr-defined]
            if gettone not in self.gettoni:
                return 410, "application/json", json.dumps({"errore": "Il gettone è scaduto: premi di nuovo."}).encode()
            self.gettoni.discard(gettone)
            return 200, "application/zip", self.pacchetto, {"X-Mese": "2026-10", "X-Struttura": "TENANT%20A"}
        if u == "/gettone" and metodo == "POST":
            n = len(self.gettoni) + len(self.ritiri) + 1
            g = f"{n}." + "b" * 43
            self.gettoni.add(g)
            return 200, "application/json", json.dumps({"gettone": g}).encode()
        if u == "/hostlab-tasto.js":
            return 200, "text/javascript", (ESTENSIONE / "docs" / "hostlab-tasto.js").read_bytes()
        if u == "/report":
            return 200, "text/html; charset=utf-8", _REPORT.encode()
        return 404, "text/plain", b"no"

    # ── Turismatica ─────────────────────────────────────────────────

    def _html(self, html: str) -> tuple[int, str, bytes]:
        return 200, "text/html; charset=UTF-8", html.encode()

    def _tabella(self, ident: str) -> str:
        if ident in self.chiusi:
            # Mese chiuso: si mostra novembre, con le frecce spente (come nel campione).
            return _riga(_P["aperta"], 0, 1, mese=11)
        presenti = self.caricati[ident]
        righe = []
        aperta_messa = False
        for g in range(1, 32):
            i = g - 1
            if g in presenti:
                righe.append(_riga_caricata(i, g, presenti[g]))
            elif not aperta_messa:
                righe.append(_riga(_P["aperta"], i, g))
                aperta_messa = True
            else:
                righe.append(_riga(_P["chiusa"], i, g))
        return "".join(righe)

    def _movimenti(self, ident: str) -> str:
        h = _P["html"]
        testa, coda = h[:int(_P["apertura"])], h[int(_P["chiusura"]):]
        pagina = testa + self._tabella(ident) + coda
        nome = STRUTTURE[ident]
        for vecchio in SOSTITUZIONI:
            pagina = pagina.replace(vecchio, nome)
        pagina = pagina.replace("12345", ident.zfill(5))
        tutti = ident not in self.chiusi and len(self.caricati[ident]) == 31
        if tutti:
            pagina = re.sub(
                r'(<button id="movimentiTabView:j_idt334"[^>]*?class="[^"]*?) ui-state-disabled("[^>]*?) disabled="disabled"',
                r"\1\2", pagina)
        return pagina

    def _parziale(self, *aggiornamenti: tuple[str, str]) -> tuple[int, str, bytes]:
        # In una risposta ajax i widget si creano subito, senza aspettare il «document ready»:
        # è ciò che lascia aperto il dialog appena aggiornato, come sul portale vero.
        def subito(c: str) -> str:
            return re.sub(r"\$\(function\(\)\{(PrimeFaces\.cw\(.*?\);)\}\);</script>", r"\1</script>", c, flags=re.S)

        pezzi = "".join(f'<update id="{i}"><![CDATA[{subito(c)}]]></update>' for i, c in aggiornamenti)
        xml = f'<?xml version="1.0" encoding="UTF-8"?><partial-response><changes>{pezzi}</changes></partial-response>'
        return 200, "text/xml; charset=UTF-8", xml.encode()

    def _blocco(self, html: str, inizio: str, fine: str) -> str:
        i = html.index(inizio)
        j = html.index(fine, i)
        return html[i:html.index("</script>", j) + len("</script>")]

    def turismatica(self, metodo: str, percorso: str, intest: object, corpo: bytes):
        u = urlparse(percorso)
        nome = u.path.rsplit("/", 1)[-1]
        if nome.endswith(".js.xhtml"):
            js = PRIMEFACES / nome.removesuffix(".xhtml")
            if js.is_file():
                return 200, "application/javascript", js.read_bytes()
            return 200, "application/javascript", b""
        if nome.endswith(".css.xhtml") or "javax.faces.resource" in u.path:
            # Del tema basta ciò che decide cosa si vede: senza, i dialog sembrerebbero già aperti.
            return 200, "text/css", b".ui-dialog,.ui-helper-hidden,.ui-overlay-hidden{display:none}"
        if nome == "login.xhtml":
            return self._html("<!DOCTYPE html><html><head><title>Accesso</title></head><body>"
                              "<h1>Turismatica Online</h1><a href='#'>Accedi con SPID</a></body></html>")
        if "/private/" in u.path and not self.dentro:
            if metodo == "GET":
                return 302, "text/html", b"", {"Location": "/ntojsf/public/login.xhtml"}
            return 200, "text/xml", (
                b'<?xml version="1.0"?><partial-response><redirect url="/ntojsf/public/login.xhtml"></redirect></partial-response>')
        if nome == "prehome.xhtml":
            if metodo == "POST":
                self.scelta = parse_qs(corpo.decode())["j_idt6:j_idt10_input"][0]
                return 200, "text/xml; charset=UTF-8", (
                    b'<?xml version="1.0" encoding="UTF-8"?><partial-response>'
                    b'<redirect url="/ntojsf/private/home.xhtml"></redirect></partial-response>')
            opzioni = "".join(f'<option value="{i}">{n}</option>' for i, n in STRUTTURE.items())
            voci = "".join(f'<li class="ui-selectonemenu-item ui-selectonemenu-list-item ui-corner-all" data-label="{n}" tabindex="-1" role="option">{n}</li>'
                           for n in STRUTTURE.values())
            h = re.sub(r"(<select id=\"j_idt6:j_idt10_input\"[^>]*>).*?(</select>)", rf"\g<1>{opzioni}\g<2>", _PREHOME, flags=re.S)
            h = re.sub(r"(<ul id=\"j_idt6:j_idt10_items\"[^>]*>).*?(</ul>)", rf"\g<1>{voci}\g<2>", h, flags=re.S)
            h = re.sub(r'(<label id="j_idt6:j_idt10_label"[^>]*>)[^<]*', r"\g<1>TENANT A", h)
            for r in ("./risorse/",):
                h = h.replace(r, "/ntojsf/javax.faces.resource/")
            return self._html(h)
        if nome == "home.xhtml":
            return self._html("<!DOCTYPE html><html><head><title>Turismatica Online</title></head>"
                              "<body><h1>Pagina iniziale del portale</h1></body></html>")
        if nome == "movimentoospiti.xhtml":
            if metodo == "GET":
                ident = parse_qs(u.query).get("idStruttura", [""])[0]
                if ident != self.scelta or ident not in STRUTTURE:
                    return self._html("<!DOCTYPE html><html><head><title>Nuova Turismatica - Error</title></head><body>Error</body></html>")
                return self._html(self._movimenti(ident))
            return self._ajax(intest, corpo)
        return 404, "text/plain", b""

    def _ajax(self, intest: object, corpo: bytes):
        tipo = intest.get("Content-Type", "")  # type: ignore[attr-defined]
        ident = self.scelta
        html = self._movimenti(ident)
        if tipo.startswith("multipart/form-data"):
            m = re.search(rb'filename="([^"]+)"\r\nContent-Type:[^\r]*\r\n\r\n(.*?)\r\n--', corpo, re.S)
            assert m, "caricamento senza file"
            nome, contenuto = m[1].decode(), m[2]
            giorno = self.apertura_dialog
            assert giorno is not None, "file senza dialog aperto"
            self.caricamenti.append({"struttura": ident, "giorno": giorno, "file": nome, "byte": contenuto})
            self.caricati[ident][giorno] = nome
            self.apertura_dialog = None
            html = self._movimenti(ident)
            risposta = self._parziale(("movimentiTabView:tblMovimenti", self._blocco(
                html, '<div id="movimentiTabView:tblMovimenti"', 'id="movimentiTabView:tblMovimenti_s"')))
            if self.scade_dopo is not None and len(self.caricamenti) >= self.scade_dopo:
                self.dentro = False
                self.scade_dopo = None
            return risposta
        c = parse_qs(corpo.decode())
        sorgente = c.get("javax.faces.source", c.get("javax.faces.partial.execute", [""]))[0]
        if "tblMovimenti:" in sorgente:
            self.apertura_dialog = int(re.search(r"tblMovimenti:(\d+):", sorgente)[1]) + 1  # type: ignore[index]
            return self._parziale(("movimentiTabView:uploadFileDialog", self._blocco(
                html, '<div id="movimentiTabView:uploadFileDialog"', 'id="movimentiTabView:uploadFileDialog_s"')))
        if sorgente == "movimentiTabView:uploadFileDialog":
            # All'apertura il dialog rifà il modulo del file (il suo behavior «open», nella pagina vera).
            i = html.index('<form id="movimentiTabView:formUploadFile"')
            return self._parziale(("movimentiTabView:formUploadFile", html[i:html.index("</form>", i) + 7]))
        if sorgente == "movimentiTabView:j_idt355":
            self.chiusi.add(ident)
            return self._parziale()
        return self._parziale()


_REPORT = """<!doctype html><html lang="it"><head><meta charset="utf-8"><title>HostLab</title></head>
<body><h1>Report ISTAT (finto)</h1><button id="tasto">Carica su Turismatica</button>
<div id="proposta" hidden>Installa l'estensione <a href="#" id="exe">o usa il programma</a></div>
<div id="avviso"></div><div id="esito"></div>
<script type="module">
import { caricaSuTurismatica } from "/hostlab-tasto.js";
const creaGettone = async () => (await (await fetch("/gettone", { method: "POST" })).json()).gettone;
document.getElementById("tasto").addEventListener("click", async () => {
  document.getElementById("esito").textContent = await caricaSuTurismatica({
    creaGettone,
    proponi() { document.getElementById("proposta").hidden = false; },
    avvisa(t) { document.getElementById("avviso").textContent = t; },
  });
});
</script></body></html>"""


if __name__ == "__main__":
    b = Banco()
    b.dentro = True
    b.accendi()
    print(f"banco acceso su 127.0.0.1:{PORTA}; Ctrl-C per spegnerlo")
    threading.Event().wait()
