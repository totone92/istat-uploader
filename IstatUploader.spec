# -*- mode: python ; coding: utf-8 -*-
"""Ricetta PyInstaller — un solo file .exe, da scaricare e aprire.

Si costruisce **su Windows**: PyInstaller non compila per un sistema diverso da
quello su cui gira (impacchetta l'interprete e le librerie di QUELLA macchina).
Da Linux esce un binario Linux, non un .exe. Due strade, stessa ricetta:

* la build automatica su GitHub (``.github/workflows/build-windows.yml``);
* ``build.bat`` sul PC Windows (vedi ``BUILD_WINDOWS.md``).

Esce ``dist\IstatUploader.exe``. L'icona è ``assets\IstatUploader.ico`` **se
c'è**: senza, l'.exe ha quella standard e si costruisce lo stesso.

⚠️ `onefile` = un .exe solo, che si scarica e si apre — ed è quello che serve
qui. Il prezzo è che a ogni avvio si estrae in una cartella temporanea, quindi
la prima schermata arriva dopo qualche secondo. Per la strada opposta (avvio
immediato, ma una cartella da scompattare) vedi `ONEDIR` qui sotto.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

NOME = "IstatUploader"
_ICONA = Path(SPECPATH) / "assets" / f"{NOME}.ico"  # noqa: F821 — lo dà PyInstaller

ONEDIR = False        # True = cartella + .exe dentro, invece del file unico

a = Analysis(
    ["uploader_turismatica/__main__.py"],
    # La cartella del progetto: il pacchetto si importa da qui, senza
    # installarlo.
    pathex=[SPECPATH],  # noqa: F821
    binaries=[],
    # ⚠️ Selenium porta dentro l'**eseguibile di Selenium Manager**, che non è
    # un modulo Python: senza questi file il .exe parte e poi non trova il
    # driver di Chrome. pywebview porta le DLL di WebView2 e i suoi JavaScript.
    # ``ui/`` è l'interfaccia (HTML, CSS, JS): senza, la finestra è bianca.
    datas=(
        collect_data_files("selenium")
        + collect_data_files("webview")
        + [(str(Path(SPECPATH) / "uploader_turismatica" / "ui"), "uploader_turismatica/ui")]  # noqa: F821
    ),
    # ⚠️ **`collect_submodules` e non una lista scritta a mano**, ed è una cosa
    # misurata, non prudenza: con l'elenco a mano il pacchetto si costruiva
    # benissimo e poi moriva con
    #     No module named 'selenium.webdriver.chrome.webdriver'
    # — cioè partiva, mostrava la finestra, e falliva **nel momento peggiore**,
    # quando l'utente preme Avvia. Selenium risolve i suoi moduli per nome a
    # runtime, quindi PyInstaller non li vede seguendo gli import.
    #
    # Lo stesso vale per pywebview: sceglie la piattaforma (WinForms + Edge
    # Chromium su Windows) per nome a runtime. Le piattaforme degli altri
    # sistemi restano fuori: su Windows non si importano nemmeno.
    hiddenimports=(
        collect_submodules("selenium")
        + collect_submodules(
            "webview",
            filter=lambda n: not any(
                x in n for x in ("cocoa", "gtk", "qt", "android", "cef", "mshtml")
            ),
        )
        + ["clr", "clr_loader", "bottle", "proxy_tools"]
        + collect_submodules("uploader_turismatica")
    ),
    hookspath=[],
    runtime_hooks=[],
    # Roba che non usiamo e che pesa: toglierla dimezza il file e riduce le
    # occasioni di falso positivo antivirus.
    excludes=[
        "numpy", "pandas", "matplotlib", "PIL", "scipy", "tkinter",
        "PyQt5", "PyQt6", "PySide2", "PySide6",
        "test", "unittest", "pydoc_data", "lib2to3",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

_comune = dict(
    name=NOME,
    debug=False,
    strip=False,
    upx=False,              # ⚠️ UPX comprime ma è il primo motivo di falso
                            # positivo antivirus: qui non vale lo scambio.
    console=False,          # è un'app con finestra, non un terminale
    icon=str(_ICONA) if _ICONA.is_file() else None,
)

if ONEDIR:
    exe = EXE(pyz, a.scripts, exclude_binaries=True, **_comune)
    coll = COLLECT(
        exe, a.binaries, a.datas, strip=False, upx=False,
        name=NOME,
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        runtime_tmpdir=None, **_comune,
    )
