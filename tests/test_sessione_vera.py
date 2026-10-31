"""Il codice vero di ``SessioneSelenium`` e ``portale.py``, con un driver
finto che serve le pagine vere del portale (``tests/driver_finto.py``).

⚠️ Sono i test che mancavano alla v1.3.0: il flusso era provato con un doppio
di ``Portale`` con la firma giusta, mentre ``SessioneSelenium.leggi_mesi``
chiamava ``apri_movimenti`` con un argomento di troppo. Qui ogni chiamata passa
dalle funzioni vere: una firma sbagliata è un ``TypeError`` nel test.
"""
from __future__ import annotations

import time
import zipfile
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
    monkeypatch.setattr(portale, "ATTESA_CONFERMA_S", 0.2)
    monkeypatch.setattr(portale, "ATTESA_USCITA_S", 0.0)
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


def _prima_diretta(driver: DriverFinto) -> bool:
    """Si è aperto l'indirizzo dei movimenti prima di scegliere la struttura?"""
    for r in driver.registro:
        if r.startswith("scegli:"):
            return False
        if r.startswith("get:") and "idStruttura=" in r:
            return True
    return False


def test_ai_movimenti_si_va_sempre_da_prehome_mai_dal_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto()
    s = _sessione(tmp_path, driver, monkeypatch)
    letti = s.leggi_mesi("12345", [OTTOBRE], strutture_note={"12345"})
    assert SCELTA_INIZIALE != "12345"
    assert "scegli:12345" in driver.registro
    assert not _prima_diretta(driver)
    assert not any(r.startswith("get:") and "idStruttura=" in r for r in driver.registro)
    assert letti.struttura is not None and letti.struttura.id_turismatica == "12345"
    assert letti.avviso == ""


def test_se_accedi_atterra_su_una_home_si_apre_l_indirizzo_solo_dopo_la_scelta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto(atterra_su_home=True)
    s = _sessione(tmp_path, driver, monkeypatch)
    letti = s.leggi_mesi("12345", [OTTOBRE], strutture_note={"12345"})
    assert not _prima_diretta(driver)
    assert any(r.startswith("get:") and "idStruttura=12345" in r for r in driver.registro)
    assert letti.avviso == "" and "2026-10" in letti.mesi


def test_una_struttura_che_prehome_non_ha_lo_dice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto()
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


# ─── in modalità vera: la conferma, il buco, la sessione che scade ──────────


def _carica_vero(
    s: SessioneSelenium, tmp_path: Path, giorni: list[date], *, periodo: Periodo | None = None,
    rientra: Any = None, prova: bool = False,
) -> Any:
    return s.carica(
        id_turismatica="12345", etichetta="CASA LAVANDA",
        sorgente=sorgente_da([_file_del_giorno(tmp_path, g) for g in giorni], di_prova=False),
        periodo=periodo or Periodo(giorni[0], giorni[-1]), prova=prova, strutture_note={"12345"},
        comunica=None, avanzamento=lambda _m: None, rientra=rientra,
    )


def _ott(*giorni: int) -> list[date]:
    return [OTTOBRE.replace(day=g) for g in giorni]


def test_caricato_solo_se_la_riga_riletta_ha_i_segni(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto()
    esito = _carica_vero(_sessione(tmp_path, driver, monkeypatch), tmp_path, _ott(1, 2, 3))
    assert esito.elenco(Esito.CARICATO) == _ott(1, 2, 3)
    assert driver.pressioni_carica == 3 and not esito.motivi


def test_dialog_chiuso_ma_riga_senza_segni_e_non_riuscito_col_motivo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto(carica_accettato=False)
    esito = _carica_vero(_sessione(tmp_path, driver, monkeypatch), tmp_path, _ott(1))
    assert esito.giorni == {OTTOBRE: Esito.NON_RIUSCITO}
    assert "non risulta caricato" in esito.motivi[OTTOBRE]


def test_la_tabella_rimasta_vecchia_non_da_un_falso_non_riuscito(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """I segni in pagina non arrivano: prima di dire «non riuscito» si riapre."""
    driver = DriverFinto(tabella_vecchia=True)
    esito = _carica_vero(_sessione(tmp_path, driver, monkeypatch), tmp_path, _ott(1))
    assert esito.giorni == {OTTOBRE: Esito.CARICATO}


def test_al_primo_buco_ci_si_ferma_e_non_si_provano_i_giorni_dopo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto()
    esito = _carica_vero(_sessione(tmp_path, driver, monkeypatch), tmp_path, _ott(1, 2, 4, 5))
    assert esito.giorni == {_ott(1)[0]: Esito.CARICATO, _ott(2)[0]: Esito.CARICATO,
                            _ott(3)[0]: Esito.FILE_MANCANTE}
    assert esito.fermata == ("Manca il file del 03/10/2026: i giorni dopo restano fermi "
                             "finché non c'è quello.")
    assert driver.pressioni_carica == 2
    assert not esito.elenco(Esito.NON_RIUSCITO)


def test_il_buco_vale_anche_in_prova(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    driver = DriverFinto()
    esito = _carica_vero(_sessione(tmp_path, driver, monkeypatch), tmp_path, _ott(1, 3), prova=True)
    assert esito.giorni[_ott(2)[0]] is Esito.FILE_MANCANTE and _ott(3)[0] not in esito.giorni
    assert driver.pressioni_carica == 0


def test_il_buco_prima_del_primo_file_ferma_tutto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sul portale fino al 2, nello zip dal 5: il periodo comincia il 5, ma il
    primo giorno senza file è il 3."""
    driver = DriverFinto(caricati=set(_ott(1, 2)))
    esito = _carica_vero(_sessione(tmp_path, driver, monkeypatch), tmp_path, _ott(5, 6))
    assert esito.giorni == {_ott(3)[0]: Esito.FILE_MANCANTE}
    assert "03/10/2026" in esito.fermata and driver.pressioni_carica == 0


def test_un_giorno_senza_file_ma_gia_sul_portale_non_e_un_buco(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto(caricati=set(_ott(2)))
    esito = _carica_vero(_sessione(tmp_path, driver, monkeypatch), tmp_path, _ott(1, 3),
                         periodo=Periodo(_ott(1)[0], _ott(3)[0]))
    assert esito.giorni[_ott(2)[0]] is Esito.GIA_CARICATO and not esito.fermata


def test_sessione_scaduta_a_meta_si_aspetta_e_si_riprende_dal_giorno(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dopo il 2° caricamento il portale butta fuori: nessun giorno fallito,
    una pausa sola, e ogni giorno caricato una volta sola."""
    driver = DriverFinto(scade_dopo=2)
    pause: list[bool] = []

    def rientra() -> None:
        pause.append(True)
        driver.rientra()

    esito = _carica_vero(_sessione(tmp_path, driver, monkeypatch), tmp_path, _ott(1, 2, 3, 4),
                         rientra=rientra)
    assert esito.elenco(Esito.CARICATO) == _ott(1, 2, 3, 4) and not esito.motivi
    assert pause == [True] and driver.pressioni_carica == 4
    # si è tornati alla pagina dei movimenti dopo il rientro
    dopo = driver.registro[driver.registro.index("rientro"):]
    assert "scegli:12345" in dopo


def test_rientro_dichiarato_ma_non_vero_si_richiede(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = DriverFinto(scade_dopo=1)
    pause: list[bool] = []

    def rientra() -> None:
        pause.append(True)
        if len(pause) == 2:                 # al primo «Sono dentro» non era vero
            driver.rientra()

    esito = _carica_vero(_sessione(tmp_path, driver, monkeypatch), tmp_path, _ott(1, 2),
                         rientra=rientra)
    assert len(pause) == 2 and esito.elenco(Esito.CARICATO) == _ott(1, 2)


def test_la_pausa_nel_flusso_dell_app_chiede_spid_e_riprende(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uploader_turismatica import configurazione
    from uploader_turismatica.configurazione import Configurazione, StrutturaConf

    driver = DriverFinto(scade_dopo=1)
    monkeypatch.setattr(sessione, "apri_chrome", lambda: driver)
    percorso = tmp_path / "configurazione.json"
    configurazione.salva(Configurazione(
        strutture=[StrutturaConf("12345", "Casa Lavanda", "PERUGIA", "Affittacamere")],
        quante="una", aggiornata_il=ORA), percorso)
    a = Api(portale=lambda: SessioneSelenium(tmp_path / "copie", lambda: ORA),
            percorso_configurazione=percorso, percorso_registro=None,
            oggi=lambda: OGGI, ora=lambda: ORA)
    z = tmp_path / "ottobre.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for g in (1, 2):
            zf.writestr(f"schedine_istat_99001_202610{g:02d}.txt", b"Casa Lavanda".ljust(255) + b"\r\n")
    a.imposta_prova(False, confermato=True)
    a.usa_zip(str(z))
    _aspetta(a, "piano")
    a.avvia(confermato=True)
    fine = time.monotonic() + 10
    while a.stato()["dati"].get("perche") != "scaduta" and time.monotonic() < fine:
        time.sleep(0.01)
    assert a.stato()["schermata"] == "spid" and a.stato()["dati"]["perche"] == "scaduta"
    driver.rientra()                         # entrato: si accorge da solo
    esito = _aspetta(a, "esito", secondi=20)
    assert esito["strutture"][0]["caricati"] == 2 and not esito["strutture"][0]["non_riusciti"]
    a.aspetta_fine()
    giorni = configurazione.carica(percorso).strutture[0].mesi["2026-10"].giorni  # type: ignore[union-attr]
    assert giorni[1] is StatoGiorno.CARICATO and giorni[2] is StatoGiorno.CARICATO


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
