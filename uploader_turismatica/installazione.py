"""L'.exe si installa da solo, per l'utente: niente installer e niente richiesta da amministratore.

Al primo avvio si copia in ``%LOCALAPPDATA%\\Programs\\IstatUploader``, la stessa cartella che
usava l'installer della v1.6.0, così chi l'aveva non si ritrova due copie. Poi lascia il posto
alla copia installata, con gli stessi argomenti (il gettone di HostLab compreso). A ogni avvio
riscrive l'indirizzo ``hostlab-turismatica://`` verso il percorso giusto: registro utente, quindi
nessun UAC. La disinstallazione è la voce in «App installate» (``--disinstalla``).

Le impostazioni in ``%APPDATA%`` restano: l'installer faceva lo stesso.

⚠️ **Niente qui deve impedire di lavorare**: se la copia non riesce il programma parte da dove
sta, con l'indirizzo che punta lì. Dentro un pacchetto MSIX (Microsoft Store) non si fa niente:
l'indirizzo lo dichiara il manifest, gli aggiornamenti li dà lo Store.
"""
from __future__ import annotations

import ctypes
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

from uploader_turismatica import __version__
from uploader_turismatica.da_hostlab import SCHEMA

log = logging.getLogger(__name__)

NOME_EXE = "IstatUploader.exe"
NOME_APP = "Istat Uploader"
_CLASSI = rf"Software\Classes\{SCHEMA}"
_DISINSTALLAZIONI = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
VOCE = rf"{_DISINSTALLAZIONI}\IstatUploader"
#: La voce che lasciava l'installer della v1.6.0 (AppId di Inno Setup).
VOCE_INNO = rf"{_DISINSTALLAZIONI}\{{6C0A9E3B-4D1F-4E57-9B5A-2F7C1D8E6A10}}_is1"
_SUFFISSO_VECCHIO = ".vecchio"
_MB_YESNO_ICONA = 0x24
_MB_OK_ICONA = 0x40
_IDYES = 6
_CREATE_NO_WINDOW = 0x08000000
_VERSIONE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class Registro(Protocol):
    def leggi(self, chiave: str, nome: str = "") -> str | None: ...
    def scrivi(self, chiave: str, nome: str, valore: str | int) -> None: ...
    def cancella(self, chiave: str) -> None: ...


class _RegistroWindows:
    """Solo ``HKEY_CURRENT_USER``: è ciò che tiene lontano l'UAC."""

    def leggi(self, chiave: str, nome: str = "") -> str | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chiave) as k:
                return str(winreg.QueryValueEx(k, nome)[0])
        except OSError:
            return None

    def scrivi(self, chiave: str, nome: str, valore: str | int) -> None:
        import winreg

        tipo = winreg.REG_DWORD if isinstance(valore, int) else winreg.REG_SZ
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chiave) as k:
            winreg.SetValueEx(k, nome, 0, tipo, valore)

    def cancella(self, chiave: str) -> None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chiave) as k:
                while True:
                    try:
                        figlia = winreg.EnumKey(k, 0)
                    except OSError:
                        break
                    self.cancella(rf"{chiave}\{figlia}")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, chiave)
        except FileNotFoundError:
            pass


def cartella_installazione() -> Path:
    return Path(os.environ["LOCALAPPDATA"]) / "Programs" / "IstatUploader"


def _programmi_menu_start() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"


def _desktop() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"


def nel_pacchetto() -> bool:
    """Gira dentro un pacchetto MSIX? (``APPMODEL_ERROR_NO_PACKAGE`` = 15700 vuol dire no.)"""
    if not sys.platform.startswith("win"):
        return False
    try:
        lunghezza = ctypes.c_uint32(0)
        kernel32 = ctypes.WinDLL("kernel32")
        return bool(kernel32.GetCurrentPackageFullName(ctypes.byref(lunghezza), None) != 15700)
    except (OSError, AttributeError):
        return False


def _numeri(testo: str | None) -> tuple[int, ...] | None:
    m = _VERSIONE.match((testo or "").strip())
    return tuple(int(x) for x in m.groups()) if m else None


def versione_installata(registro: Registro) -> str | None:
    return registro.leggi(VOCE, "DisplayVersion") or registro.leggi(VOCE_INNO, "DisplayVersion")


def va_copiato(destinazione: Path, installata: str | None, questa: str = __version__) -> bool:
    """Un .exe vecchio scaricato di nuovo non scavalca quello più recente già installato."""
    if not destinazione.exists():
        return True
    gia, nuova = _numeri(installata), _numeri(questa)
    return gia is None or nuova is None or gia < nuova


def copia(sorgente: Path, destinazione: Path) -> None:
    """``copyfile`` e non ``copy2``: solo il contenuto, senza il segno «scaricato da internet».

    Un .exe in uso non si sovrascrive ma si rinomina: si mette da parte quello e al prossimo
    avvio si butta (``togli_avanzi``).
    """
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = destinazione.with_name(f"{destinazione.name}.nuovo")
    shutil.copyfile(sorgente, temporaneo)
    try:
        os.replace(temporaneo, destinazione)
    except PermissionError:
        accantonato = destinazione.with_name(f"{destinazione.name}.{os.getpid()}{_SUFFISSO_VECCHIO}")
        os.replace(destinazione, accantonato)
        os.replace(temporaneo, destinazione)


def togli_avanzi(cartella: Path) -> None:
    for avanzo in cartella.glob(f"*{_SUFFISSO_VECCHIO}"):
        try:
            avanzo.unlink()
        except OSError:
            log.info("avanzo ancora in uso: lo tolgo al prossimo avvio")


def registra_indirizzo(registro: Registro, exe: Path) -> None:
    registro.scrivi(_CLASSI, "", "URL:HostLab Turismatica")
    registro.scrivi(_CLASSI, "URL Protocol", "")
    registro.scrivi(rf"{_CLASSI}\DefaultIcon", "", f"{exe},0")
    registro.scrivi(rf"{_CLASSI}\shell\open\command", "", f'"{exe}" "%1"')


def registra_voce(registro: Registro, exe: Path) -> None:
    valori: dict[str, str | int] = {
        "DisplayName": NOME_APP,
        "DisplayVersion": __version__,
        "Publisher": "Fortitudo",
        "DisplayIcon": f"{exe},0",
        "InstallLocation": str(exe.parent),
        "UninstallString": f'"{exe}" --disinstalla',
        "QuietUninstallString": f'"{exe}" --disinstalla --silenzioso',
        "NoModify": 1,
        "NoRepair": 1,
    }
    for nome, valore in valori.items():
        registro.scrivi(VOCE, nome, valore)


def togli_installer_vecchio(registro: Registro, cartella: Path, programmi: Path) -> None:
    """Toglie ciò che restava dell'installer senza lanciare il suo disinstallatore, che
    cancellerebbe anche l'.exe e l'indirizzo. Il collegamento sul Desktop resta: punta allo
    stesso percorso, e la disinstallazione lo toglie."""
    if registro.leggi(VOCE_INNO, "DisplayName") is None:
        return
    registro.cancella(VOCE_INNO)
    for avanzo in cartella.glob("unins000.*"):
        try:
            avanzo.unlink()
        except OSError:
            log.warning("disinstallatore vecchio non cancellato: %s", avanzo.name)
    shutil.rmtree(programmi / NOME_APP, ignore_errors=True)
    log.info("installer della v1.6.0 sostituito")


def crea_collegamento(collegamento: Path, exe: Path) -> None:
    """Il collegamento con IShellLink, in un thread suo: COM non deve toccare quello della finestra."""
    def lavora() -> None:
        ole32, guid = ctypes.WinDLL("ole32"), ctypes.c_byte * 16
        ole32.CLSIDFromString.argtypes = (ctypes.c_wchar_p, ctypes.c_void_p)

        def uuid(testo: str) -> ctypes.Array:
            valore = guid()
            ole32.CLSIDFromString(testo, ctypes.byref(valore))
            return valore

        def metodo(oggetto: ctypes.c_void_p, posto: int, *tipi: Any) -> Any:
            tabella = ctypes.cast(oggetto, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
            return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *tipi)(tabella[posto])

        ole32.CoInitialize(None)
        shell = ctypes.c_void_p()
        file_ = ctypes.c_void_p()
        try:
            risultato = ole32.CoCreateInstance(
                ctypes.byref(uuid("{00021401-0000-0000-C000-000000000046}")), None, 1,
                ctypes.byref(uuid("{000214F9-0000-0000-C000-000000000046}")), ctypes.byref(shell),
            )
            if risultato != 0:
                raise OSError(f"CoCreateInstance: {risultato}")
            metodo(shell, 20, ctypes.c_wchar_p)(shell, str(exe))              # SetPath
            metodo(shell, 9, ctypes.c_wchar_p)(shell, str(exe.parent))        # SetWorkingDirectory
            metodo(shell, 0, ctypes.c_void_p, ctypes.c_void_p)(               # QueryInterface
                shell, ctypes.byref(uuid("{0000010B-0000-0000-C000-000000000046}")),
                ctypes.byref(file_),
            )
            risultato = metodo(file_, 6, ctypes.c_wchar_p, ctypes.c_int)(file_, str(collegamento), 1)
            if risultato != 0:                                                # Save
                raise OSError(f"Save: {risultato}")
        finally:
            for oggetto in (file_, shell):
                if oggetto:
                    metodo(oggetto, 2)(oggetto)                               # Release
            ole32.CoUninitialize()

    errore: list[BaseException] = []

    def protetto() -> None:
        try:
            lavora()
        except Exception as exc:  # noqa: BLE001 — senza collegamento il programma funziona lo stesso
            errore.append(exc)

    collegamento.parent.mkdir(parents=True, exist_ok=True)
    filo = threading.Thread(target=protetto)
    filo.start()
    filo.join()
    if errore:
        log.warning("collegamento non creato: %s", errore[0])


def registra_tutto(registro: Registro, exe: Path) -> None:
    """Ciò che si controlla a ogni avvio. Ognuno per sé: uno che fallisce non ferma gli altri."""
    programmi = _programmi_menu_start()
    try:
        togli_installer_vecchio(registro, exe.parent, programmi)
    except OSError as exc:
        log.warning("installer vecchio: %s", exc)
    for passo in (registra_indirizzo, registra_voce):
        try:
            passo(registro, exe)
        except OSError as exc:
            log.warning("%s non riuscito: %s", passo.__name__, exc)
    collegamento = programmi / f"{NOME_APP}.lnk"
    if not collegamento.exists():
        crea_collegamento(collegamento, exe)


def _rilancia(exe: Path, argomenti: Sequence[str]) -> None:
    # Senza questa variabile un .exe PyInstaller lanciato da un altro riusa la cartella estratta
    # del primo, che sparisce quando il primo esce.
    ambiente = {**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"}
    subprocess.Popen([str(exe), *argomenti], env=ambiente, close_fds=True)  # noqa: S603


def _si_applica() -> bool:
    return (sys.platform.startswith("win") and bool(getattr(sys, "frozen", False))
            and not nel_pacchetto())


def _stessa(a: Path, b: Path) -> bool:
    return os.path.normcase(str(a)) == os.path.normcase(str(b))


def allinea(argomenti: Sequence[str], registro: Registro | None = None) -> bool:
    """A ogni avvio normale. ``True`` se la copia installata ha preso il posto di questa, che
    quindi deve uscire."""
    if not _si_applica():
        return False
    questo = Path(sys.executable).resolve()
    registro = registro if registro is not None else _RegistroWindows()
    try:
        destinazione = cartella_installazione() / NOME_EXE
        if _stessa(questo, destinazione):
            togli_avanzi(destinazione.parent)
            registra_tutto(registro, destinazione)
            return False
        if va_copiato(destinazione, versione_installata(registro)):
            copia(questo, destinazione)
            registra_voce(registro, destinazione)
        _rilancia(destinazione, argomenti)
        return True
    except (OSError, KeyError) as exc:
        log.warning("installazione non riuscita, parto da dove sono: %s", exc)
        registra_tutto(registro, questo)
        return False


def installa() -> int:
    """``--installa``: copia e registra senza aprire niente. Per la prova del giro su GitHub."""
    if not _si_applica():
        return 2
    registro = _RegistroWindows()
    destinazione = cartella_installazione() / NOME_EXE
    questo = Path(sys.executable).resolve()
    if not _stessa(questo, destinazione) and va_copiato(destinazione, versione_installata(registro)):
        copia(questo, destinazione)
    registra_tutto(registro, destinazione)
    return 0


def togli_registrazioni(registro: Registro, programmi: Path, desktop: Path) -> None:
    registro.cancella(_CLASSI)
    registro.cancella(VOCE)
    registro.cancella(VOCE_INNO)
    (programmi / f"{NOME_APP}.lnk").unlink(missing_ok=True)
    (desktop / f"{NOME_APP}.lnk").unlink(missing_ok=True)
    shutil.rmtree(programmi / NOME_APP, ignore_errors=True)


def _messaggio(testo: str, stile: int) -> int:
    return int(ctypes.WinDLL("user32").MessageBoxW(None, testo, NOME_APP, stile))


def disinstalla(argomenti: Sequence[str]) -> int:
    """``--disinstalla``, dalla voce in «App installate». L'.exe in uso non può cancellare se
    stesso: la cartella la toglie un comando che parte dopo la sua uscita."""
    if not sys.platform.startswith("win"):
        return 2
    silenzioso = "--silenzioso" in argomenti
    from uploader_turismatica import istanza
    from uploader_turismatica.finestra import MUTEX

    if istanza.gia_aperto(MUTEX, NOME_APP):
        if not silenzioso:
            _messaggio("Istat Uploader è aperto: chiudilo e riprova.", _MB_OK_ICONA)
        return 1
    if not silenzioso and _messaggio(
        "Vuoi togliere Istat Uploader da questo computer?\n\n"
        "Le tue strutture e le impostazioni restano salvate: se lo rimetti, le ritrovi.",
        _MB_YESNO_ICONA,
    ) != _IDYES:
        return 0
    togli_registrazioni(_RegistroWindows(), _programmi_menu_start(), _desktop())
    cartella = cartella_installazione()
    subprocess.Popen(  # noqa: S603, S607 — percorso nostro, sotto %LOCALAPPDATA%
        f'cmd /c ping -n 6 127.0.0.1 >nul & rmdir /s /q "{cartella}"',
        cwd=tempfile.gettempdir(), creationflags=_CREATE_NO_WINDOW,
    )
    return 0
