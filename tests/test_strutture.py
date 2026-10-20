from __future__ import annotations

from pathlib import Path

from uploader_turismatica.strutture import Struttura, carica, salva


def test_giro_completo(tmp_path: Path) -> None:
    p = tmp_path / "strutture.json"
    salva([Struttura("12345", "Il Melograno", "C:/x/istat.zip")], p)
    assert carica(p) == [Struttura("12345", "Il Melograno", "C:/x/istat.zip")]


def test_file_assente_non_e_un_errore(tmp_path: Path) -> None:
    """Un errore all'avvio non ha rimedio per l'utente; una lista vuota sì."""
    assert carica(tmp_path / "mai_scritto.json") == []


def test_file_corrotto_non_e_un_errore(tmp_path: Path) -> None:
    p = tmp_path / "strutture.json"
    p.write_text("{questo non è json", encoding="utf-8")
    assert carica(p) == []


def test_le_voci_rotte_si_saltano_una_per_una(tmp_path: Path) -> None:
    """Una riga sbagliata non deve far perdere le altre."""
    p = tmp_path / "strutture.json"
    p.write_text(
        '[{"id_turismatica":"1","etichetta":"Buona"},'
        '{"manca_id":true},'
        '"nemmeno una voce"]',
        encoding="utf-8",
    )
    assert carica(p) == [Struttura("1", "Buona", "")]


def test_niente_credenziali_nel_file(tmp_path: Path) -> None:
    """⚠️ Non c'è niente da custodire: l'accesso è SPID e lo fa la persona."""
    p = tmp_path / "strutture.json"
    salva([Struttura("12345", "Il Melograno", "C:/x.zip")], p)
    testo = p.read_text(encoding="utf-8").lower()
    for parola in ("password", "token", "cookie", "spid", "codice", "pin"):
        assert parola not in testo


def test_la_validazione_parla_all_utente() -> None:
    assert Struttura("", "Nome").valida() == (
        "Manca il numero della struttura su Turismatica."
    )
    assert "non è un numero" in (Struttura("abc", "Nome").valida() or "")
    assert "Dai un nome" in (Struttura("1", "  ").valida() or "")
    assert Struttura("12345", "Il Melograno").valida() is None


def test_salvataggio_atomico_non_lascia_mezzi_file(tmp_path: Path) -> None:
    p = tmp_path / "strutture.json"
    salva([Struttura("1", "A")], p)
    salva([Struttura("2", "B")], p)
    assert carica(p) == [Struttura("2", "B")]
    assert list(tmp_path.glob("*.tmp")) == []
