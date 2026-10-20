"""Lo zip di prova: che sia nel formato giusto, e che non arrivi MAI al portale
in modalità vera."""
from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest

from scripts import zip_di_prova as zp
from uploader_turismatica.esito import Esito
from uploader_turismatica.periodo import mese
from uploader_turismatica.portale import carica_struttura
from uploader_turismatica.sorgente import (
    MESSAGGIO_ZIP_DI_PROVA,
    apri,
    blocco_modalita_vera,
)

SETTEMBRE = mese(2026, 9)
_RIFERIMENTO = Path(__file__).parent / "fixtures" / "tolm_hostlab_20260903.txt"


@pytest.fixture
def zip_prova(tmp_path: Path) -> Path:
    return zp.zip_di_prova(tmp_path / zp.NOME_ZIP)


# ─── il formato ──────────────────────────────────────────────────────────────


def test_la_copia_del_renderer_da_gli_stessi_byte_di_hostlab() -> None:
    """⭐ Il riferimento l'ha reso ``hostlab.turismatica.tolm.rendi`` (lo stesso
    giorno inventato, il 03/09), che in HostLab è provato byte per byte sui file
    di beb accettati dal portale. Se la copia diverge, qui si vede."""
    terzo = next(g for g in zp.mese_inventato() if g.giorno == date(2026, 9, 3))
    assert zp.rendi(zp.NOME_STRUTTURA, terzo) == _RIFERIMENTO.read_bytes()


def test_la_forma_di_ogni_file_e_quella_del_portale(zip_prova: Path) -> None:
    with zipfile.ZipFile(zip_prova) as zf:
        for nome in zf.namelist():
            if nome == zp.MARCATORE:
                continue
            b = zf.read(nome)
            righe = b.split(b"\r\n")
            assert not b.endswith(b"\r\n") and b"\n" not in b.replace(b"\r\n", b"")
            assert len(righe[0]) == 255 and righe[0].rstrip() == b"STRUTTURA DI PROVA"
            assert b.isascii()


def test_i_numeri_inventati_tornano_come_in_un_mese_vero() -> None:
    giorni = zp.mese_inventato()
    assert [g.giorno for g in giorni] == SETTEMBRE.giorni
    ieri = 0
    for g in giorni:
        assert g.presenti_notte_precedente == ieri
        assert g.presenti_notte == g.totale - g.partiti
        assert sum(r.arrivati for r in g.righe) == g.arrivati
        assert sum(r.partiti for r in g.righe) == g.partiti
        assert 0 <= g.camere_occupate <= zp.CAMERE
        ieri = g.presenti_notte
    assert sum(g.arrivati for g in giorni) > 0     # un mese con del movimento
    assert zp.mese_inventato() == giorni           # deterministico


def test_l_app_riconosce_tutto_settembre_e_il_marcatore_non_e_un_giorno(
    zip_prova: Path,
) -> None:
    s = apri(zip_prova)
    try:
        assert s.mancanti(SETTEMBRE) == []
        assert s.non_riconosciuti == []
        assert s.di_prova
        primo = s.file_del(date(2026, 9, 1))
        assert primo is not None and primo.name == "schedine_istat_PROVA_20260901.txt"
    finally:
        s.pulisci()


# ─── il blocco ───────────────────────────────────────────────────────────────


def test_in_modalita_vera_lo_zip_di_prova_e_bloccato_in_prova_no(zip_prova: Path) -> None:
    s = apri(zip_prova)
    try:
        assert blocco_modalita_vera(s, prova=False) == (
            "Questo è lo zip di prova: serve solo in modalità prova."
        )
        assert blocco_modalita_vera(s, prova=True) is None
    finally:
        s.pulisci()


def test_il_portale_non_viene_nemmeno_aperto(zip_prova: Path) -> None:
    """Il muro sotto la finestra: ``carica_struttura`` si ferma prima di usare
    il browser. ``driver=None`` lo prova — se lo toccasse, esploderebbe."""
    s = apri(zip_prova)
    try:
        esito = carica_struttura(
            None,  # type: ignore[arg-type]
            id_turismatica="12345", etichetta="Prova", sorgente=s,
            periodo=SETTEMBRE, prova=False, strutture_note=frozenset(),
        )
    finally:
        s.pulisci()
    assert esito.saltata == MESSAGGIO_ZIP_DI_PROVA
    assert esito.giorni == {}
    assert Esito.CARICATO not in esito.giorni.values()


def test_senza_marcatore_i_file_inventati_restano_bloccati(
    zip_prova: Path, tmp_path: Path,
) -> None:
    """Il marcatore si può perdere (zip estratto a mano, file cancellato): i
    giorni inventati si riconoscono anche dal nome della struttura."""
    cartella = tmp_path / "estratto"
    with zipfile.ZipFile(zip_prova) as zf:
        zf.extractall(cartella)
    (cartella / zp.MARCATORE).unlink()
    s = apri(cartella)
    assert s.di_prova
    assert blocco_modalita_vera(s, prova=False) == MESSAGGIO_ZIP_DI_PROVA


def test_i_file_veri_non_sono_bloccati(tmp_path: Path) -> None:
    (tmp_path / "schedine_istat_99001_20260901.txt").write_bytes(
        b"Agriturismo Le Ginestre".ljust(255) + b"\r\n"
    )
    (tmp_path / "02092026.txt").write_text("x")
    s = apri(tmp_path)
    assert not s.di_prova
    assert blocco_modalita_vera(s, prova=False) is None
