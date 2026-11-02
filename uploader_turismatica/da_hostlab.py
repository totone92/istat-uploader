"""L'avvio da HostLab: il tasto «Carica su Turismatica» apre l'app con un gettone monouso.

L'.exe registra da solo l'indirizzo (``installazione.py``) ``hostlab-turismatica://carica/<gettone>``: Windows avvia
l'.exe con quell'argomento. L'indirizzo porta solo il gettone. Ogni avvio lo deposita in un
file nella cartella dati, e la finestra aperta (questa o quella di prima) lo ritira da lì:
la strada è una sola, che l'app fosse chiusa o già aperta.

⚠️ **Il server non viene dall'indirizzo, è scritto qui**: qualunque pagina web può aprire un
``hostlab-turismatica://``, e non deve poter far caricare al gestore uno zip di chi vuole.
Per le prove in locale, un file ``server_di_prova.txt`` nella cartella dati indica un
indirizzo della rete privata; un indirizzo pubblico si ignora.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

from uploader_turismatica import __version__
from uploader_turismatica.strutture import cartella_impostazioni

log = logging.getLogger(__name__)

SCHEMA = "hostlab-turismatica"
SERVER = "https://hostlab.umbriaround.it"
PERCORSO_PACCHETTO = "/turismatica/pacchetto"
FILE_ARRIVO = "gettone_in_arrivo.txt"
FILE_SERVER_DI_PROVA = "server_di_prova.txt"
#: Il gettone vale due minuti sul server: oltre, un file rimasto è di un'altra volta.
ETA_MASSIMA_ARRIVO_S = 300.0
ATTESA_RETE_S = 60.0
#: Un mese sono al massimo 31 file da pochi kB.
DIMENSIONE_MASSIMA = 5 * 1024 * 1024

_LINK = re.compile(rf"^{SCHEMA}://carica/(\d{{1,12}}\.[A-Za-z0-9_-]{{32,64}})/?$", re.IGNORECASE)


class PacchettoNonDisponibile(Exception):
    """Il pacchetto non è arrivato; il testo è per il gestore."""


@dataclass(frozen=True)
class Pacchetto:
    percorso: Path
    struttura: str
    mese: str           # AAAA-MM


def gettone_dal_link(link: str) -> str | None:
    m = _LINK.match(link.strip())
    return m.group(1) if m else None


def link_fra_gli_argomenti(argomenti: list[str]) -> str | None:
    prefisso = f"{SCHEMA}:"
    return next((a for a in argomenti if a.lower().startswith(prefisso)), None)


def deposita(gettone: str, cartella: Path | None = None) -> None:
    dove = cartella or cartella_impostazioni()
    dove.mkdir(parents=True, exist_ok=True)
    temp = dove / f"{FILE_ARRIVO}.{os.getpid()}"
    temp.write_text(gettone, encoding="ascii")
    os.replace(temp, dove / FILE_ARRIVO)


def ritira(cartella: Path | None = None, *, adesso: float | None = None) -> str | None:
    """Il gettone depositato, una volta sola. Uno rimasto da troppo tempo si butta."""
    file = (cartella or cartella_impostazioni()) / FILE_ARRIVO
    try:
        eta = (time.time() if adesso is None else adesso) - file.stat().st_mtime
        testo = file.read_text(encoding="ascii").strip()
        file.unlink()
    except (OSError, UnicodeError):
        return None
    return testo if eta <= ETA_MASSIMA_ARRIVO_S else None


def server(cartella: Path | None = None) -> str:
    file = (cartella or cartella_impostazioni()) / FILE_SERVER_DI_PROVA
    try:
        scritto = file.read_text(encoding="utf-8").strip().rstrip("/")
    except (OSError, UnicodeError):
        return SERVER
    parti = urlsplit(scritto)
    try:
        privato = parti.scheme in ("http", "https") and ipaddress.ip_address(
            parti.hostname or "").is_private
    except ValueError:
        privato = False
    if not privato:
        log.warning("server di prova ignorato: non è un indirizzo della rete privata")
        return SERVER
    log.info("server di prova in uso")
    return scritto


def _messaggio_errore(exc: urllib.error.HTTPError) -> str:
    try:
        dati = json.loads(exc.read(4096).decode("utf-8"))
        testo = dati.get("errore") if isinstance(dati, dict) else None
    except (OSError, ValueError):
        testo = None
    return str(testo) if testo else (
        "HostLab non ha dato il pacchetto. Torna in HostLab e premi di nuovo "
        "«Carica su Turismatica»."
    )


def scarica(gettone: str, *, base: str | None = None) -> Pacchetto:
    """Ritira il pacchetto: il gettone viaggia nell'intestazione, non nell'indirizzo."""
    richiesta = urllib.request.Request(  # noqa: S310 — https, indirizzo scritto qui
        (base or server()) + PERCORSO_PACCHETTO, method="POST",
        headers={"Authorization": f"Bearer {gettone}",
                 "User-Agent": f"IstatUploader/{__version__}"},
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=ATTESA_RETE_S) as risposta:  # noqa: S310
            contenuto = risposta.read(DIMENSIONE_MASSIMA + 1)
            struttura = unquote(risposta.headers.get("X-Struttura", ""))
            mese = risposta.headers.get("X-Mese", "")
    except urllib.error.HTTPError as exc:
        log.warning("pacchetto rifiutato: HTTP %s", exc.code)
        raise PacchettoNonDisponibile(_messaggio_errore(exc)) from exc
    except OSError as exc:
        log.warning("pacchetto non scaricato: %s", type(exc).__name__)
        raise PacchettoNonDisponibile(
            "Non riesco a parlare con HostLab: controlla la connessione, poi torna in "
            "HostLab e premi di nuovo «Carica su Turismatica»."
        ) from exc
    if len(contenuto) > DIMENSIONE_MASSIMA:
        raise PacchettoNonDisponibile("Il pacchetto arrivato è troppo grande: mi fermo.")
    cartella = Path(tempfile.mkdtemp(prefix="istat-hostlab-"))
    percorso = cartella / "pacchetto-hostlab.zip"
    percorso.write_bytes(contenuto)
    log.info("pacchetto ritirato | mese=%s | %d byte", mese, len(contenuto))
    return Pacchetto(percorso, struttura, mese)
