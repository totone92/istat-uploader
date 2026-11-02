"""Prepara la cartella da cui MakeAppx fa il pacchetto MSIX per il Microsoft Store.

    python scripts/pacchetto_msix.py dist-msix/IstatUploader dist-msix/pacchetto

Dentro: la build a cartella di PyInstaller, il manifest e le icone. L'app gira a fiducia piena
(``runFullTrust``) e dichiara ``hostlab-turismatica://`` nel manifest. Nome ed editore arrivano
da ``STORE_NOME``, ``STORE_EDITORE`` e ``STORE_NOME_EDITORE``, che dà Partner Center: senza, i
valori di prova vanno bene solo per installare il pacchetto firmato in locale.
"""
from __future__ import annotations

import os
import shutil
import struct
import sys
import zlib
from pathlib import Path
from xml.sax.saxutils import quoteattr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.controlla_tag import versione_app  # noqa: E402
from uploader_turismatica.da_hostlab import SCHEMA  # noqa: E402

NOME_PROVA = "Fortitudo.IstatUploader"
EDITORE_PROVA = "CN=ProvaFortitudo"
NOME_EDITORE_PROVA = "Fortitudo"
#: Blu con una barra bianca: basta per pubblicare, un'icona vera si mette al posto di questa.
_FONDO, _SEGNO = (0x1F, 0x5F, 0xA8), (0xFF, 0xFF, 0xFF)

_MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap rescap">
  <Identity Name={nome} Publisher={editore} Version="{versione}.0" ProcessorArchitecture="x64"/>
  <Properties>
    <DisplayName>Istat Uploader</DisplayName>
    <PublisherDisplayName>{nome_editore}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.26100.0"/>
  </Dependencies>
  <Resources><Resource Language="it-IT"/></Resources>
  <Applications>
    <Application Id="IstatUploader" Executable="IstatUploader\\IstatUploader.exe"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="Istat Uploader" Description="Carica su Turismatica i movimenti ISTAT giornalieri"
                          BackgroundColor="transparent" Square150x150Logo="Assets\\Square150x150Logo.png"
                          Square44x44Logo="Assets\\Square44x44Logo.png"/>
      <Extensions>
        <uap:Extension Category="windows.protocol">
          <uap:Protocol Name="{schema}"><uap:DisplayName>HostLab Turismatica</uap:DisplayName></uap:Protocol>
        </uap:Extension>
      </Extensions>
    </Application>
  </Applications>
  <Capabilities>
    <Capability Name="internetClient"/>
    <rescap:Capability Name="runFullTrust"/>
  </Capabilities>
</Package>
"""


def manifest(ambiente: dict[str, str], versione: str) -> str:
    return _MANIFEST.format(
        nome=quoteattr(ambiente.get("STORE_NOME") or NOME_PROVA),
        editore=quoteattr(ambiente.get("STORE_EDITORE") or EDITORE_PROVA),
        nome_editore=(ambiente.get("STORE_NOME_EDITORE") or NOME_EDITORE_PROVA).replace("&", "&amp;"),
        versione=versione,
        schema=SCHEMA,
    )


def icona(lato: int) -> bytes:
    """Un PNG senza librerie: nel giro non serve altro."""
    righe = bytearray()
    for y in range(lato):
        righe.append(0)
        for x in range(lato):
            dentro = 0.4 * lato <= x < 0.6 * lato and 0.2 * lato <= y < 0.8 * lato
            righe.extend(_SEGNO if dentro else _FONDO)

    def blocco(tipo: bytes, dati: bytes) -> bytes:
        return (struct.pack(">I", len(dati)) + tipo + dati
                + struct.pack(">I", zlib.crc32(tipo + dati)))

    return (b"\x89PNG\r\n\x1a\n"
            + blocco(b"IHDR", struct.pack(">IIBBBBB", lato, lato, 8, 2, 0, 0, 0))
            + blocco(b"IDAT", zlib.compress(bytes(righe)))
            + blocco(b"IEND", b""))


def prepara(build: Path, destinazione: Path, ambiente: dict[str, str], versione: str) -> None:
    if destinazione.exists():
        shutil.rmtree(destinazione)
    shutil.copytree(build, destinazione / "IstatUploader")
    (destinazione / "AppxManifest.xml").write_text(manifest(ambiente, versione), encoding="utf-8")
    risorse = destinazione / "Assets"
    risorse.mkdir()
    for nome, lato in (("StoreLogo", 50), ("Square44x44Logo", 44), ("Square150x150Logo", 150)):
        (risorse / f"{nome}.png").write_bytes(icona(lato))


if __name__ == "__main__":
    prepara(Path(sys.argv[1]), Path(sys.argv[2]), dict(os.environ), versione_app())
