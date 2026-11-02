from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.pacchetto_msix import icona, manifest, prepara

_NS = {"f": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
       "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10"}


def test_il_manifest_dichiara_indirizzo_fiducia_e_versione_a_quattro_numeri() -> None:
    radice = ET.fromstring(manifest({}, "1.6.1"))
    assert radice.find("f:Identity", _NS).get("Version") == "1.6.1.0"
    assert radice.find(".//uap:Protocol", _NS).get("Name") == "hostlab-turismatica"
    app = radice.find(".//f:Application", _NS)
    assert app.get("EntryPoint") == "Windows.FullTrustApplication"
    assert "runFullTrust" in manifest({}, "1.6.1")


def test_nome_ed_editore_di_partner_center_prendono_il_posto_di_quelli_di_prova() -> None:
    radice = ET.fromstring(manifest(
        {"STORE_NOME": "123.Istat", "STORE_EDITORE": 'CN="A & B"', "STORE_NOME_EDITORE": "A & B"},
        "1.6.1",
    ))
    assert radice.find("f:Identity", _NS).get("Name") == "123.Istat"
    assert radice.find("f:Identity", _NS).get("Publisher") == 'CN="A & B"'
    assert radice.find(".//f:PublisherDisplayName", _NS).text == "A & B"


def test_le_icone_sono_png_della_misura_giusta() -> None:
    dati = icona(44)
    assert dati[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(dati[16:20], "big") == 44


def test_la_cartella_ha_build_manifest_e_icone(tmp_path: Path) -> None:
    build = tmp_path / "build"
    build.mkdir()
    (build / "IstatUploader.exe").write_bytes(b"x")
    destinazione = tmp_path / "pacchetto"
    prepara(build, destinazione, {}, "1.6.1")
    assert (destinazione / "IstatUploader" / "IstatUploader.exe").exists()
    assert (destinazione / "AppxManifest.xml").exists()
    assert (destinazione / "Assets" / "Square44x44Logo.png").exists()
