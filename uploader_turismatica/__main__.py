"""Punto d'ingresso.

``--controllo`` fa il controllo del computer e non apre la finestra: è la prima
cosa da eseguire su un PC nuovo (vedi ``diagnostica.py``).
"""
import sys


def main() -> int:
    if "--controllo" in sys.argv[1:]:
        from uploader_turismatica.diagnostica import da_riga_di_comando

        return da_riga_di_comando()
    from uploader_turismatica.app import avvia

    avvia()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
