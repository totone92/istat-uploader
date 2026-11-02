"""I binari dentro l'.exe, per Smart App Control.

Smart App Control non guarda solo l'.exe: controlla ogni DLL, ``.pyd`` ed eseguibile che
parte, anche quelli che PyInstaller estrae all'avvio. Firmare il guscio non basta: nella
v1.6.0 c'erano 7 binari interni senza firma, ``selenium-manager.exe`` compreso.

Dalla ricetta: ``togli_inutili`` e ``firma_interni``. Dal giro di GitHub, a build finita:

    python scripts/firma_pe.py dist/IstatUploader.exe
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
_FIRMA = RADICE / "scripts" / "firma.ps1"

# Mai caricati da un .exe a 64 bit per Windows: ogni binario in meno è uno da firmare in meno.
# Non i WebView2Loader degli altri processori: pywebview pretende che ci siano, e sono già
# firmati da Microsoft.
_INUTILI = (
    "/dlls/x86/", "webbrowserinterop.x86", "/common/linux/", "/common/macos/",
)


def inutile(destinazione: str) -> bool:
    return any(p in destinazione.replace("\\", "/").lower() for p in _INUTILI)


def togli_inutili(voci: list) -> list:
    return [v for v in voci if not inutile(v[0])]


def stato_firma(dati: bytes) -> bool | None:
    """``True`` se il PE ha una firma, ``False`` se no, ``None`` se non è un PE."""
    if len(dati) < 64 or dati[:2] != b"MZ":
        return None
    pe = struct.unpack_from("<I", dati, 60)[0]
    if dati[pe:pe + 4] != b"PE\0\0":
        return None
    opzionale = pe + 24
    magic = struct.unpack_from("<H", dati, opzionale)[0]
    # La tabella dei certificati è la voce 4 delle directory (8 byte l'una).
    voce = opzionale + (96 if magic == 0x10B else 112) + 4 * 8
    return struct.unpack_from("<I", dati, voce + 4)[0] > 0


def firma_interni(voci: list, cartella: Path) -> list:
    """Firma una copia dei PE senza firma e rimanda la voce alla copia."""
    if os.environ.get("FIRMA_PRONTA") != "1":
        return voci
    nuove = []
    for destinazione, sorgente, tipo in voci:
        if stato_firma(Path(sorgente).read_bytes()) is False:
            copia = cartella / destinazione
            copia.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sorgente, copia)
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                 "-File", str(_FIRMA), str(copia)],
                check=True,
            )
            sorgente = str(copia)
        nuove.append((destinazione, sorgente, tipo))
    return nuove


def senza_firma(exe: Path) -> list[str]:
    from PyInstaller.archive.readers import CArchiveReader

    archivio = CArchiveReader(str(exe))
    mancano = []
    for nome in archivio.toc:
        if nome.lower().endswith((".pyz", ".pkg")):
            continue
        dati = archivio.extract(nome)
        if isinstance(dati, tuple):
            dati = dati[1]
        if dati and stato_firma(dati) is False:
            mancano.append(nome)
    return mancano


def main(argomenti: list[str]) -> int:
    mancano = senza_firma(Path(argomenti[0]))
    print("\n".join(f"senza firma: {n}" for n in mancano) or "binari interni: tutti firmati")
    return 1 if mancano else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
