"""La finestra: pywebview con l'interfaccia HTML di ``ui/``, servita in locale.

Su Windows pywebview usa **WebView2**, il motore di Edge già presente su
Windows 10 e 11. ⚠️ Se WebView2 manca, pywebview **ripiega in silenzio** su
MSHTML (il motore di Internet Explorer), dove questa interfaccia si
romperebbe senza dire niente. Due difese:

* prima di aprire, si guarda nel registro di Windows se WebView2 c'è
  (le stesse chiavi che controlla pywebview); se manca, un messaggio di
  Windows dice cosa fare e apre la pagina per installarlo;
* all'avvio, se il motore scelto non è ``edgechromium``, la finestra non parte
  (``events.initialized`` che restituisce ``False``) e si dice la stessa cosa.

Il trascinamento dello zip passa dagli eventi DOM di pywebview, che danno il
**percorso vero** del file (``pywebviewFullPath``): dal JavaScript di una
pagina il percorso non si vede.
"""
from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from collections.abc import Callable, Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from uploader_turismatica import __version__, configurazione, registro
from uploader_turismatica.api import Api
from uploader_turismatica.sessione import SessioneSelenium

log = logging.getLogger(__name__)

UI = Path(__file__).resolve().parent / "ui"
URL_WEBVIEW2 = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
MESSAGGIO_WEBVIEW2 = (
    "Per mostrare la sua finestra, Istat Uploader usa «Microsoft Edge WebView2», "
    "un componente di Windows che su questo computer non c'è.\n\n"
    "Ti apro la pagina di Microsoft da cui installarlo (è gratuito, ci vuole un "
    "minuto): scegli «Evergreen Bootstrapper», installalo e riapri il programma.\n\n"
    + URL_WEBVIEW2
)
_CHIAVI_WEBVIEW2 = (
    "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",   # runtime
    "{2CD8A007-E189-409D-A2C8-9AF4EF3C72AA}",   # beta
    "{0D50BFEC-CD6A-4F9A-964C-C7416E3ACB10}",   # dev
    "{65C35B14-6C1D-4122-AC46-7148CC9D6497}",   # canary
)
VERSIONE_MINIMA = (86, 0, 622, 0)


def versione_sufficiente(versioni: Iterable[str]) -> bool:
    """Almeno una versione di WebView2 ≥ 86.0.622.0 (come pretende pywebview)."""
    for v in versioni:
        try:
            numeri = tuple(int(x) for x in v.strip().split("."))
        except ValueError:
            continue
        if numeri and numeri != (0,) and numeri >= VERSIONE_MINIMA[: len(numeri)]:
            return True
    return False


def _versioni_dal_registro() -> list[str]:
    import winreg  # solo Windows

    trovate: list[str] = []
    for chiave in _CHIAVI_WEBVIEW2:
        for radice, percorso in (
            (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{chiave}"),
            (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{chiave}"),
            (winreg.HKEY_CURRENT_USER, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{chiave}"),
        ):
            try:
                with winreg.OpenKey(radice, percorso) as k:
                    valore, _ = winreg.QueryValueEx(k, "pv")
                    trovate.append(str(valore))
            except OSError:
                continue
    return trovate


def webview2_presente(versioni: Callable[[], list[str]] | None = None) -> bool | None:
    """``True``/``False`` su Windows, ``None`` altrove (lì non serve)."""
    if not sys.platform.startswith("win") and versioni is None:
        return None
    try:
        return versione_sufficiente((versioni or _versioni_dal_registro)())
    except Exception:  # noqa: BLE001 — un registro illeggibile non è un «sì»
        log.exception("lettura del registro di WebView2")
        return False


def _avviso_nativo(titolo: str, testo: str) -> None:
    """Un messaggio di Windows, senza bisogno della finestra (che non c'è)."""
    if sys.platform.startswith("win"):
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, testo, titolo, 0x30)  # MB_ICONWARNING
    else:
        print(f"{titolo}\n\n{testo}", file=sys.stderr)


def _manca_webview2() -> int:
    log.error("WebView2 assente: la finestra non si apre")
    _avviso_nativo("Istat Uploader — manca un componente", MESSAGGIO_WEBVIEW2)
    with contextlib.suppress(Exception):
        webbrowser.open(URL_WEBVIEW2)
    return 2


def apri_cartella(cartella: Path) -> None:
    with contextlib.suppress(Exception):
        if sys.platform.startswith("win"):
            os.startfile(cartella)
        else:
            subprocess.Popen(["xdg-open", str(cartella)])


def _controlla_motore(esito: dict[str, Any]) -> Callable[[str], bool]:
    def al_via(renderer: str) -> bool:
        esito["renderer"] = renderer
        log.info("motore della finestra: %s", renderer)
        if sys.platform.startswith("win") and renderer != "edgechromium":
            esito["motore_sbagliato"] = True
            return False
        return True

    return al_via


def _collega_trascinamento(finestra: Any, api: Api) -> None:
    from webview.dom import DOMEventHandler

    def su_drop(evento: dict[str, Any]) -> None:
        file = (evento.get("dataTransfer") or {}).get("files") or []
        percorsi = [f.get("pywebviewFullPath") for f in file if f.get("pywebviewFullPath")]
        if percorsi:
            log.info("zip trascinato: %s", Path(percorsi[0]).name)
            api.usa_zip(percorsi[0])

    def niente(_evento: dict[str, Any]) -> None:
        return None

    doc = finestra.dom.document
    doc.events.dragover += DOMEventHandler(niente, True, True, debounce=500)
    doc.events.drop += DOMEventHandler(su_drop, True, True)


def _crea_api(percorso_registro: Path | None, finestra_ref: dict[str, Any]) -> Api:
    import webview

    def scegli_file() -> str | None:
        f = finestra_ref.get("finestra")
        if f is None:
            return None
        scelti = f.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=("Zip dei file ISTAT (*.zip)", "Tutti i file (*.*)"),
        )
        return scelti[0] if scelti else None

    from uploader_turismatica.diagnostica import rapporto

    cartella_copie = percorso_registro.parent if percorso_registro else (
        configurazione.percorso_file().parent
    )
    return Api(
        portale=lambda: SessioneSelenium(cartella_copie, datetime.now),
        percorso_configurazione=configurazione.percorso_file(),
        percorso_registro=percorso_registro,
        oggi=date.today,
        ora=datetime.now,
        scegli_file=scegli_file,
        apri_cartella=apri_cartella,
        rapporto_computer=rapporto,
    )


def avvia() -> int:
    percorso = registro.configura()
    log.info("avvio | versione=%s", __version__)
    if webview2_presente() is False:
        return _manca_webview2()

    import webview

    finestra_ref: dict[str, Any] = {}
    api = _crea_api(percorso, finestra_ref)
    finestra = webview.create_window(
        f"Istat Uploader {__version__}", url=str(UI / "index.html"), js_api=api,
        width=1120, height=800, min_size=(900, 640), background_color="#F5F6F8",
        text_select=True,
    )
    assert finestra is not None
    finestra_ref["finestra"] = finestra
    esito: dict[str, Any] = {}
    finestra.events.initialized += _controlla_motore(esito)
    collegato = threading.Event()

    def al_caricamento() -> None:
        if not collegato.is_set():
            collegato.set()
            _collega_trascinamento(finestra, api)

    finestra.events.loaded += al_caricamento
    webview.start(private_mode=True)
    if esito.get("motore_sbagliato"):
        return _manca_webview2()
    log.info("chiuso")
    return 0


def autoverifica_finestra(destinazione: Path, attesa_s: float = 60.0) -> int:
    """Per la build: apre la finestra **vera** con l'interfaccia vera, aspetta
    che il JavaScript abbia parlato col Python (``window.__ui_pronto``, messo
    da ``app.js`` dopo la prima risposta di ``api.stato()``) e la chiude.
    Scrive l'esito in ``destinazione``; 0 = la finestra funziona."""
    import webview

    esito: dict[str, Any] = {"ok": False, "dettaglio": "nessuna risposta dalla finestra"}
    cartella = Path(tempfile.mkdtemp(prefix="istat-av-"))
    api = Api(
        portale=lambda: SessioneSelenium(cartella, datetime.now),
        percorso_configurazione=cartella / "configurazione.json",
        percorso_registro=None, oggi=date.today, ora=datetime.now,
    )
    finestra = webview.create_window("Istat Uploader — autoverifica",
                                     url=str(UI / "index.html"), js_api=api)
    assert finestra is not None
    finestra.events.initialized += _controlla_motore(esito)

    def controlla() -> None:
        fine = time.monotonic() + attesa_s
        while time.monotonic() < fine:
            with contextlib.suppress(Exception):
                if finestra.evaluate_js("window.__ui_pronto === true"):
                    titolo = finestra.evaluate_js("document.querySelector('h1') ? "
                                                  "document.querySelector('h1').innerText : ''")
                    esito.update(ok=True, dettaglio=f"interfaccia pronta: «{titolo}»")
                    break
            time.sleep(0.5)
        finestra.destroy()

    finestra.events.loaded += lambda: threading.Thread(target=controlla, daemon=True).start()
    webview.start(private_mode=True)
    if esito.get("motore_sbagliato"):
        esito.update(ok=False, dettaglio=f"motore {esito.get('renderer')}: WebView2 assente")
    testo = (f"Istat Uploader v{__version__} — autoverifica della finestra\n"
             f"motore: {esito.get('renderer', '?')}\n"
             f"{'✓' if esito['ok'] else '✗'} {esito['dettaglio']}\n")
    destinazione.write_text(testo, encoding="utf-8")
    return 0 if esito["ok"] else 1
