from __future__ import annotations

from pathlib import Path

from uploader_turismatica import installazione as inst


class RegistroFinto:
    def __init__(self) -> None:
        self.valori: dict[tuple[str, str], str | int] = {}

    def leggi(self, chiave: str, nome: str = "") -> str | None:
        valore = self.valori.get((chiave, nome))
        return None if valore is None else str(valore)

    def scrivi(self, chiave: str, nome: str, valore: str | int) -> None:
        self.valori[(chiave, nome)] = valore

    def cancella(self, chiave: str) -> None:
        self.valori = {k: v for k, v in self.valori.items()
                       if k[0] != chiave and not k[0].startswith(chiave + "\\")}


def test_si_copia_se_manca_o_se_quello_installato_e_piu_vecchio(tmp_path: Path) -> None:
    exe = tmp_path / "a.exe"
    assert inst.va_copiato(exe, None, "1.6.1")
    exe.write_bytes(b"x")
    assert inst.va_copiato(exe, "1.6.0", "1.6.1")
    assert inst.va_copiato(exe, None, "1.6.1")
    assert not inst.va_copiato(exe, "1.6.1", "1.6.1")
    assert not inst.va_copiato(exe, "1.10.0", "1.9.0")


def test_la_versione_installata_si_legge_anche_dall_installer_vecchio() -> None:
    r = RegistroFinto()
    assert inst.versione_installata(r) is None
    r.scrivi(inst.VOCE_INNO, "DisplayVersion", "1.6.0")
    assert inst.versione_installata(r) == "1.6.0"
    r.scrivi(inst.VOCE, "DisplayVersion", "1.6.1")
    assert inst.versione_installata(r) == "1.6.1"


def test_l_indirizzo_punta_all_exe_col_comando_che_si_aspetta_windows() -> None:
    r = RegistroFinto()
    inst.registra_indirizzo(r, Path("C:/x/IstatUploader.exe"))
    comando = r.leggi(r"Software\Classes\hostlab-turismatica\shell\open\command")
    assert comando == f'"{Path("C:/x/IstatUploader.exe")}" "%1"'
    assert r.leggi(r"Software\Classes\hostlab-turismatica", "URL Protocol") == ""


def test_la_voce_in_app_installate_sa_disinstallare() -> None:
    r = RegistroFinto()
    exe = Path("C:/x/IstatUploader.exe")
    inst.registra_voce(r, exe)
    assert r.leggi(inst.VOCE, "UninstallString") == f'"{exe}" --disinstalla'
    assert r.leggi(inst.VOCE, "DisplayName") == "Istat Uploader"


def test_passare_dall_installer_toglie_i_doppioni_e_non_l_exe(tmp_path: Path) -> None:
    r = RegistroFinto()
    r.scrivi(inst.VOCE_INNO, "DisplayName", "Istat Uploader")
    cartella = tmp_path / "prog"
    cartella.mkdir()
    (cartella / inst.NOME_EXE).write_bytes(b"x")
    (cartella / "unins000.exe").write_bytes(b"x")
    (cartella / "unins000.dat").write_bytes(b"x")
    programmi = tmp_path / "start"
    (programmi / inst.NOME_APP).mkdir(parents=True)
    (programmi / inst.NOME_APP / "Istat Uploader.lnk").write_bytes(b"x")

    inst.togli_installer_vecchio(r, cartella, programmi)

    assert r.leggi(inst.VOCE_INNO, "DisplayName") is None
    assert [p.name for p in cartella.iterdir()] == [inst.NOME_EXE]
    assert not (programmi / inst.NOME_APP).exists()


def test_senza_installer_vecchio_non_tocca_niente(tmp_path: Path) -> None:
    programmi = tmp_path / inst.NOME_APP
    programmi.mkdir()
    inst.togli_installer_vecchio(RegistroFinto(), tmp_path, tmp_path)
    assert programmi.exists()


def test_la_copia_scavalca_e_un_exe_in_uso_si_accantona(tmp_path: Path, monkeypatch) -> None:
    sorgente = tmp_path / "scaricato.exe"
    sorgente.write_bytes(b"nuovo")
    destinazione = tmp_path / "prog" / inst.NOME_EXE
    inst.copia(sorgente, destinazione)
    assert destinazione.read_bytes() == b"nuovo"

    vero = inst.os.replace
    bloccato = {"una_volta": True}

    def replace(a: object, b: object) -> None:
        if bloccato.pop("una_volta", False):
            raise PermissionError("in uso")
        vero(a, b)  # type: ignore[arg-type]

    sorgente.write_bytes(b"ancora piu nuovo")
    monkeypatch.setattr(inst.os, "replace", replace)
    inst.copia(sorgente, destinazione)
    monkeypatch.undo()
    assert destinazione.read_bytes() == b"ancora piu nuovo"
    avanzi = list(destinazione.parent.glob("*.vecchio"))
    assert [a.read_bytes() for a in avanzi] == [b"nuovo"]
    inst.togli_avanzi(destinazione.parent)
    assert not list(destinazione.parent.glob("*.vecchio"))


def test_disinstallare_toglie_indirizzo_voce_e_collegamenti(tmp_path: Path) -> None:
    r = RegistroFinto()
    exe = Path("C:/x/IstatUploader.exe")
    inst.registra_indirizzo(r, exe)
    inst.registra_voce(r, exe)
    start, desktop = tmp_path / "start", tmp_path / "desk"
    start.mkdir()
    desktop.mkdir()
    (start / "Istat Uploader.lnk").write_bytes(b"x")
    (desktop / "Istat Uploader.lnk").write_bytes(b"x")
    (desktop / "Altro.lnk").write_bytes(b"x")

    inst.togli_registrazioni(r, start, desktop)

    assert r.valori == {}
    assert not list(start.iterdir())
    assert [p.name for p in desktop.iterdir()] == ["Altro.lnk"]


def test_da_sorgente_o_fuori_da_windows_non_fa_niente() -> None:
    assert inst.allinea([], RegistroFinto()) is False
