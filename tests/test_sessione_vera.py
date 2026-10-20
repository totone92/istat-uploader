"""Il codice vero di ``SessioneSelenium`` e ``portale.py``, con un driver
finto che serve le pagine vere del portale (``tests/driver_finto.py``).

⚠️ Sono i test che mancavano alla v1.3.0: il flusso era provato con un doppio
di ``Portale`` con la firma giusta, mentre ``SessioneSelenium.leggi_mesi``
chiamava ``apri_movimenti`` con un argomento di troppo. Qui ogni chiamata passa
dalle funzioni vere: una firma sbagliata è un ``TypeError`` nel test.
"""
from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from tests.driver_finto import SCELTA_INIZIALE, DriverFinto
from uploader_turismatica import api as api_mod
from uploader_turismatica import portale, sessione
from uploader_turismatica.api import Api
from uploader_turismatica.esito import Esito
from uploader_turismatica.periodo import Periodo
from uploader_turismatica.piano import StatoGiorno
from uploader_turismatica.sessione import SessioneSelenium
from uploader_turismatica.sorgente import sorgente_da

OGGI = date(2026, 10, 20)
ORA = datetime(2026, 10, 20, 15, 10)
OTTOBRE = date(2026, 10, 1)
SETTEMBRE = date(2026, 9, 1)


@pytest.fixture(autouse=True)
def _attese_brevi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(portale, "ATTESA_PAGINA_S", 0.2)
    monkeypatch.setattr(portale, "ATTESA_SCHEDA_S", 0.2)
    monkeypatch.setattr(portale, "PAUSA_FRA_GIORNI_S", 0.0)
    monkeypatch.setattr(portale, "ATTESA_BOTTONE_S", 0.2)
    monkeypatch.setattr(sessione, "ATTESA_ELENCO_S", 3.0)
    monkeypatch.setattr(api_mod, "ATTESA_LOGIN_S", 0.01)


def _sessione(tmp_path: Path, driver: DriverFinto, monkeypatch: pytest.MonkeyPatch) -> SessioneSelenium:
    monkeypatch.setattr(sessione, "apri_chrome", lambda: driver)
    s = SessioneSelenium(tmp_path / "copie", lambda: ORA)
    s.apri()
    return s


# ─── le letture ──────────────────────────────────────────────────────────────


def test_leggi_strutture_da_prehome(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = _sessione(tmp_path, DriverFinto(), monkeypatch)
    lettura = s.leggi_strutture()
    assert len(lettura.strutture) == 8 and lettura.copia_pagina is None


def test_la_tendina_si_aspetta_se_la_pagina_non_e_ancora_pronta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prima prova del 20/10: elenco non letto al primo avvio, letto al
    secondo. Le prime letture di prehome qui sono vuote."""
    s = _sessione(tmp_path, DriverFinto(prehome_lenta=3), monkeypatch)
    lettura = s.leggi_strutture()
    assert len(lettura.strutture) == 8
    assert not (tmp_path / "copie").exists()


def test_leggi_mesi_col_codice_vero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Il punto esatto dove si è fermata la v1.3.0 sul PC di Marco."""
    s = _sessione(tmp_path, DriverFinto(), monkeypatch)
    letti = s.leggi_mesi("12345", [SETTEMBRE, OTTOBRE], strutture_note={"12345"})
    assert letti.struttura is not None
    assert (letti.struttura.id_turismatica, letti.struttura.cin) == ("12345", "IT054039B403012345")
    ottobre = letti.mesi["2026-10"]
    assert ottobre.giorni[1] is StatoGiorno.DA_FARE and ottobre.giorni[2] is StatoGiorno.NON_APERTO
    assert ottobre.invio_possibile is False
    # settembre: «Mese precedente» spento ⇒ periodo chiuso; la scheda chiusa
    # del finto è vuota, quindi «chiuso, giorni non letti», e non un avviso
    settembre = letti.mesi["2026-09"]
    assert settembre.chiuso and not settembre.giorni
    assert letti.avviso == ""


def test_leggi_mesi_di_un_altra_struttura_dell_elenco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    s = _sessione(tmp_path, DriverFinto(), monkeypatch)
    letti = s.leggi_mesi("12347", [OTTOBRE], strutture_note={"12345", "12347"})
    assert letti.struttura is not None and letti.struttura.cin == "IT054039B403012347"
    assert "2026-10" in letti.mesi


def test_se_l_indirizzo_apre_un_altra_struttura_si_passa_da_prehome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto(ricorda_scelta=True)
    s = _sessione(tmp_path, driver, monkeypatch)
    letti = s.leggi_mesi("12345", [OTTOBRE], strutture_note={"12345"})
    assert SCELTA_INIZIALE != "12345"
    assert "scegli:12345" in driver.registro
    assert letti.struttura is not None and letti.struttura.id_turismatica == "12345"
    assert letti.avviso == ""


def test_una_struttura_che_prehome_non_ha_lo_dice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto(ricorda_scelta=True)
    s = _sessione(tmp_path, driver, monkeypatch)
    letti = s.leggi_mesi("99999", [OTTOBRE], strutture_note={"12345"})
    assert letti.avviso.startswith("La struttura 99999 non è fra quelle del tuo account")
    assert letti.mesi == {}
    assert list((tmp_path / "copie").glob("pagina-movimenti-99999-*.html"))


def test_il_login_e_riconosciuto_in_prehome_solo_con_la_tendina(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto(prehome_lenta=1)
    s = _sessione(tmp_path, driver, monkeypatch)     # apri() va su prehome
    assert not s.dentro()                             # pagina ancora vuota (redirect al login)
    assert s.dentro()                                 # la tendina c'è


# ─── il caricamento e la comunicazione, in prova ────────────────────────────


def _file_del_giorno(tmp_path: Path, giorno: date) -> Path:
    f = tmp_path / f"schedine_istat_99001_{giorno:%Y%m%d}.txt"
    f.write_bytes(b"CASA LAVANDA".ljust(255) + b"\r\n")
    return f


def test_carica_in_prova_col_codice_vero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    driver = DriverFinto()
    s = _sessione(tmp_path, driver, monkeypatch)
    giorni = [date(2026, 10, 1), date(2026, 10, 2)]
    sorgente = sorgente_da([_file_del_giorno(tmp_path, g) for g in giorni], di_prova=False)
    passi: list[str] = []
    esito = s.carica(
        id_turismatica="12345", etichetta="CASA LAVANDA", sorgente=sorgente,
        periodo=Periodo(giorni[0], giorni[-1]), prova=True, strutture_note={"12345"},
        comunica=None, avanzamento=passi.append,
    )
    assert esito.saltata is None
    # il 1° ha il bottone: arriva a «Carica» e si ferma. Il 2 il portale lo
    # aprirà solo dopo il 1°: in prova è «da caricare», non «non riuscito»
    assert esito.giorni == {giorni[0]: Esito.DA_CARICARE, giorni[1]: Esito.DA_CARICARE}
    assert "apri_dialog" in driver.registro
    assert "send_keys:schedine_istat_99001_20261001.txt" in driver.registro
    assert not driver.dialog_aperto                  # chiuso senza caricare


def test_la_comunicazione_in_prova_non_parte_se_mancano_giorni(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto()
    s = _sessione(tmp_path, driver, monkeypatch)
    esito = s.carica(
        id_turismatica="12345", etichetta="CASA LAVANDA", sorgente=sorgente_da([], di_prova=False),
        periodo=None, prova=True, strutture_note={"12345"}, comunica=OTTOBRE,
        avanzamento=lambda _m: None,
    )
    assert not esito.comunicazione_riuscita
    assert "mancano ancora 31 giorni" in esito.comunicazione
    assert not any(r.startswith("premi:") for r in driver.registro)


def test_un_mese_chiuso_non_si_carica(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    s = _sessione(tmp_path, DriverFinto(), monkeypatch)
    giorno = date(2026, 9, 30)
    esito = s.carica(
        id_turismatica="12345", etichetta="CASA LAVANDA",
        sorgente=sorgente_da([_file_del_giorno(tmp_path, giorno)], di_prova=False),
        periodo=Periodo(giorno, giorno), prova=True, strutture_note={"12345"},
        comunica=None, avanzamento=lambda _m: None,
    )
    assert esito.saltata is not None and "già chiuso sul portale" in esito.saltata


# ─── il flusso dell'app sopra la sessione vera ───────────────────────────────


def _aspetta(a: Api, schermata: str, secondi: float = 10.0) -> dict[str, Any]:
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        s = a.stato()
        if s["schermata"] == schermata:
            return s["dati"]
        if s["schermata"] == "errore":
            raise AssertionError(s["dati"]["messaggio"])
        time.sleep(0.01)
    raise AssertionError(f"attesa «{schermata}», c'è «{a.stato()['schermata']}»")


def test_collega_da_capo_a_riepilogo_con_la_sessione_vera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Il giro che sul PC di Marco si è fermato: Api → SessioneSelenium →
    portale, con le otto strutture vere della copia di prehome."""
    driver = DriverFinto()
    monkeypatch.setattr(sessione, "apri_chrome", lambda: driver)
    a = Api(portale=lambda: SessioneSelenium(tmp_path / "copie", lambda: ORA),
            percorso_configurazione=tmp_path / "configurazione.json",
            percorso_registro=None, oggi=lambda: OGGI, ora=lambda: ORA)
    a.collega()
    # niente «Sono dentro»: in prehome con la tendina il login si riconosce da sé
    quante = _aspetta(a, "quante")
    assert len(quante["trovate"]) == 8 and quante["proposta"] == "piu"
    a.rispondi_quante("piu")
    riepilogo = _aspetta(a, "riepilogo", secondi=30)
    a.aspetta_fine()
    lavanda = next(s for s in riepilogo["strutture"] if s["id"] == "12345")
    assert lavanda["cin"] == "IT054039B403012345" and lavanda["comune"] == "PERUGIA"
    assert all(not s["avviso"] for s in riepilogo["strutture"])
    settembre, ottobre = lavanda["mesi"]
    assert settembre["comunicazione"] == "comunicato"
    assert ottobre["letto"] and ottobre["mancanti"] == list(range(1, 20))
    assert "quit" in driver.registro
    assert a.conferma_strutture([s["id"] for s in riepilogo["strutture"]]) == {"ok": True}


# ─── i doppi hanno la firma del codice vero ─────────────────────────────────


@pytest.mark.parametrize("metodo", ["apri", "dentro", "leggi_strutture", "leggi_mesi", "carica", "chiudi"])
def test_il_portale_finto_dei_test_ha_la_firma_della_sessione_vera(metodo: str) -> None:
    """Il doppio di ``test_flusso`` deve avere le stesse firme di
    ``SessioneSelenium`` e del Protocol ``Portale``: un doppio con una firma
    sua prova un programma che non esiste."""
    import inspect

    from tests.test_flusso import PortaleFinto
    from uploader_turismatica.sessione import Portale

    def firma(cls: type) -> list[tuple[str, Any]]:
        return [(p.name, p.kind) for p in inspect.signature(getattr(cls, metodo)).parameters.values()]

    assert firma(PortaleFinto) == firma(SessioneSelenium) == firma(Portale)
