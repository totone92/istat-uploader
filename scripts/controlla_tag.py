"""Il tag che sta per diventare una Release è la versione dell'app?

    python scripts/controlla_tag.py v1.1.0

Legge ``__version__`` dal **testo** di ``uploader_turismatica/__init__.py``,
senza importare il pacchetto: un import può stampare altro (log, avvisi) e la
versione arriverebbe sporca. Fa il confronto qui e non nello shell del runner:
in PowerShell ``"…$app: …"`` non è nemmeno uno script valido (``$app:`` si
legge come variabile con ambito), ed è così che è fallito il primo tag v1.1.0.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

INIT = Path(__file__).resolve().parent.parent / "uploader_turismatica" / "__init__.py"
_VERSIONE = re.compile(r"""^__version__\s*=\s*["']([^"']+)["']\s*$""", re.MULTILINE)


def versione_app(init: Path = INIT) -> str:
    m = _VERSIONE.search(init.read_text(encoding="utf-8"))
    if m is None:
        raise SystemExit(f"non trovo __version__ in {init.name}")
    return m.group(1)


def controlla(tag: str, versione: str) -> str | None:
    """``None`` se combaciano, altrimenti il messaggio con i due valori esatti."""
    if tag.strip() == f"v{versione}":
        return None
    return (
        f"il tag è {tag!r} ma __version__ è {versione!r} (atteso il tag "
        f"{'v' + versione!r}): allinea uploader_turismatica/__init__.py"
    )


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("uso: python scripts/controlla_tag.py vX.Y.Z", file=sys.stderr)
        return 2
    errore = controlla(argv[0], versione_app())
    if errore:
        print(errore, file=sys.stderr)
        return 1
    print(f"ok: tag {argv[0]!r} = __version__ {versione_app()!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
