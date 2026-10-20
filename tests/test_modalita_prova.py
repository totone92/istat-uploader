"""La modalità prova: tutto fino all'ultimo passo, e l'ultimo passo no.

⚠️ Il finto qui sotto è un finto di ``portale.Passi`` — **la nostra**
interfaccia — e non del portale: non riproduce selettori né PrimeFaces, conta
solo quali passi la sequenza chiede e in che ordine. Ciò che si prova è la
nostra decisione («in prova non si preme Carica»), che è l'unica cosa di questo
giro che può far danni sul portale vero.
"""
from __future__ import annotations

import inspect
from datetime import date
from pathlib import Path

import pytest

from uploader_turismatica.esito import Esito, EsitoStruttura, riepilogo
from uploader_turismatica.portale import carica_giorno, carica_struttura

GIORNO = date(2026, 9, 3)
FILE = Path("schedine_istat_99001_20260903.txt")

#: Una riga del portale per un giorno già dentro («File caricato: …»).
RIGA_CARICATA = (
    ["", "03/09/2026", "4", "1", "2", "3", "2"], [], ["File caricato: x.txt"],
)
#: Una riga per un giorno ancora da fare (la doppia freccia, nessun valore).
RIGA_DA_FARE = (
    ["", "03/09/2026", "", "", "", "", ""], ["fa fa-angle-double-down"], [],
)


class PassiFinti:
    def __init__(
        self,
        riga: tuple[list[str], list[str], list[str]] | None = RIGA_DA_FARE,
        *,
        bottone: bool = True,
        pronto: bool = True,
        conferma: bool = True,
    ) -> None:
        self._riga, self._bottone = riga, bottone
        self._pronto, self._conferma = pronto, conferma
        self.chiamate: list[str] = []

    def riga(self, giorno: date) -> tuple[list[str], list[str], list[str]] | None:
        self.chiamate.append("riga")
        return self._riga

    def apri_dialog(self, giorno: date) -> bool:
        self.chiamate.append("apri_dialog")
        return self._bottone

    def scegli_file(self, file: Path) -> None:
        self.chiamate.append(f"scegli_file:{file.name}")

    def pronto(self) -> bool:
        self.chiamate.append("pronto")
        return self._pronto

    def conferma(self) -> bool:
        self.chiamate.append("conferma")
        return self._conferma

    def annulla(self) -> None:
        self.chiamate.append("annulla")


def test_in_prova_si_arriva_a_carica_e_NON_si_preme() -> None:
    """⭐ La sostanza della modalità: dialog aperto, file scelto, «Carica»
    pronto — poi si chiude. ``conferma`` non compare mai."""
    passi = PassiFinti()
    assert carica_giorno(passi, GIORNO, FILE, prova=True) is Esito.DA_CARICARE
    assert passi.chiamate == [
        "riga", "apri_dialog", f"scegli_file:{FILE.name}", "pronto", "annulla",
    ]


def test_in_modalita_vera_si_preme_carica() -> None:
    passi = PassiFinti()
    assert carica_giorno(passi, GIORNO, FILE, prova=False) is Esito.CARICATO
    assert passi.chiamate == [
        "riga", "apri_dialog", f"scegli_file:{FILE.name}", "conferma",
    ]


@pytest.mark.parametrize("prova", [True, False])
def test_un_giorno_gia_caricato_non_si_tocca_in_nessuna_modalita(prova: bool) -> None:
    """Ricaricarlo lo sostituirebbe: né in prova né in vera si apre il dialog.
    È anche ciò che la prima prova su un mese già caricato deve far vedere."""
    passi = PassiFinti(RIGA_CARICATA)
    assert carica_giorno(passi, GIORNO, FILE, prova=prova) is Esito.GIA_CARICATO
    assert passi.chiamate == ["riga"]


def test_in_prova_un_carica_che_non_si_accende_e_non_riuscito() -> None:
    """Se il portale non accetta il file scelto, la prova lo deve dire: è
    esattamente ciò che si vuole scoprire prima del giro vero."""
    passi = PassiFinti(pronto=False)
    assert carica_giorno(passi, GIORNO, FILE, prova=True) is Esito.NON_RIUSCITO
    assert "conferma" not in passi.chiamate
    assert passi.chiamate[-1] == "annulla"


@pytest.mark.parametrize("prova", [True, False])
def test_senza_pulsante_il_giorno_non_e_riuscito_e_nessun_file_si_sceglie(
    prova: bool,
) -> None:
    passi = PassiFinti(bottone=False)
    assert carica_giorno(passi, GIORNO, FILE, prova=prova) is Esito.NON_RIUSCITO
    assert passi.chiamate == ["riga", "apri_dialog"]


def test_un_carica_fallito_in_modalita_vera_chiude_il_dialog() -> None:
    """Un dialog rimasto aperto fa fallire anche il giorno dopo."""
    passi = PassiFinti(conferma=False)
    assert carica_giorno(passi, GIORNO, FILE, prova=False) is Esito.NON_RIUSCITO
    assert passi.chiamate[-2:] == ["conferma", "annulla"]


@pytest.mark.parametrize("funzione", [carica_giorno, carica_struttura])
def test_prova_non_ha_default(funzione: object) -> None:
    """Dimenticare di dirlo non deve voler dire caricare."""
    parametro = inspect.signature(funzione).parameters["prova"]  # type: ignore[arg-type]
    assert parametro.default is inspect.Parameter.empty
    assert parametro.kind is inspect.Parameter.KEYWORD_ONLY


def test_l_app_si_sveglia_in_prova() -> None:
    from uploader_turismatica.app import PROVA_ALL_AVVIO

    assert PROVA_ALL_AVVIO is True


def test_il_riepilogo_di_prova_dice_che_non_ha_caricato_e_cosa_avrebbe_caricato() -> None:
    e = EsitoStruttura(etichetta="Il Melograno", id_turismatica="12345")
    e.segna(date(2026, 9, 1), Esito.GIA_CARICATO, "schedine_istat_99001_20260901.txt")
    e.segna(date(2026, 9, 2), Esito.DA_CARICARE, "schedine_istat_99001_20260902.txt")
    e.segna(date(2026, 9, 3), Esito.DA_CARICARE, "03092026.txt")
    testo = riepilogo([e], "settembre 2026", prova=True)
    assert testo.startswith("MODALITÀ PROVA — NON HO CARICATO NIENTE.")
    assert "2 giorni da caricare, 1 già c'erano" in testo
    assert "02/09/2026  ←  schedine_istat_99001_20260902.txt" in testo
    assert "03/09/2026  ←  03092026.txt" in testo
    assert "caricati" not in testo           # nessun «N giorni caricati»
    assert "Tutto a posto" not in testo      # una prova non chiude niente
    assert "MODALITÀ VERA" in testo


def test_il_riepilogo_vero_non_parla_di_prova() -> None:
    e = EsitoStruttura(etichetta="Il Melograno", id_turismatica="12345")
    e.segna(date(2026, 9, 2), Esito.CARICATO, "schedine_istat_99001_20260902.txt")
    testo = riepilogo([e], "settembre 2026", prova=False)
    assert "PROVA" not in testo
    assert "←" not in testo
    assert "Tutto a posto" in testo
