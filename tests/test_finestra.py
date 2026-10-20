"""La finestra: WebView2 c'è? e l'interfaccia è tutta locale?"""
from __future__ import annotations

import re

import pytest

from uploader_turismatica.finestra import UI, versione_sufficiente, webview2_presente


@pytest.mark.parametrize(("versioni", "atteso"), [
    (["130.0.2849.80"], True),
    (["86.0.622.0"], True),
    (["86.0.621.9"], False),
    (["0.0.0.0"], False),
    ([], False),
    (["boh", "120.0.1"], True),
])
def test_versione_minima_di_webview2(versioni: list[str], atteso: bool) -> None:
    assert versione_sufficiente(versioni) is atteso


def test_registro_illeggibile_non_e_un_si() -> None:
    def rotto() -> list[str]:
        raise OSError("accesso negato")

    assert webview2_presente(rotto) is False
    assert webview2_presente(lambda: ["130.0.0.0"]) is True


def test_l_interfaccia_c_e() -> None:
    for nome in ("index.html", "app.css", "app.js"):
        assert (UI / nome).is_file()


def test_nessuna_risorsa_esterna() -> None:
    """Funziona offline: niente CDN, niente font scaricati, niente script da
    fuori. (Gli unici indirizzi sono quelli scritti per il gestore.)"""
    html = (UI / "index.html").read_text(encoding="utf-8")
    css = (UI / "app.css").read_text(encoding="utf-8")
    js = (UI / "app.js").read_text(encoding="utf-8")
    assert not re.search(r'(src|href)="(https?:)?//', html)
    assert "@import" not in css and not re.search(r"url\(\s*['\"]?(https?:)?//", css)
    assert not re.search(r"\bfetch\(|XMLHttpRequest|import\s*\(", js)


def test_l_interfaccia_segnala_quando_e_pronta() -> None:
    """``window.__ui_pronto`` è ciò che l'autoverifica della build aspetta."""
    assert "window.__ui_pronto = true" in (UI / "app.js").read_text(encoding="utf-8")
