"""Un portale finto, servito a un Chrome vero.

Le copie delle pagine del portale (``fixtures/turismatica``) servite da un
piccolo server su ``127.0.0.1``, **con il JavaScript di PrimeFaces 6.2**
(``fixtures/primefaces-6.2``), a un Chrome headless guidato da Selenium. Così
selettori, ``execute_script`` e ``page_source`` sono quelli di Chrome, e la
lettura vede la pagina **dopo** il JavaScript — com'è sul PC del gestore.

Il ``DriverFinto`` restituisce l'HTML che gli si dà; questo no: è il motivo per
cui la v1.3.1 è passata dai test e si è fermata sul portale vero.

Cosa fa il server:

* ``prehome.xhtml`` → la copia vera; il POST di «Accedi» (``PrimeFaces.ab``)
  ricorda la struttura scelta e risponde con un ``redirect`` ajax a una
  ``home.xhtml`` senza tabella — come potrebbe fare il portale;
* ``movimentoospiti.xhtml?idStruttura=N`` → la copia vera con il numero N, ma
  con ``diretta=False`` solo se N è la struttura scelta in prehome (altrimenti
  la home); con ``mai_tabella`` sempre la home;
* le risorse PrimeFaces, per nome del file; tutto il resto 404.

⚠️ **Nessuna rete**: Chrome risolve solo ``127.0.0.1`` (``--host-resolver-rules``),
e i link assoluti al portale nelle copie sono riscritti verso il server locale.

Chrome si trova con Selenium Manager, come nell'app; ``CHROMEDRIVER`` nell'ambiente
indica un driver già installato (su Linux: ``/snap/bin/chromium.chromedriver``).
Senza Chrome i test si saltano — **tranne** con ``CHROME_OBBLIGATORIO=1``, che il
giro di GitHub imposta: lì un Chrome che non parte è un fallimento.
"""
from __future__ import annotations

import os
import re
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

FIXTURE = Path(__file__).parent / "fixtures"
PRIMEFACES = FIXTURE / "primefaces-6.2"
_PREHOME = (FIXTURE / "turismatica" / "prehome.html").read_text(encoding="utf-8")
_MOVIMENTI = (FIXTURE / "turismatica" / "movimenti.html").read_text(encoding="utf-8")
_HOME = ("<!DOCTYPE html><html><head><title>Turismatica Online</title></head>"
         "<body><h1>Pagina iniziale del portale</h1></body></html>")
_PORTALE = "https://turismatica.regione.umbria.it"


class PortaleLocale:
    def __init__(self) -> None:
        self.diretta = True
        self.mai_tabella = False
        self.scelta = ""
        self.richieste: list[str] = []
        portale = self

        class Gestore(BaseHTTPRequestHandler):
            def log_message(self, *_: object) -> None:
                pass

            def do_GET(self) -> None:
                portale.richieste.append(f"GET {self.path}")
                self._rispondi(*portale.get(self.path))

            def do_POST(self) -> None:
                corpo = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
                portale.richieste.append(f"POST {self.path}")
                self._rispondi(*portale.post(self.path, corpo))

            def _rispondi(self, stato: int, tipo: str, corpo: bytes) -> None:
                self.send_response(stato)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Gestore)
        self.base = f"http://127.0.0.1:{self._server.server_address[1]}"
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def prehome_url(self) -> str:
        return f"{self.base}/ntojsf/private/prehome.xhtml"

    @property
    def movimenti_url(self) -> str:
        return f"{self.base}/ntojsf/private/OSR/movimento/movimentoospiti.xhtml?idStruttura={{}}"

    def _pagina(self, html: str) -> tuple[int, str, bytes]:
        return 200, "text/html; charset=UTF-8", html.replace(_PORTALE, self.base).encode()

    def get(self, percorso: str) -> tuple[int, str, bytes]:
        u = urlparse(percorso)
        nome = u.path.rsplit("/", 1)[-1]
        if nome.endswith(".js.xhtml"):
            js = PRIMEFACES / nome.removesuffix(".xhtml")
            if js.is_file():
                return 200, "application/javascript", js.read_bytes()
            return 404, "text/plain", b""
        if nome == "prehome.xhtml":
            return self._pagina(_PREHOME)
        if nome == "movimentoospiti.xhtml":
            ident = parse_qs(u.query).get("idStruttura", [""])[0]
            if self.mai_tabella or not (self.diretta or ident == self.scelta):
                return self._pagina(_HOME)
            return self._pagina(movimenti_di(ident))
        if nome == "home.xhtml":
            return self._pagina(_HOME)
        return 404, "text/plain", b""

    def post(self, percorso: str, corpo: str) -> tuple[int, str, bytes]:
        if urlparse(percorso).path.endswith("prehome.xhtml"):
            scelta = parse_qs(corpo).get("j_idt6:j_idt10_input", [""])[0]
            self.scelta = scelta
            xml = ('<?xml version="1.0" encoding="UTF-8"?><partial-response>'
                   '<redirect url="/ntojsf/private/home.xhtml"></redirect></partial-response>')
            return 200, "text/xml; charset=UTF-8", xml.encode()
        return 404, "text/plain", b""

    def chiudi(self) -> None:
        self._server.shutdown()


def movimenti_di(id_turismatica: str) -> str:
    return _MOVIMENTI.replace("12345", id_turismatica.zfill(5))


def apri_chrome_di_prova() -> webdriver.Chrome:
    opzioni = webdriver.ChromeOptions()
    for a in ("--headless=new", "--no-sandbox", "--disable-gpu", "--window-size=1600,1000",
              "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE 127.0.0.1"):
        opzioni.add_argument(a)
    percorso = os.environ.get("CHROMEDRIVER")
    servizio = Service(percorso) if percorso else Service()
    return webdriver.Chrome(service=servizio, options=opzioni)


@pytest.fixture(scope="session")
def chrome() -> Iterator[webdriver.Chrome]:
    try:
        driver = apri_chrome_di_prova()
    except WebDriverException as exc:
        motivo = f"Chrome non si apre: {str(exc).splitlines()[0][:200]}"
        if os.environ.get("CHROME_OBBLIGATORIO") == "1":
            pytest.fail(motivo)
        pytest.skip(motivo)
    yield driver
    driver.quit()


@pytest.fixture
def portale(monkeypatch: pytest.MonkeyPatch) -> Iterator[PortaleLocale]:
    """Il server locale, con gli indirizzi del portale dell'app puntati su di lui."""
    from uploader_turismatica import portale as modulo_portale
    from uploader_turismatica import sessione as modulo_sessione

    p = PortaleLocale()
    monkeypatch.setattr(modulo_portale, "PREHOME_URL", p.prehome_url)
    monkeypatch.setattr(modulo_portale, "MOVIMENTI_URL", p.movimenti_url)
    monkeypatch.setattr(modulo_sessione, "PREHOME_URL", p.prehome_url)
    yield p
    p.chiudi()


def etichette_reflow(html: str) -> list[str]:
    """Le etichette che PrimeFaces ha messo nelle celle della tabella dei
    movimenti: la prova che il JavaScript è girato davvero."""
    i = html.find('id="movimentiTabView:tblMovimenti_data"')
    if i < 0:
        return []
    corpo = html[i:html.find("</tbody>", i)]
    return re.findall(r'<span class="ui-column-title">([^<]*)</span>', corpo)
