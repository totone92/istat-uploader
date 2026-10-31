"""Un programma solo per volta: il secondo avvio porta davanti la finestra già aperta e si chiude.

Due finestre sulla stessa cartella dati si rubano il profilo di WebView2 («Failed to delete
user data folder», visto sul PC di Ambra dopo un doppio clic). Il mutex si prende **prima** di
creare la finestra; se Windows non risponde si parte lo stesso: un controllo in più non deve
mai impedire di lavorare. Fuori da Windows non fa niente.
"""
from __future__ import annotations

import ctypes
import logging
import sys
import time
from typing import Protocol

log = logging.getLogger(__name__)

#: La finestra del primo avvio può non esserci ancora: la si cerca per questo tempo.
ATTESA_FINESTRA_S = 5.0
_PAUSA_S = 0.25
_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9
#: Le finestre di pywebview: una cartella o una scheda di Chrome con lo stesso nome non contano.
_CLASSE = "WindowsForms"


class Sistema(Protocol):
    def mutex_gia_preso(self, nome: str) -> bool: ...
    def porta_davanti(self, inizio_titolo: str) -> bool: ...


class _Windows:
    def __init__(self) -> None:
        from ctypes import wintypes

        self._wt = wintypes
        self._k = ctypes.WinDLL("kernel32", use_last_error=True)
        self._u = ctypes.WinDLL("user32", use_last_error=True)
        self._k.CreateMutexW.restype = wintypes.HANDLE
        self._k.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        self._u.IsIconic.argtypes = (wintypes.HWND,)
        self._u.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
        self._u.SetForegroundWindow.argtypes = (wintypes.HWND,)
        self._u.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        self._u.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
        self._u.IsWindowVisible.argtypes = (wintypes.HWND,)

    def mutex_gia_preso(self, nome: str) -> bool:
        # La maniglia resta aperta fino all'uscita del processo: è lei che tiene il mutex.
        maniglia = self._k.CreateMutexW(None, False, nome)
        errore = ctypes.get_last_error()
        return bool(maniglia) and errore == _ERROR_ALREADY_EXISTS

    def porta_davanti(self, inizio_titolo: str) -> bool:
        trovate: list[int] = []
        wt = self._wt

        @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
        def guarda(finestra: int, _: int) -> bool:
            titolo, classe = ctypes.create_unicode_buffer(256), ctypes.create_unicode_buffer(256)
            self._u.GetWindowTextW(finestra, titolo, 256)
            self._u.GetClassNameW(finestra, classe, 256)
            if (self._u.IsWindowVisible(finestra) and titolo.value.startswith(inizio_titolo)
                    and classe.value.startswith(_CLASSE)):
                trovate.append(finestra)
                return False
            return True

        self._u.EnumWindows(guarda, 0)
        if not trovate:
            return False
        if self._u.IsIconic(trovate[0]):
            self._u.ShowWindow(trovate[0], _SW_RESTORE)
        self._u.SetForegroundWindow(trovate[0])
        return True


def gia_aperto(nome_mutex: str, inizio_titolo: str, sistema: Sistema | None = None) -> bool:
    """``True`` se il programma è già aperto: la sua finestra è davanti e questo deve chiudersi."""
    try:
        if sistema is None:
            if not sys.platform.startswith("win"):
                return False
            sistema = _Windows()
        if not sistema.mutex_gia_preso(nome_mutex):
            return False
        fine = time.monotonic() + ATTESA_FINESTRA_S
        while not sistema.porta_davanti(inizio_titolo) and time.monotonic() < fine:
            time.sleep(_PAUSA_S)
    except (OSError, AttributeError, ValueError) as exc:
        log.warning("controllo dell'istanza unica non riuscito: %s", type(exc).__name__)
        return False
    return True
