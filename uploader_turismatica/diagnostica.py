"""«Questo computer è messo bene?» — da eseguire **prima** del primo giro vero.

Esiste perché il primo avvio su un PC che non conosciamo è il momento in cui si
scoprono le cose, e si scoprono nel modo peggiore: davanti al portale, con
l'utente che aspetta. Questo controllo le scopre prima, e in trenta secondi.

⚠️ **Non tocca Turismatica e non fa login**: apre e chiude Chrome, e basta.

Due modi di chiamarlo, stesso testo:

* il bottone «Verifica il computer» nella finestra;
* ``IstatUploader.exe --controllo``, che lo scrive anche in un
  file — perché un .exe senza console non ha dove stampare, e il file è l'unica
  cosa che si può poi mandare a qualcuno.

C'è anche ``--autoverifica <file>``, che **non è per l'utente**: la usa la
build su GitHub per controllare l'.exe appena costruito senza aprire né Chrome
né una finestra (vedi ``autoverifica``).
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

    # 2. la finestra: WebView2 (solo Windows)
    from uploader_turismatica.finestra import URL_WEBVIEW2, webview2_presente

    presente = webview2_presente()
    if presente is True:
        righe.append("✓  Il componente per la finestra c'è  (Microsoft Edge WebView2)")
    elif presente is False:
        righe.append(
            "✗  Manca «Microsoft Edge WebView2», che serve alla finestra.\n"
            f"   Installalo da {URL_WEBVIEW2} e riapri il programma."
        )

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


def autoverifica() -> list[str]:
    """Le parti dell'eseguibile che si sono già perse una volta impacchettando.

    Non apre niente: controlla che **dentro** l'.exe ci siano i moduli che
    Selenium carica per nome a runtime (senza, l'app partiva e moriva al primo
    «Avvia» con ``No module named 'selenium.webdriver.chrome.webdriver'``),
    l'eseguibile di Selenium Manager (che non è un modulo Python e va copiato a
    parte), pywebview col suo motore e i file dell'interfaccia. Ritorna i problemi: lista vuota = a posto."""
    problemi: list[str] = []
    import importlib

    moduli = [
        "webview",
        "webview.dom",
        "selenium.webdriver.chrome.webdriver",
        "selenium.webdriver.chrome.service",
        "selenium.webdriver.support.expected_conditions",
        "uploader_turismatica.api",
        "uploader_turismatica.finestra",
        "uploader_turismatica.portale",
        "uploader_turismatica.sessione",
    ]
    if sys.platform.startswith("win"):
        # Il motore della finestra su Windows: pythonnet + WinForms + WebView2.
        moduli += ["clr", "webview.platforms.winforms", "webview.platforms.edgechromium"]
    for modulo in moduli:
        try:
            importlib.import_module(modulo)
        except Exception as exc:  # noqa: BLE001
            problemi.append(f"manca {modulo}: {exc}")
    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager

        binario = Path(SeleniumManager._get_binary())  # noqa: SLF001
        if not binario.is_file():
            problemi.append(f"Selenium Manager non è nel pacchetto ({binario.name})")
    except Exception as exc:  # noqa: BLE001
        problemi.append(f"Selenium Manager non è nel pacchetto: {exc}")
    from uploader_turismatica.finestra import UI

    for nome in ("index.html", "app.css", "app.js"):
        if not (UI / nome).is_file():
            problemi.append(f"l'interfaccia non è nel pacchetto: manca ui/{nome}")
    return problemi


def autoverifica_da_riga_di_comando(destinazione: Path) -> int:
    problemi = autoverifica()
    testo = "\n".join(
        [f"Istat Uploader v{__version__} — autoverifica",
         f"impacchettato: {'sì' if getattr(sys, 'frozen', False) else 'no'}"]
        + ([f"✗ {p}" for p in problemi] or ["✓ tutto dentro"])
    )
    destinazione.write_text(testo + "\n", encoding="utf-8")
    return 1 if problemi else 0
