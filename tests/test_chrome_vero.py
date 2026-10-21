"""Le pagine del portale in un **Chrome vero**, con il loro JavaScript
(``tests/chrome_vero.py``).

⚠️ È il guasto della v1.3.1: sul PC di Marco nessuna delle otto strutture
apriva la pagina dei movimenti — «senza tabella» anche dopo la strada da
prehome. La copia della pagina era quella del server (dal HAR), e lì le celle
sono ``<td>01/10/2026</td>``; in Chrome PrimeFaces, all'avvio, ci aggiunge
l'etichetta della colonna (tabella «reflow») e la cella diventa
``Data01/10/2026``. La data non si riconosceva più, e i test col driver finto
non potevano vederlo.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

# le fixture ``chrome`` e ``portale`` arrivano da qui, via ``conftest.py``
from tests.chrome_vero import PortaleLocale, etichette_reflow, movimenti_di
from tests.driver_finto import CARTELLA
from uploader_turismatica import portale as modulo_portale
from uploader_turismatica import sessione as modulo_sessione
from uploader_turismatica.pagina_movimenti import leggi_pagina
from uploader_turismatica.portale import Copie, apri_movimenti
from uploader_turismatica.sessione import SessioneSelenium

ORA = datetime(2026, 10, 20, 15, 10)
OTTOBRE = date(2026, 10, 1)
#: Numeri inventati, mai quelli veri.
STRUTTURE = ("12340", "12341", "12342", "12343", "12344", "12345", "12346", "12347")


@pytest.fixture(autouse=True)
def _attese_brevi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_portale, "ATTESA_PAGINA_S", 4.0)
    monkeypatch.setattr(modulo_sessione, "ATTESA_ELENCO_S", 4.0)


def _apri(chrome: WebDriver, url: str) -> str:
    chrome.get(url)
    return chrome.page_source


# ─── la lettura dopo il JavaScript ───────────────────────────────────────────


def test_il_javascript_di_primefaces_gira_davvero(chrome: WebDriver, portale: PortaleLocale) -> None:
    """Senza questo, gli altri test proverebbero l'HTML del server un'altra volta."""
    html = _apri(chrome, portale.movimenti_url.format("12345"))
    assert chrome.execute_script("return !!(window.PrimeFaces && PrimeFaces.ab)")
    # il widget delle schede che ``apri_scheda`` usa per nome
    assert chrome.execute_script("return typeof PF('tabView').select") == "function"
    assert "Data" in etichette_reflow(html)


def test_la_tabella_letta_da_chrome_e_quella_del_server(chrome: WebDriver, portale: PortaleLocale) -> None:
    dal_server = leggi_pagina(movimenti_di("12345"))
    da_chrome = leggi_pagina(_apri(chrome, portale.movimenti_url.format("12345")))
    assert len(da_chrome.righe) == 20
    assert da_chrome.righe == dal_server.righe
    assert da_chrome.struttura == dal_server.struttura
    assert (da_chrome.scheda, da_chrome.schede) == (dal_server.scheda, dal_server.schede)
    assert (da_chrome.indietro, da_chrome.avanti, da_chrome.invio_mensile) == (
        dal_server.indietro, dal_server.avanti, dal_server.invio_mensile)
    assert not any(r.caricato for r in da_chrome.righe)


def test_la_copia_dopo_il_javascript_e_quella_che_chrome_produce(
    chrome: WebDriver, portale: PortaleLocale,
) -> None:
    """``movimenti-dopo-js.html`` (servita dal driver finto) resta fedele a Chrome."""
    salvata = (CARTELLA / "movimenti-dopo-js.html").read_text(encoding="utf-8")
    da_chrome = _apri(chrome, portale.movimenti_url.format("12345"))
    assert etichette_reflow(salvata) == etichette_reflow(da_chrome)
    assert leggi_pagina(salvata).righe == leggi_pagina(da_chrome).righe


# ─── i selettori ─────────────────────────────────────────────────────────────


def test_i_selettori_del_portale_valgono_in_chrome(chrome: WebDriver, portale: PortaleLocale) -> None:
    """Gli id JSF hanno i due punti: in CSS vanno scritti con l'escape. Un
    selettore sbagliato qui è ``InvalidSelectorException``, o una lista vuota."""
    _apri(chrome, portale.movimenti_url.format("12345"))
    for chi in (modulo_portale._DIALOG, modulo_portale._CAMPO_FILE, modulo_portale._CHIUDI_DIALOG):
        assert chrome.find_elements(*chi), chi
    # questi due esistono solo con un file scelto: qui conta che Chrome li accetti
    for chi in (modulo_portale._BOTTONE_CARICA, modulo_portale._ANNULLA_FILE):
        assert chrome.find_elements(*chi) == []


# ─── l'apertura della pagina dei movimenti ───────────────────────────────────


def test_apri_movimenti_con_l_indirizzo_diretto(chrome: WebDriver, portale: PortaleLocale) -> None:
    for ident in ("12345", "12347"):
        assert apri_movimenti(chrome, ident, strutture_note=STRUTTURE) is None
    assert not any(r.startswith("POST") for r in portale.richieste)


def test_apri_movimenti_passando_da_prehome(
    chrome: WebDriver, portale: PortaleLocale, tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    """Il portale apre la tabella solo per la struttura scelta in prehome, e
    dopo «Accedi» atterra su una sua home: si sceglie con la tendina vera, si
    preme «Accedi» (POST di PrimeFaces) e si riapre l'indirizzo diretto."""
    portale.diretta = False
    with caplog.at_level(logging.INFO):
        problema = apri_movimenti(chrome, "12343", strutture_note=STRUTTURE,
                                  copie=Copie(tmp_path, lambda: ORA))
    assert problema is None
    assert portale.scelta == "12343"
    assert "POST /ntojsf/private/prehome.xhtml" in portale.richieste
    # la prima strada non ha funzionato: la sua copia c'è, e il registro dice dove si era
    assert [p.name for p in tmp_path.iterdir()] == ["pagina-movimenti-12343-diretta-20261020-151000.html"]
    assert "titolo: «Turismatica Online»" in caplog.text
    assert "home.xhtml" in caplog.text


def test_se_non_si_apre_il_registro_dice_dove_si_e(
    chrome: WebDriver, portale: PortaleLocale, tmp_path: Path, caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(modulo_portale, "ATTESA_PAGINA_S", 1.0)
    portale.mai_tabella = True
    with caplog.at_level(logging.INFO):
        problema = apri_movimenti(chrome, "12340", strutture_note=STRUTTURE,
                                  copie=Copie(tmp_path, lambda: ORA))
    assert problema is not None and "12340" in problema
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "pagina-movimenti-12340-20261020-151000.html",
        "pagina-movimenti-12340-diretta-20261020-151000.html",
    ]
    assert "pagina dei movimenti di 12340 non aperta — indirizzo: http://127.0.0.1:" in caplog.text
    assert "/ntojsf/private/OSR/movimento/movimentoospiti.xhtml?idStruttura=12340" in caplog.text
    copia = (tmp_path / "pagina-movimenti-12340-20261020-151000.html").read_text(encoding="utf-8")
    assert "Pagina iniziale del portale" in copia and "copia ripulita" in copia


# ─── la sessione intera ──────────────────────────────────────────────────────


def test_la_sessione_vera_in_chrome(
    chrome: WebDriver, portale: PortaleLocale, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Strutture da prehome, poi il mese di ottobre di una di loro: le stesse
    chiamate dell'app, in Chrome."""
    monkeypatch.setattr(modulo_sessione, "apri_chrome", lambda: chrome)
    s = SessioneSelenium(tmp_path, lambda: ORA)
    s.apri()
    strutture = s.leggi_strutture()
    assert sorted(x.id_turismatica for x in strutture.strutture) == sorted(STRUTTURE)
    letti = s.leggi_mesi("12345", [OTTOBRE], strutture_note=STRUTTURE)
    assert letti.avviso == ""
    assert letti.struttura is not None and letti.struttura.id_turismatica == "12345"
    assert list(letti.mesi) == ["2026-10"]
    assert list(tmp_path.iterdir()) == []
