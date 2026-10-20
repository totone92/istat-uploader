"""Quali file vanno a quale struttura: da soli quando è certo, chiedendo
quando non lo è — mai indovinando."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from uploader_turismatica.abbinamento import (
    StrutturaNota,
    abbina,
    id_dal_nome,
    intestazione,
    normalizza,
    raggruppa,
)

CASA_LAVANDA = StrutturaNota("12345", "CASA LAVANDA")
GINESTRE = StrutturaNota("23456", "Agriturismo Le Ginestre")
STRUTTURE = [CASA_LAVANDA, GINESTRE]


def _file(cartella: Path, nome_struttura: str, ident: str, giorni: int = 3) -> list[Path]:
    out = []
    for i in range(giorni):
        g = date(2026, 9, 1) + timedelta(days=i)
        p = cartella / f"schedine_istat_{ident}_{g:%Y%m%d}.txt"
        p.write_bytes(nome_struttura.encode().ljust(255) + b"\r\n\r\nPresenti notte precedente  0")
        out.append(p)
    return out


def test_il_nome_si_legge_dalla_prima_riga_e_l_id_dal_nome_del_file(tmp_path: Path) -> None:
    (f,) = _file(tmp_path, "Casa Lavanda", "99001", 1)
    assert intestazione(f) == "Casa Lavanda"
    assert id_dal_nome(f.name) == "99001"
    assert id_dal_nome("01092026.txt") is None


def test_normalizza_ignora_maiuscole_accenti_e_punteggiatura() -> None:
    assert normalizza("  Càsa  Lavanda, s.r.l. ") == "CASA LAVANDA S R L"


def test_nome_uguale_a_una_sola_struttura_si_abbina_da_solo(tmp_path: Path) -> None:
    gruppi = raggruppa(_file(tmp_path, "Casa Lavanda", "99001"), marcatore_prova=False)
    (a,) = abbina(gruppi, STRUTTURE, {})
    assert (a.id_turismatica, a.motivo) == ("12345", "nome")


def test_nome_diverso_si_chiede_con_la_piu_somigliante_in_cima(tmp_path: Path) -> None:
    gruppi = raggruppa(_file(tmp_path, "Le Ginestre B&B", "99002"), marcatore_prova=False)
    (a,) = abbina(gruppi, STRUTTURE, {})
    assert a.id_turismatica is None and a.motivo == "da_chiedere"
    assert a.proposte[0] == "23456"
    assert "Le Ginestre B&B" in a.domanda


def test_l_id_nel_nome_del_file_NON_e_il_numero_turismatica(tmp_path: Path) -> None:
    """⚠️ L'id nel nome è quello di beb.it o il CIN: se per caso coincide con
    un numero Turismatica, abbinare sarebbe indovinare."""
    gruppi = raggruppa(_file(tmp_path, "Un altro nome", "12345"), marcatore_prova=False)
    (a,) = abbina(gruppi, STRUTTURE, {})
    assert a.id_turismatica is None


def test_una_scelta_ricordata_vale_per_id_e_per_nome(tmp_path: Path) -> None:
    gruppi = raggruppa(_file(tmp_path, "Le Ginestre B&B", "99002"), marcatore_prova=False)
    (per_id,) = abbina(gruppi, STRUTTURE, {"id:99002": "23456"})
    (per_nome,) = abbina(gruppi, STRUTTURE, {"nome:LE GINESTRE B B": "23456"})
    assert per_id.id_turismatica == per_nome.id_turismatica == "23456"
    assert per_id.motivo == "ricordato"


def test_un_ricordo_verso_una_struttura_tolta_non_vale(tmp_path: Path) -> None:
    gruppi = raggruppa(_file(tmp_path, "Le Ginestre B&B", "99002"), marcatore_prova=False)
    (a,) = abbina(gruppi, STRUTTURE, {"id:99002": "77777"})
    assert a.id_turismatica is None


def test_due_strutture_nello_stesso_zip_non_si_mescolano(tmp_path: Path) -> None:
    """Gli stessi giorni per due strutture: indicizzare per giorno ne
    butterebbe via metà."""
    file = _file(tmp_path, "Casa Lavanda", "99001") + _file(tmp_path, "Agriturismo Le Ginestre", "99002")
    gruppi = raggruppa(file, marcatore_prova=False)
    assert len(gruppi) == 2 and all(len(g.per_giorno) == 3 for g in gruppi)
    assert sorted(a.id_turismatica or "" for a in abbina(gruppi, STRUTTURE, {})) == ["12345", "23456"]


def test_due_gruppi_sulla_stessa_struttura_si_chiedono_entrambi(tmp_path: Path) -> None:
    file = _file(tmp_path, "Casa Lavanda", "99001") + _file(tmp_path, "CASA LAVANDA", "99009")
    risultato = abbina(raggruppa(file, marcatore_prova=False), STRUTTURE, {})
    assert len(risultato) == 2
    assert all(a.id_turismatica is None and a.proposte[0] == "12345" for a in risultato)


def test_lo_zip_di_prova_non_si_abbina_mai_da_solo(tmp_path: Path) -> None:
    file = _file(tmp_path, "STRUTTURA DI PROVA", "PROVA")
    (a,) = abbina(raggruppa(file, marcatore_prova=False), [StrutturaNota("1", "STRUTTURA DI PROVA")],
                  {"id:PROVA": "1"})
    assert a.id_turismatica is None and a.motivo == "prova"
    assert "solo per vedere il giro in modalità prova" in a.domanda


def test_il_marcatore_rende_di_prova_tutto_lo_zip(tmp_path: Path) -> None:
    gruppi = raggruppa(_file(tmp_path, "Casa Lavanda", "99001"), marcatore_prova=True)
    assert all(g.di_prova for g in gruppi)
