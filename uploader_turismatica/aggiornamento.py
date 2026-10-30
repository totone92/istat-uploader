"""C'è una versione nuova? Solo un avviso, mai un download.

All'avvio si legge l'ultima Release del repository pubblico su GitHub. Se è più
nuova di questa, l'interfaccia mostra una fascia con il link alla pagina della
Release; scaricarla è una scelta del gestore. **Senza rete, con un errore o con
una risposta che non si capisce non succede niente**: non deve mai disturbare il
lavoro. Alla richiesta non si allega niente che riguardi chi la fa.
"""
from __future__ import annotations

import json
import logging
import re
import urllib.request
from dataclasses import dataclass

from uploader_turismatica import __version__

log = logging.getLogger(__name__)

ULTIMA_RELEASE = "https://api.github.com/repos/totone92/istat-uploader/releases/latest"
#: Il link si apre nel browser: si accetta solo quello del nostro repository.
PREFISSO_RELEASE = "https://github.com/totone92/istat-uploader/releases/"
ATTESA_S = 5.0

_VERSIONE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


@dataclass(frozen=True)
class NuovaVersione:
    versione: str
    indirizzo: str


def _numeri(testo: str) -> tuple[int, ...] | None:
    m = _VERSIONE.match(testo.strip())
    return tuple(int(x) for x in m.groups()) if m else None


def piu_nuova(dati: object, attuale: str = __version__) -> NuovaVersione | None:
    """Dalla risposta di GitHub, la versione da segnalare (logica pura)."""
    if not isinstance(dati, dict):
        return None
    etichetta, indirizzo = dati.get("tag_name"), dati.get("html_url")
    if not isinstance(etichetta, str) or not isinstance(indirizzo, str):
        return None
    nuova, questa = _numeri(etichetta), _numeri(attuale)
    if nuova is None or questa is None or nuova <= questa:
        return None
    if not indirizzo.startswith(PREFISSO_RELEASE):
        return None
    return NuovaVersione(etichetta.strip().removeprefix("v"), indirizzo)


def cerca(indirizzo: str = ULTIMA_RELEASE, attesa_s: float = ATTESA_S) -> NuovaVersione | None:
    richiesta = urllib.request.Request(  # noqa: S310 — indirizzo nostro, https
        indirizzo,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": f"IstatUploader/{__version__}"},
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=attesa_s) as risposta:  # noqa: S310
            trovata = piu_nuova(json.loads(risposta.read().decode("utf-8")))
    except Exception as exc:                    # noqa: BLE001 — senza rete non succede niente
        log.info("versione nuova non controllata: %s", type(exc).__name__)
        return None
    log.info("versione nuova: %s", trovata.versione if trovata else "nessuna")
    return trovata
