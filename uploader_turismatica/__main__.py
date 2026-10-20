"""Punto d'ingresso.

``--controllo`` fa il controllo del computer e non apre la finestra: è la prima
cosa da eseguire su un PC nuovo (vedi ``diagnostica.py``). ``--autoverifica
<file>`` è per la build automatica.
"""
import sys


def main() -> int:
    argomenti = sys.argv[1:]
    if argomenti[:1] == ["--autoverifica"] and len(argomenti) == 2:
        from pathlib import Path

        from uploader_turismatica.diagnostica import autoverifica_da_riga_di_comando

        return autoverifica_da_riga_di_comando(Path(argomenti[1]))
    if "--controllo" in argomenti:
        from uploader_turismatica.diagnostica import da_riga_di_comando

        return da_riga_di_comando()
    from uploader_turismatica.app import avvia

    avvia()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
