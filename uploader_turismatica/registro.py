"""Il registro: un file di testo **accanto all'.exe**, da rimandare quando
qualcosa non va.

Una riga per giorno (data e ora, struttura, giorno, esito, file, errore) più
l'inizio e la fine di ogni giro, con la modalità. È la cosa che chi assiste
legge per primo, quindi deve bastare da solo — e non deve contenere niente che
non si possa mandare per email:

* **nessuna credenziale**, e non per filtro: l'app non ne vede (l'accesso è
  SPID/CIE, nel browser);
* **nessun dato degli ospiti**: del file si scrive il **nome**, che dichiara una
  data e l'id della struttura, mai il contenuto;
* **nessun percorso della cartella personale**: ``C:\\Users\\<nome>\\…``
  porta il nome di chi usa il PC. Il formattatore lo sostituisce con ``~``
  in ogni riga, anche in quelle che arrivano dagli errori di Selenium.

Accanto all'.exe e non in ``%APPDATA%`` (dove stanno le strutture): è il posto
in cui chi l'ha scaricato lo ritrova senza istruzioni. Se lì non si può
scrivere (``Program Files``, una chiavetta protetta) si ripiega sulla cartella
delle impostazioni, e la finestra dice dove.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from uploader_turismatica.strutture import cartella_impostazioni

NOME_FILE = "IstatUploader.log"
_MAX_BYTE = 1_000_000
_COPIE = 3
_FORMATO = "%(asctime)s | %(levelname)-7s | %(message)s"
_DATA = "%Y-%m-%d %H:%M:%S"


def cartella_preferita() -> Path:
    """Accanto all'eseguibile quando è impacchettato; da sorgente, la cartella
    delle impostazioni (accanto a ``python.exe`` non avrebbe senso)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return cartella_impostazioni()


class FormattatoreRiservato(logging.Formatter):
    """Sostituisce la cartella personale con ``~`` in tutto ciò che scrive,
    traccia degli errori compresa."""

    def __init__(self, casa: Path | None = None) -> None:
        super().__init__(_FORMATO, _DATA)
        base = str(casa if casa is not None else Path.home())
        # Le due grafie: Windows usa ``\\``, ma Selenium e Chrome a volte
        # scrivono lo stesso percorso con ``/``.
        self._case = sorted(
            {base, base.replace("\\", "/"), base.replace("/", "\\")},
            key=len, reverse=True,
        )

    def format(self, record: logging.LogRecord) -> str:
        testo = super().format(record)
        for c in self._case:
            if len(c) > 1:
                testo = testo.replace(c, "~")
        return testo


def _gestore(cartella: Path) -> RotatingFileHandler:
    cartella.mkdir(parents=True, exist_ok=True)
    g = RotatingFileHandler(
        cartella / NOME_FILE, maxBytes=_MAX_BYTE, backupCount=_COPIE,
        encoding="utf-8",
    )
    g.set_name("registro-istat-uploader")
    return g


def configura(cartella: Path | None = None) -> Path | None:
    """Accende il registro e dice **dove** l'ha messo (``None`` se in nessun
    posto si poteva scrivere: l'app funziona lo stesso).

    Idempotente: richiamata, sostituisce il proprio gestore invece di
    aggiungerne un secondo (ogni riga uscirebbe due volte)."""
    radice = logging.getLogger()
    radice.setLevel(logging.INFO)
    for g in list(radice.handlers):
        if g.get_name() in ("registro-istat-uploader", "registro-console"):
            radice.removeHandler(g)
            g.close()

    # Un .exe senza console ha ``sys.stderr`` a None: lì non si scrive niente.
    if sys.stderr is not None:
        console = logging.StreamHandler(sys.stderr)
        console.set_name("registro-console")
        console.setFormatter(FormattatoreRiservato())
        radice.addHandler(console)

    for candidata in (cartella or cartella_preferita(), cartella_impostazioni()):
        try:
            g = _gestore(candidata)
        except OSError:
            continue
        g.setFormatter(FormattatoreRiservato())
        radice.addHandler(g)
        return candidata / NOME_FILE
    return None
