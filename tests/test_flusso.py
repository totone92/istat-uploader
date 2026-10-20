"""Il flusso dell'app da capo a fondo, con un portale finto.

Il finto è un finto di ``sessione.Portale`` — la **nostra** interfaccia — e
non del portale: risponde con strutture e giorni decisi qui, e registra cosa
gli si chiede. Ciò che si prova è il flusso: le schermate, cosa si salva e
quando, e soprattutto cosa **non** si fa (salvare prima dell'OK, caricare in
prova, usare lo zip di prova in modalità vera).
"""
from __future__ import annotations

import json
import time
import zipfile
from collections.abc import Callable, Collection, Iterator, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from scripts import zip_di_prova as zp
from uploader_turismatica import api as api_mod
from uploader_turismatica.api import Api
from uploader_turismatica.esito import Esito, EsitoStruttura
from uploader_turismatica.periodo import Periodo
from uploader_turismatica.piano import StatoGiorno, StatoMese
from uploader_turismatica.riconoscimento import StrutturaTrovata
from uploader_turismatica.sessione import LetturaMesi, LetturaStrutture
from uploader_turismatica.sorgente import MESSAGGIO_ZIP_DI_PROVA, Sorgente

OGGI = date(2026, 10, 20)
ORA = datetime(2026, 10, 20, 9, 30)


class PortaleFinto:
    def __init__(self, strutture: list[StrutturaTrovata], *, caricati_settembre: set[int],
                 avvisi: dict[str, str] | None = None, cin: dict[str, str] | None = None) -> None:
        self.strutture = strutture
        #: Il CIN che l'intestazione dei movimenti mostra, per struttura.
        self.cin = cin or {}
        self.caricati = caricati_settembre
        self.avvisi = avvisi or {}
        self.chiamate: list[str] = []
        self.caricamenti: list[dict[str, Any]] = []

    def apri(self) -> None:
        self.chiamate.append("apri")

    def dentro(self) -> bool:
        return True

    def leggi_strutture(self) -> LetturaStrutture:
        self.chiamate.append("leggi_strutture")
        if not self.strutture:
            return LetturaStrutture([], Path("/registro/pagina-strutture.html"))
        return LetturaStrutture(list(self.strutture))

    def leggi_mesi(self, id_turismatica: str, mesi: Sequence[date], *,
                   strutture_note: Collection[str]) -> LetturaMesi:
        self.chiamate.append(f"leggi_mesi:{id_turismatica}")
        if id_turismatica in self.avvisi:
            return LetturaMesi({}, self.avvisi[id_turismatica])
        settembre = StatoMese(2026, 9, {
            g: StatoGiorno.CARICATO if g in self.caricati else StatoGiorno.DA_FARE
            for g in range(1, 31)}, ORA)
        testata = StrutturaTrovata(id_turismatica, "NOME DALL'INTESTAZIONE", "PERUGIA",
                                   "Affittacamere", "VALIDATA", cin=self.cin.get(id_turismatica, ""))
        return LetturaMesi({"2026-09": settembre}, struttura=testata)

    def carica(self, *, id_turismatica: str, etichetta: str, sorgente: Sorgente,
               periodo: Periodo | None, prova: bool, strutture_note: Collection[str],
               comunica: date | None, avanzamento: Callable[[str], None]) -> EsitoStruttura:
        self.caricamenti.append({
            "id": id_turismatica, "periodo": (periodo.dal, periodo.al) if periodo else None,
            "prova": prova, "di_prova": sorgente.di_prova, "comunica": comunica,
        })
        e = EsitoStruttura(etichetta=etichetta, id_turismatica=id_turismatica)
        if comunica is not None:
            e.comunicazione_riuscita = True
            e.comunicazione = "pronta" if prova else "inviata"
        for g in (periodo.giorni if periodo else []):
            avanzamento(f"{g:%d/%m/%Y}")
            if g.day in self.caricati:
                e.segna(g, Esito.GIA_CARICATO)
            else:
                e.segna(g, Esito.DA_CARICARE if prova else Esito.CARICATO)
        return e

    def chiudi(self) -> None:
        self.chiamate.append("chiudi")


DUE = [StrutturaTrovata("12345", "CASA LAVANDA", "PERUGIA", "Affittacamere", "VALIDATA"),
       StrutturaTrovata("23456", "Agriturismo Le Ginestre", "ASSISI", "Agriturismo")]


@pytest.fixture(autouse=True)
def _login_veloce(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_mod, "ATTESA_LOGIN_S", 0.01)


def _api(tmp_path: Path, portale: PortaleFinto) -> Api:
    return Api(portale=lambda: portale, percorso_configurazione=tmp_path / "configurazione.json",
               percorso_registro=None, oggi=lambda: OGGI, ora=lambda: ORA)


def _aspetta(a: Api, schermata: str, secondi: float = 5.0) -> dict[str, Any]:
    fine = time.monotonic() + secondi
    while time.monotonic() < fine:
        s = a.stato()
        if s["schermata"] == schermata:
            return s["dati"]
        time.sleep(0.01)
    raise AssertionError(f"attesa «{schermata}», c'è «{a.stato()['schermata']}»")


def _collega(tmp_path: Path, portale: PortaleFinto, tieni: list[str] | None = None) -> Api:
    a = _api(tmp_path, portale)
    assert a.stato()["schermata"] == "benvenuto"
    a.collega()
    quante = _aspetta(a, "quante")
    assert quante["proposta"] == ("una" if len(portale.strutture) == 1 else "piu")
    a.rispondi_quante(quante["proposta"])
    _aspetta(a, "riepilogo")
    assert a.conferma_strutture(tieni or [s.id_turismatica for s in portale.strutture]) == {"ok": True}
    return a


# ─── il primo avvio ──────────────────────────────────────────────────────────


def test_primo_avvio_riconosce_legge_i_giorni_e_salva_solo_dopo_l_ok(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set(range(1, 31)) - {12, 19})
    a = _api(tmp_path, portale)
    a.collega()
    quante = _aspetta(a, "quante")
    assert [s["nome"] for s in quante["trovate"]] == ["CASA LAVANDA", "Agriturismo Le Ginestre"]
    assert quante["proposta"] == "piu"
    a.rispondi_quante("piu")
    riepilogo = _aspetta(a, "riepilogo")
    settembre = riepilogo["strutture"][0]["mesi"][0]
    assert settembre["etichetta"] == "settembre 2026" and settembre["mancanti"] == [12, 19]
    assert portale.chiamate == ["apri", "leggi_strutture", "leggi_mesi:12345",
                                "leggi_mesi:23456", "chiudi", "chiudi"]
    # ⚠️ prima dell'OK non c'è niente su disco
    assert not (tmp_path / "configurazione.json").exists()
    a.conferma_strutture(["23456"])                  # tolta CASA LAVANDA
    principale = _aspetta(a, "principale")
    assert [s["nome"] for s in principale["strutture"]] == ["Agriturismo Le Ginestre"]
    salvata = json.loads((tmp_path / "configurazione.json").read_text())
    assert [s["id_turismatica"] for s in salvata["strutture"]] == ["23456"]


def test_al_secondo_avvio_si_apre_la_principale(tmp_path: Path) -> None:
    _collega(tmp_path, PortaleFinto(DUE, caricati_settembre=set()))
    assert _api(tmp_path, PortaleFinto([], caricati_settembre=set())).stato()["schermata"] == "principale"


def test_una_struttura_sola_propone_una(tmp_path: Path) -> None:
    a = _api(tmp_path, PortaleFinto(DUE[:1], caricati_settembre=set()))
    a.collega()
    assert _aspetta(a, "quante")["proposta"] == "una"


def test_se_l_elenco_non_si_legge_si_inseriscono_a_mano(tmp_path: Path) -> None:
    portale = PortaleFinto([], caricati_settembre=set())
    a = _api(tmp_path, portale)
    a.collega()
    manuale = _aspetta(a, "manuale")
    assert "pagina-strutture.html" in manuale["messaggio"] and "senza dati personali" in manuale["messaggio"]
    assert "errore" in a.inserisci_a_mano([{"id": "UCI", "nome": ""}])
    a.inserisci_a_mano([{"id": "123", "nome": "UCI"}])
    riepilogo = _aspetta(a, "riepilogo")
    assert riepilogo["manuale"] and riepilogo["strutture"][0]["id"] == "123"


def test_una_struttura_non_tua_lo_dice_nel_riepilogo(tmp_path: Path) -> None:
    portale = PortaleFinto([StrutturaTrovata("123", "UCI")], caricati_settembre=set(),
                           avvisi={"123": "La struttura 123 non è fra quelle del tuo account Turismatica."})
    a = _api(tmp_path, portale)
    a.collega()
    _aspetta(a, "quante")
    a.rispondi_quante("una")
    (s,) = _aspetta(a, "riepilogo")["strutture"]
    assert s["avviso"].startswith("La struttura 123 non è fra quelle del tuo account")


def test_annullare_durante_spid_non_salva_niente(tmp_path: Path) -> None:
    class Lento(PortaleFinto):
        def dentro(self) -> bool:
            return False

    a = _api(tmp_path, Lento(DUE, caricati_settembre=set()))
    a.collega()
    assert _aspetta(a, "spid")["perche"] == "collega"
    a.annulla()
    _aspetta(a, "benvenuto")
    assert not (tmp_path / "configurazione.json").exists()


# ─── lo zip, l'abbinamento, il piano, il giro ───────────────────────────────


def _zip(tmp_path: Path, nome_struttura: str, ident: str, giorni: range) -> Path:
    z = tmp_path / f"istat_{ident}.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for g in giorni:
            zf.writestr(f"schedine_istat_{ident}_202609{g:02d}.txt",
                        nome_struttura.encode().ljust(255) + b"\r\n")
    return z


def test_nome_uguale_va_dritto_al_piano_e_la_prova_non_carica(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set(range(1, 31)) - {12, 19})
    a = _collega(tmp_path, portale)
    a.usa_zip(str(_zip(tmp_path, "Casa Lavanda", "99001", range(1, 31))))
    piano = _aspetta(a, "piano")
    assert piano["voci"][0]["testo"] == (
        "Settembre 2026, CASA LAVANDA: 28 giorni già presenti, 2 da caricare (12 e 19).")
    assert a.stato()["prova"] is True
    a.avvia()
    esito = _aspetta(a, "esito")
    assert esito["prova"] and esito["testo"].startswith("MODALITÀ PROVA")
    (c,) = portale.caricamenti
    assert c["prova"] is True and c["periodo"] == (date(2026, 9, 12), date(2026, 9, 19))


def test_modalita_vera_solo_con_conferma_e_aggiorna_lo_stato(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set(range(1, 31)) - {12, 19})
    a = _collega(tmp_path, portale)
    assert "errore" in a.imposta_prova(False)            # senza conferma no
    assert a.imposta_prova(False, confermato=True) == {"ok": True}
    a.usa_zip(str(_zip(tmp_path, "Casa Lavanda", "99001", range(1, 31))))
    _aspetta(a, "piano")
    assert "errore" in a.avvia()                          # seconda conferma
    a.avvia(confermato=True)
    esito = _aspetta(a, "esito")
    assert not esito["prova"] and esito["strutture"][0]["caricati"] == 2
    salvata = json.loads((tmp_path / "configurazione.json").read_text())
    giorni = salvata["strutture"][0]["mesi"]["2026-09"]["giorni"]
    assert giorni["12"] == giorni["19"] == "caricato"


def test_nome_diverso_si_chiede_e_la_scelta_si_ricorda(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set())
    a = _collega(tmp_path, portale)
    a.usa_zip(str(_zip(tmp_path, "Le Ginestre B&B", "99002", range(1, 4))))
    (g,) = _aspetta(a, "abbina")["gruppi"]
    assert g["proposte"][0]["id"] == "23456" and g["scelta"] == ""      # proposta, non scelta
    assert a.conferma_abbinamenti({g["chiave"]: "23456"}, ricorda=True) == {"ok": True}
    _aspetta(a, "piano")
    a.torna_alla_principale()
    a.usa_zip(str(_zip(tmp_path, "Le Ginestre B&B", "99002", range(1, 4))))
    assert _aspetta(a, "piano")["voci"][0]["struttura"] == "Agriturismo Le Ginestre"


def test_una_struttura_sola_preseleziona_ma_chiede(tmp_path: Path) -> None:
    a = _collega(tmp_path, PortaleFinto(DUE[:1], caricati_settembre=set()))
    a.usa_zip(str(_zip(tmp_path, "Nome di beb diverso", "99001", range(1, 4))))
    (g,) = _aspetta(a, "abbina")["gruppi"]
    assert g["scelta"] == "12345" and not g["deciso"]


# ─── lo zip di prova ─────────────────────────────────────────────────────────


@pytest.fixture
def zip_prova(tmp_path: Path) -> Iterator[Path]:
    yield zp.zip_di_prova(tmp_path / zp.NOME_ZIP)


def test_lo_zip_di_prova_si_abbina_a_mano_solo_in_prova_e_non_si_ricorda(
    tmp_path: Path, zip_prova: Path,
) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set(range(1, 29)))
    a = _collega(tmp_path, portale)
    a.usa_zip(str(zip_prova))
    (g,) = _aspetta(a, "abbina")["gruppi"]
    assert g["di_prova"] and "solo per vedere il giro in modalità prova" in g["domanda"]
    a.conferma_abbinamenti({g["chiave"]: "12345"}, ricorda=True)
    _aspetta(a, "piano")
    salvata = json.loads((tmp_path / "configurazione.json").read_text())
    assert salvata["alias"] == {}                        # mai ricordato
    a.avvia()
    _aspetta(a, "esito")
    assert portale.caricamenti[0]["prova"] is True and portale.caricamenti[0]["di_prova"]


def test_lo_zip_di_prova_in_modalita_vera_e_bloccato(tmp_path: Path, zip_prova: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set())
    a = _collega(tmp_path, portale)
    a.imposta_prova(False, confermato=True)
    a.usa_zip(str(zip_prova))
    principale = _aspetta(a, "principale")
    assert principale["avviso"] == MESSAGGIO_ZIP_DI_PROVA
    assert principale["tipo_avviso"] == "errore"
    assert portale.caricamenti == []


def test_lo_zip_di_prova_abbinato_in_prova_non_parte_se_si_passa_alla_vera(
    tmp_path: Path, zip_prova: Path,
) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set())
    a = _collega(tmp_path, portale)
    a.usa_zip(str(zip_prova))
    (g,) = _aspetta(a, "abbina")["gruppi"]
    a.conferma_abbinamenti({g["chiave"]: "12345"}, ricorda=False)
    _aspetta(a, "piano")
    a.imposta_prova(False, confermato=True)
    assert a.avvia(confermato=True) == {"errore": MESSAGGIO_ZIP_DI_PROVA}
    assert portale.caricamenti == []


def test_un_file_che_non_e_uno_zip_lo_dice(tmp_path: Path) -> None:
    a = _collega(tmp_path, PortaleFinto(DUE, caricati_settembre=set()))
    (tmp_path / "foto.jpg").write_bytes(b"x")
    a.usa_zip(str(tmp_path / "foto.jpg"))
    assert "Scegli lo zip dei file ISTAT" in _aspetta(a, "principale")["avviso"]


# ─── l'intestazione dei movimenti, il CIN, la comunicazione mensile ─────────

CIN = {"12345": "IT054039B403012345", "23456": "IT054056C203023456"}


def test_l_intestazione_completa_la_struttura_ma_il_nome_resta_quello_dell_elenco(
    tmp_path: Path,
) -> None:
    _collega(tmp_path, PortaleFinto([StrutturaTrovata("12345", "CASA LAVANDA")],
                                    caricati_settembre=set(), cin=CIN))
    (s,) = json.loads((tmp_path / "configurazione.json").read_text())["strutture"]
    assert (s["nome"], s["comune"], s["tipologia"], s["cin"]) == (
        "CASA LAVANDA", "PERUGIA", "Affittacamere", "IT054039B403012345")


def test_i_file_col_cin_si_abbinano_da_soli_se_la_regola_regge_su_tutte(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set(), cin=CIN)
    a = _collega(tmp_path, portale)
    a.usa_zip(str(_zip(tmp_path, "Un nome che il portale non conosce", CIN["23456"], range(1, 4))))
    assert _aspetta(a, "piano")["voci"][0]["struttura"] == "Agriturismo Le Ginestre"


def test_se_un_cin_non_contiene_il_numero_il_cin_non_abbina_niente(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set(),
                           cin={**CIN, "23456": "IT054056C203099999"})
    a = _collega(tmp_path, portale)
    a.usa_zip(str(_zip(tmp_path, "Un nome che il portale non conosce", CIN["12345"], range(1, 4))))
    (g,) = _aspetta(a, "abbina")["gruppi"]
    assert not g["deciso"]


def _api_al(tmp_path: Path, portale: PortaleFinto, oggi: date) -> Api:
    return Api(portale=lambda: portale, percorso_configurazione=tmp_path / "configurazione.json",
               percorso_registro=None, oggi=lambda: oggi, ora=lambda: ORA)


def test_la_comunicazione_mensile_si_chiede_e_va_in_fondo_al_giro(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE[:1], caricati_settembre=set(range(1, 31)) - {30})
    _collega(tmp_path, portale)
    a = _api_al(tmp_path, portale, date(2026, 10, 3))
    a.imposta_prova(False, confermato=True)
    a.usa_zip(str(_zip(tmp_path, "Casa Lavanda", "99001", range(1, 31))))
    (v,) = _aspetta(a, "piano")["voci"]
    assert v["comunicabile"] and v["scadenza"] == "05/10"
    # non richiesta: non parte
    a.avvia(confermato=True)
    _aspetta(a, "esito")
    assert portale.caricamenti[-1]["comunica"] is None
    # richiesta: va al portale insieme al caricamento, e il mese si segna chiuso
    a.torna_alla_principale()
    a.usa_zip(str(_zip(tmp_path, "Casa Lavanda", "99001", range(1, 31))))
    _aspetta(a, "piano")
    a.avvia(confermato=True, comunica=[v["chiave"]])
    esito = _aspetta(a, "esito")
    assert portale.caricamenti[-1]["comunica"] == date(2026, 9, 1)
    assert esito["strutture"][0]["comunicazione"] == "inviata"
    salvata = json.loads((tmp_path / "configurazione.json").read_text())
    assert salvata["strutture"][0]["mesi"]["2026-09"]["chiuso"] is True


def test_la_comunicazione_non_si_chiede_per_un_mese_che_non_lo_permette(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE[:1], caricati_settembre=set())
    a = _collega(tmp_path, portale)                       # oggi 20/10: oltre il 5
    a.usa_zip(str(_zip(tmp_path, "Casa Lavanda", "99001", range(1, 31))))
    (v,) = _aspetta(a, "piano")["voci"]
    assert not v["comunicabile"]
    assert "errore" in a.avvia(comunica=[v["chiave"]])
    assert portale.caricamenti == []
