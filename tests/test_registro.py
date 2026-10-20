"""Il registro accanto all'.exe: dove finisce, e cosa NON ci finisce."""
from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

from uploader_turismatica import registro
from uploader_turismatica.esito import Esito
from uploader_turismatica.portale import registra_giorno


@pytest.fixture(autouse=True)
def _pulisci_gestori() -> Iterator[None]:
    yield
    radice = logging.getLogger()
    for g in list(radice.handlers):
        if g.get_name() in ("registro-istat-uploader", "registro-console"):
            radice.removeHandler(g)
            g.close()


def _testo(percorso: Path | None) -> str:
    assert percorso is not None
    for g in logging.getLogger().handlers:
        g.flush()
    return percorso.read_text(encoding="utf-8")


def test_una_riga_per_giorno_con_data_giorno_esito_ed_errore(tmp_path: Path) -> None:
    percorso = registro.configura(tmp_path)
    assert percorso == tmp_path / registro.NOME_FILE
    registra_giorno("12345", date(2026, 9, 3), Esito.DA_CARICARE,
                    "schedine_istat_99001_20260903.txt", "")
    registra_giorno("12345", date(2026, 9, 4), Esito.NON_RIUSCITO,
                    "schedine_istat_99001_20260904.txt", "TimeoutException: dialog")
    righe = _testo(percorso).splitlines()
    assert righe[0].endswith(
        "struttura=12345 giorno=03/09/2026 esito=da_caricare "
        "file=schedine_istat_99001_20260903.txt"
    )
    assert "| WARNING |" in righe[1]
    assert righe[1].endswith("esito=non_riuscito file=schedine_istat_99001_20260904.txt "
                             "errore=TimeoutException: dialog")
    assert righe[0][:4].isdigit()          # comincia con la data


def test_la_cartella_personale_non_finisce_nel_registro() -> None:
    """``C:\\Users\\<nome>`` porta il nome di chi usa il PC: si scrive ``~``,
    anche dentro gli errori di Selenium e in tutte e due le grafie."""
    f = registro.FormattatoreRiservato(casa=Path("C:\\Users\\Mario Rossi"))
    rec = logging.LogRecord(
        "x", logging.WARNING, __file__, 1,
        "errore su C:\\Users\\Mario Rossi\\Downloads\\x.zip e C:/Users/Mario Rossi/AppData",
        None, None,
    )
    testo = f.format(rec)
    assert "Mario" not in testo
    assert "~\\Downloads\\x.zip" in testo and "~/AppData" in testo


def test_se_accanto_all_exe_non_si_scrive_si_ripiega(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Un .exe in ``Program Files`` o su una chiavetta protetta: il registro va
    nella cartella delle impostazioni, e la finestra dice dove."""
    bloccata = tmp_path / "file-non-cartella"
    bloccata.write_text("x")
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    percorso = registro.configura(bloccata / "sotto")
    assert percorso == tmp_path / "appdata" / "UploaderTurismatica" / registro.NOME_FILE
    logging.getLogger("prova").info("eccomi")
    assert "eccomi" in _testo(percorso)


def test_configurare_due_volte_non_raddoppia_le_righe(tmp_path: Path) -> None:
    registro.configura(tmp_path)
    percorso = registro.configura(tmp_path)
    logging.getLogger("prova").info("una volta sola")
    assert _testo(percorso).count("una volta sola") == 1


def test_impacchettato_il_registro_sta_accanto_all_exe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "IstatUploader.exe"))
    assert registro.cartella_preferita() == tmp_path.resolve()
