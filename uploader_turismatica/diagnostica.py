"""«Questo computer è messo bene?» — da eseguire **prima** del primo giro vero.

Esiste perché il primo avvio su un PC che non conosciamo è il momento in cui si
scoprono le cose, e si scoprono nel modo peggiore: davanti al portale, con
l'utente che aspetta. Questo controllo le scopre prima, e in trenta secondi.

⚠️ **Non tocca Turismatica e non fa login**: apre e chiude Chrome, e basta.

Due modi di chiamarlo, stesso testo:

* il bottone «Verifica il computer» nella finestra;
* ``CaricaMovimentiTurismatica.exe --controllo``, che lo scrive anche in un
  file — perché un .exe senza console non ha dove stampare, e il file è l'unica
  cosa che si può poi mandare a qualcuno.
"""
from __future__ import annotations

import platform
import sys
from datetime import datetime
from pathlib import Path

from uploader_turismatica import __version__


def rapporto() -> str:
    """Il testo del controllo. Non solleva mai: ogni riga o dice ✓ o dice cosa fare."""
    righe: list[str] = [
        f"Controllo del computer — {datetime.now():%d/%m/%Y %H:%M}",  # noqa: DTZ005
        f"Uploader Turismatica v{__version__}",
        f"Sistema: {platform.system()} {platform.release()} ({platform.machine()})",
        f"Impacchettato: {'sì' if getattr(sys, 'frozen', False) else 'no (da sorgente)'}",
        "",
    ]

    # 1. le impostazioni si possono scrivere?
    from uploader_turismatica.strutture import cartella_impostazioni, percorso_file

    try:
        cartella_impostazioni().mkdir(parents=True, exist_ok=True)
        prova = cartella_impostazioni() / ".prova"
        prova.write_text("x", encoding="utf-8")
        prova.unlink()
        righe.append(f"✓  Posso ricordare le strutture  ({percorso_file()})")
    except OSError as exc:
        righe.append(
            f"✗  NON posso salvare le strutture in {cartella_impostazioni()}\n"
            f"   Le dovrai ridichiarare ogni volta. ({exc})"
        )

    # 2. la finestra si apre?
    try:
        import tkinter

        radice = tkinter.Tk()
        radice.withdraw()
        righe.append(f"✓  La finestra si apre  (Tk {radice.tk.call('info', 'patchlevel')})")
        radice.destroy()
    except Exception as exc:  # noqa: BLE001
        righe.append(f"✗  La finestra NON si apre: {exc}")

    # 3. Chrome + il componente che lo guida
    righe.append("")
    righe.append("Provo ad aprire Chrome (si apre e si chiude da solo)…")
    try:
        from uploader_turismatica.chrome import ChromeNonDisponibile, apri_chrome

        driver = apri_chrome()
        try:
            versione = driver.capabilities.get("browserVersion", "?")
            righe.append(f"✓  Chrome si apre  (versione {versione})")
        finally:
            driver.quit()
    except ChromeNonDisponibile as exc:
        righe.append(f"✗  {exc}")
    except Exception as exc:  # noqa: BLE001
        righe.append(f"✗  Chrome non si è aperto: {exc}")

    righe.append("")
    if any(r.startswith("✗") for r in righe):
        righe.append("C'è qualcosa da sistemare: leggi le righe con ✗ qui sopra.")
    else:
        righe.append("Tutto a posto: il computer è pronto.")
    return "\n".join(righe)


def da_riga_di_comando() -> int:
    """``--controllo``: scrive il rapporto su file **e** su stdout.

    Il file serve perché un .exe senza console non ha dove stampare: da
    PowerShell non si vedrebbe niente e sembrerebbe che non sia successo
    nulla."""
    testo = rapporto()
    from uploader_turismatica.strutture import cartella_impostazioni

    destinazione: Path | None = None
    try:
        cartella_impostazioni().mkdir(parents=True, exist_ok=True)
        destinazione = cartella_impostazioni() / "controllo.txt"
        destinazione.write_text(testo, encoding="utf-8")
    except OSError:
        destinazione = None

    print(testo)
    if destinazione is not None:
        print(f"\n(scritto anche in {destinazione})")
    return 0 if "✗" not in testo else 1
