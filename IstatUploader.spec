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
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

sys.path.insert(0, SPECPATH)  # noqa: F821
from scripts.firma_pe import firma_interni, togli_inutili  # noqa: E402

NOME = "IstatUploader"
_VERSIONE = re.search(
    r'^__version__ = "(\d+)\.(\d+)\.(\d+)"',
    (Path(SPECPATH) / "uploader_turismatica" / "__init__.py").read_text(encoding="utf-8"),  # noqa: F821
    re.MULTILINE,
).groups()
_V = ".".join(_VERSIONE)
_V4 = (*map(int, _VERSIONE), 0)
# Editore e versione nelle proprietà del file: un .exe anonimo è più sospetto per gli antivirus.
_INFO = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_V4, prodvers=_V4),
    kids=[
        StringFileInfo([StringTable("041004B0", [
            StringStruct("CompanyName", "Fortitudo"),
            StringStruct("FileDescription", "Istat Uploader"),
            StringStruct("FileVersion", _V),
            StringStruct("InternalName", NOME),
            StringStruct("LegalCopyright", "Licenza MIT"),
            StringStruct("OriginalFilename", f"{NOME}.exe"),
            StringStruct("ProductName", "Istat Uploader"),
            StringStruct("ProductVersion", _V),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x0410, 0x04B0])]),
    ],
)
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
# Via ciò che non parte mai; col certificato pronto, si firma ciò che resta senza firma
# (scripts/firma_pe.py). Senza certificato non cambia altro.
_FIRMATI = Path(SPECPATH) / "build" / "firmati"  # noqa: F821
a.binaries = firma_interni(togli_inutili(a.binaries), _FIRMATI)
a.datas = firma_interni(togli_inutili(a.datas), _FIRMATI)
pyz = PYZ(a.pure)

_comune = dict(
    name=NOME,
    debug=False,
    strip=False,
    upx=False,              # ⚠️ UPX comprime ma è il primo motivo di falso
                            # positivo antivirus: qui non vale lo scambio.
    console=False,          # è un'app con finestra, non un terminale
    icon=str(_ICONA) if _ICONA.is_file() else None,
    version=_INFO,
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
