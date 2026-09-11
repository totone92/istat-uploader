"""Da dove arrivano i file — la parte che si può provare davvero.

⚠️ Il resto (Chrome, SPID, il portale) **non è provabile senza il portale
vero**: vedi README → «Cosa non ho potuto provare». Per questo qui si prova
tanto: è dove i difetti si possono ancora prendere.
"""
from __future__ import annotations

import zipfile
from datetime import date
from pathlib import Path

import pytest

from uploader_turismatica.periodo import Periodo, mese
from uploader_turismatica.sorgente import SorgenteNonValida, apri, data_dal_nome


def test_i_due_nomi_veri_danno_lo_stesso_giorno() -> None:
    """HostLab scrive AAAAMMGG dentro un nome lungo, lo script originale
    GGMMAAAA nudo: due convenzioni, un solo giorno."""
    assert data_dal_nome("schedine_istat_99001_20260901.txt") == date(2026, 9, 1)
    assert data_dal_nome("01092026.txt") == date(2026, 9, 1)


def test_lordine_dei_tentativi_e_deciso_dal_NOME_non_dalla_plausibilita() -> None:
    """⭐ Le due convenzioni sono ambigue fra loro: `01022026` è il 1° febbraio
    letto GGMMAAAA. Si decide dal prefisso, che è un fatto — non indovinando
    quale data «sembra giusta»."""
    assert data_dal_nome("01022026.txt") == date(2026, 2, 1)
    assert data_dal_nome("schedine_istat_9_20260201.txt") == date(2026, 2, 1)


def test_un_nome_che_non_dice_una_data_non_si_carica() -> None:
    """Non si va a caccia di otto cifre in un nome qualunque: caricare un file
    su una riga indovinata è una dichiarazione falsa fatta a nome del gestore."""
    for nome in ("appunti.txt", "movimenti.txt", "report 2026.txt", "3009.txt"):
        assert data_dal_nome(nome) is None


def test_data_impossibile_non_passa() -> None:
    assert data_dal_nome("32092026.txt") is None
    assert data_dal_nome("schedine_istat_1_20261332.txt") is None


def test_il_file_estratto_due_volte_finisce_fra_i_non_riconosciuti(
    tmp_path: Path,
) -> None:
    """Windows chiama il secondo `... (1).txt`, e quel nome NON dichiara più una
    data: la parentesi sta fra la data e l'estensione.

    Finisce quindi fra i non riconosciuti, ed è la scelta giusta: allentare la
    regola per acchiapparlo la farebbe acchiappare anche altro, e l'originale
    con lo stesso giorno è lì accanto. Se invece è rimasto solo lui, il giorno
    risulta «file mancante» e il riepilogo dice di riscaricarlo — un esito
    recuperabile, non un file caricato sulla riga sbagliata."""
    (tmp_path / "schedine_istat_99001_20260901 (1).txt").write_text("x")
    s = apri(tmp_path)
    assert s.per_giorno == {}
    assert s.non_riconosciuti == ["schedine_istat_99001_20260901 (1).txt"]


def test_cartella_con_file_veri(tmp_path: Path) -> None:
    for g in (1, 2, 3):
        (tmp_path / f"schedine_istat_99001_202609{g:02d}.txt").write_text("dati")
    s = apri(tmp_path)
    assert sorted(s.per_giorno) == [date(2026, 9, g) for g in (1, 2, 3)]
    assert s.primo == date(2026, 9, 1)
    assert s.ultimo == date(2026, 9, 3)


def test_zip_di_hostlab(tmp_path: Path) -> None:
    """Lo zip è quello che HostLab fa scaricare: file .txt piatti, niente
    cartelle."""
    z = tmp_path / "istat_2026-09.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for g in (1, 2):
            zf.writestr(f"schedine_istat_99001_202609{g:02d}.txt", "dati")
    s = apri(z)
    try:
        assert sorted(s.per_giorno) == [date(2026, 9, 1), date(2026, 9, 2)]
        assert s.file_del(date(2026, 9, 1)).read_text() == "dati"
    finally:
        s.pulisci()


def test_zip_riaperto_e_ricompresso_da_windows(tmp_path: Path) -> None:
    """⭐ Il caso normale, non quello strano: chi apre uno zip su Windows e lo
    ricomprime si ritrova i file dentro una cartella con lo stesso nome.
    Pretendere che stiano in cima farebbe fallire proprio l'uso più comune."""
    z = tmp_path / "istat.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("istat_2026-09/schedine_istat_99001_20260901.txt", "dati")
    s = apri(z)
    try:
        assert list(s.per_giorno) == [date(2026, 9, 1)]
    finally:
        s.pulisci()


def test_lo_zip_non_puo_scrivere_fuori_dalla_sua_cartella(tmp_path: Path) -> None:
    """⚠️ `zip slip`: un percorso che risale scriverebbe altrove sul PC. Lo zip
    lo fa HostLab, ma il campo lo riempie l'utente e può scegliere qualunque
    file."""
    z = tmp_path / "cattivo.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../../fuori_20260901.txt", "x")
        zf.writestr("schedine_istat_1_20260902.txt", "buono")
    s = apri(z)
    try:
        assert not (tmp_path.parent / "fuori_20260901.txt").exists()
        assert list(s.per_giorno) == [date(2026, 9, 2)]
    finally:
        s.pulisci()


def test_solo_i_txt_escono_dallo_zip(tmp_path: Path) -> None:
    z = tmp_path / "misto.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("schedine_istat_1_20260901.txt", "buono")
        zf.writestr("virus.exe", "MZ")
    s = apri(z)
    try:
        assert s._temp is not None
        assert [p.name for p in s._temp.rglob("*")] == [
            "schedine_istat_1_20260901.txt"
        ]
    finally:
        s.pulisci()


def test_mancanti_e_presenti_sul_periodo(tmp_path: Path) -> None:
    for g in (1, 2, 5):
        (tmp_path / f"schedine_istat_1_202609{g:02d}.txt").write_text("x")
    s = apri(tmp_path)
    p = Periodo(dal=date(2026, 9, 1), al=date(2026, 9, 5))
    assert s.presenti(p) == [date(2026, 9, g) for g in (1, 2, 5)]
    assert s.mancanti(p) == [date(2026, 9, 3), date(2026, 9, 4)]


def test_percorso_che_non_esiste_lo_dice_con_parole(tmp_path: Path) -> None:
    with pytest.raises(SorgenteNonValida, match="Non trovo"):
        apri(tmp_path / "mai_esistito.zip")


def test_uno_zip_rotto_lo_dice_con_parole(tmp_path: Path) -> None:
    rotto = tmp_path / "rotto.zip"
    rotto.write_text("non sono uno zip")
    with pytest.raises(SorgenteNonValida, match="danneggiato"):
        apri(rotto)


def test_pulisci_e_idempotente(tmp_path: Path) -> None:
    z = tmp_path / "z.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("schedine_istat_1_20260901.txt", "x")
    s = apri(z)
    temp = s._temp
    assert temp is not None and temp.exists()
    s.pulisci()
    s.pulisci()
    assert not temp.exists()


def test_un_mese_intero_si_indicizza(tmp_path: Path) -> None:
    settembre = mese(2026, 9)
    for g in settembre.giorni:
        (tmp_path / f"schedine_istat_99001_{g:%Y%m%d}.txt").write_text("x")
    s = apri(tmp_path)
    assert len(s.per_giorno) == 30
    assert s.mancanti(settembre) == []
