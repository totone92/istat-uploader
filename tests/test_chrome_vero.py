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
import time
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


def test_apri_movimenti_passando_da_prehome(
    chrome: WebDriver, portale: PortaleLocale, tmp_path: Path, caplog: pytest.LogCaptureFixture,
) -> None:
    """Il portale apre la tabella solo per la struttura scelta in prehome, e
    dopo «Accedi» atterra su una sua home: si sceglie con la tendina vera, si
    preme «Accedi» (POST di PrimeFaces) e solo allora si apre l'indirizzo."""
    portale.diretta = False
    with caplog.at_level(logging.INFO):
        problema = apri_movimenti(chrome, "12343", strutture_note=STRUTTURE,
                                  copie=Copie(tmp_path, lambda: ORA))
    assert problema is None
    assert portale.scelta == "12343"
    assert "POST /ntojsf/private/prehome.xhtml" in portale.richieste
    prima = portale.richieste[:portale.richieste.index("POST /ntojsf/private/prehome.xhtml")]
    assert not any("movimentoospiti" in r for r in prima)
    assert list(tmp_path.iterdir()) == []
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
    assert [p.name for p in tmp_path.iterdir()] == ["pagina-movimenti-12340-20261020-151000.html"]
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


# ─── la sessione scaduta e la conferma, in Chrome ────────────────────────────


def test_il_ritorno_al_login_si_riconosce_e_una_pagina_vera_no(
    chrome: WebDriver, portale: PortaleLocale, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(modulo_portale, "ATTESA_USCITA_S", 0.0)
    chrome.get(portale.movimenti_url.format("12345"))
    assert not modulo_portale.sessione_scaduta(chrome)
    chrome.get(portale.prehome_url)
    assert not modulo_portale.sessione_scaduta(chrome)
    portale.scaduta = True
    chrome.get(portale.movimenti_url.format("12345"))       # redirect al login
    assert "/public/" in chrome.current_url
    assert modulo_portale.sessione_scaduta(chrome)
    pause: list[bool] = []

    def rientra() -> None:
        pause.append(True)
        portale.scaduta = False

    assert modulo_portale.rientra_se_uscito(chrome, rientra) and pause == [True]
    chrome.get(portale.movimenti_url.format("12345"))
    assert not modulo_portale.sessione_scaduta(chrome)


def test_i_segni_si_leggono_sulla_riga_vera_dopo_il_javascript(
    chrome: WebDriver, portale: PortaleLocale, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from selenium.webdriver.support.ui import WebDriverWait

    monkeypatch.setattr(modulo_portale, "ATTESA_CONFERMA_S", 0.5)
    chrome.get(portale.movimenti_url.format("12345"))
    passi = modulo_portale._PassiSelenium(chrome, WebDriverWait(chrome, 1))
    assert not passi.caricato(OTTOBRE)
    chrome.execute_script(
        "const r = document.querySelector('#movimentiTabView\\\\:tblMovimenti_data tr');"
        "const s = document.createElement('span'); s.title = 'File caricato: x.txt';"
        "r.cells[1].appendChild(s);"
    )
    assert passi.caricato(OTTOBRE)


# ─── la fascia della versione nuova, nell'interfaccia vera ───────────────────


def _apri_interfaccia(chrome: WebDriver, nuova: str, schermata: str = "benvenuto",
                      dati: str = "{}") -> None:
    from uploader_turismatica.finestra import UI

    finto = f"""
      window.__aperture = 0;
      window.pywebview = {{api: {{
        stato: async () => ({{rev: 1, schermata: {schermata!r}, dati: {dati}, prova: true,
          versione: '1.4.0', occupato: false, verifica: {{in_corso: false, testo: ''}},
          nuova_versione: {nuova!r}}}),
        apri_nuova_versione: async () => {{ window.__aperture += 1; }},
      }}}};"""
    comando = chrome.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": finto})
    try:
        chrome.get((UI / "index.html").as_uri())
        for _ in range(40):
            if chrome.execute_script("return window.__ui_pronto === true"):
                break
            time.sleep(0.1)
        time.sleep(0.2)
    finally:
        chrome.execute_cdp_cmd("Page.removeScriptToEvaluateOnNewDocument",
                               {"identifier": comando["identifier"]})


def test_la_fascia_compare_col_link_e_non_scarica_niente(chrome: WebDriver) -> None:
    _apri_interfaccia(chrome, "9.9.9")
    fascia = chrome.find_element("id", "nuova-versione")
    assert fascia.is_displayed() and "C'è una versione nuova" in fascia.text
    fascia.find_element("tag name", "a").click()
    time.sleep(0.2)
    assert chrome.execute_script("return window.__aperture") == 1


def test_senza_versione_nuova_la_fascia_non_c_e(chrome: WebDriver) -> None:
    _apri_interfaccia(chrome, "")
    assert not chrome.find_element("id", "nuova-versione").is_displayed()


def test_la_schermata_di_rientro_dice_che_il_giro_e_in_pausa(chrome: WebDriver) -> None:
    _apri_interfaccia(chrome, "", "spid", "{perche: 'scaduta', fase: 'aspetto'}")
    testo = chrome.find_element("id", "app").text
    assert "Il portale ti ha fatto uscire" in testo and "riprendo dal giorno" in testo
