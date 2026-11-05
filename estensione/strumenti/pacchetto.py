"""Gli zip dell'estensione, solo src/: dist/istat-uploader-estensione-<versione>.zip per lo
Store (file in radice), e dist/IstatUploader-<versione>.zip per l'installazione a mano come
estensione non pacchettizzata, con tutto dentro una cartella «IstatUploader»: estratto sempre
nello stesso posto, Chrome la ritrova con lo stesso id e gli abbinamenti salvati."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
SRC = RADICE / "estensione" / "src"


CARTELLA_A_MANO = "IstatUploader"


def _zip(uscita: Path, cartella: str = "") -> Path:
    uscita.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(uscita, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(SRC.rglob("*")):
            if p.is_file():
                z.write(p, Path(cartella) / p.relative_to(SRC))
    return uscita


def versione() -> str:
    return str(json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))["version"])


def costruisci() -> Path:
    return _zip(RADICE / "dist" / f"istat-uploader-estensione-{versione()}.zip")


def costruisci_a_mano() -> Path:
    return _zip(RADICE / "dist" / f"{CARTELLA_A_MANO}-{versione()}.zip", CARTELLA_A_MANO)


if __name__ == "__main__":
    print(costruisci())
    print(costruisci_a_mano())
