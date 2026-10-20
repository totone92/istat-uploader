"""Punto d'ingresso.

* senza argomenti: la finestra (``finestra.avvia``);
* ``--controllo``: il controllo del computer, scritto anche su file (vedi
  ``diagnostica.py``) — la prima cosa da fare su un PC nuovo;
* ``--autoverifica <file>`` e ``--autoverifica-finestra <file>``: per la build
  automatica. Il primo controlla che nell'.exe ci sia tutto, il secondo apre la
  finestra vera e aspetta che l'interfaccia parli col Python.
"""
import sys
from pathlib import Path


def main() -> int:
    argomenti = sys.argv[1:]
    if argomenti[:1] == ["--autoverifica"] and len(argomenti) == 2:
        from uploader_turismatica.diagnostica import autoverifica_da_riga_di_comando

        return autoverifica_da_riga_di_comando(Path(argomenti[1]))
    if argomenti[:1] == ["--autoverifica-finestra"] and len(argomenti) == 2:
        from uploader_turismatica.finestra import autoverifica_finestra

        return autoverifica_finestra(Path(argomenti[1]))
    if "--controllo" in argomenti:
        from uploader_turismatica.diagnostica import da_riga_di_comando

        return da_riga_di_comando()
    from uploader_turismatica.finestra import avvia

    return avvia()


if __name__ == "__main__":
    raise SystemExit(main())
