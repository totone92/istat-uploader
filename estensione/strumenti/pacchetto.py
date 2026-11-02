"""Lo zip dell'estensione: dist/istat-uploader-estensione-<versione>.zip, solo src/."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
SRC = RADICE / "estensione" / "src"


def costruisci() -> Path:
    versione = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))["version"]
    uscita = RADICE / "dist" / f"istat-uploader-estensione-{versione}.zip"
    uscita.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(uscita, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(SRC.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(SRC))
    return uscita


if __name__ == "__main__":
    print(costruisci())
