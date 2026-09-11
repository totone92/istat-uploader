"""Le strutture dell'utente: **dichiarate una volta**, e poi restano.

⚠️ **Niente credenziali qui dentro, e non per prudenza: non ce ne sono.**
L'accesso a Turismatica è SPID/CIE e lo fa la persona nel browser; l'app non
vede né password né codici, quindi non ha niente da custodire. Questo file
contiene un id pubblico, un'etichetta e un percorso.

Il file vive accanto alle impostazioni dell'utente
(``%APPDATA%\\UploaderTurismatica`` su Windows, ``~/.config`` altrove) e **non**
accanto all'eseguibile: un .exe in Download dev'essere sostituibile senza
perdere le strutture, e in ``Program Files`` non si può scrivere.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

NOME_FILE = "strutture.json"


@dataclass
class Struttura:
    """Una struttura sul portale Turismatica.

    ``id_turismatica`` è il numero che sta nell'indirizzo della pagina movimenti
    (``…movimentoospiti.xhtml?idStruttura=12345``). ⚠️ **Non è l'id di beb.it**:
    sono due sistemi diversi e i due numeri non si somigliano nemmeno.

    ``sorgente`` è l'ultimo zip o cartella usato: si ripropone da solo al giro
    dopo, perché il gesto normale è rifare la stessa cosa il mese dopo.
    """

    id_turismatica: str
    etichetta: str
    sorgente: str = ""

    def valida(self) -> str | None:
        """Messaggio d'errore per l'utente, o ``None`` se va bene."""
        if not self.etichetta.strip():
            return "Dai un nome alla struttura (quello che usi tu, serve solo a te)."
        idt = self.id_turismatica.strip()
        if not idt:
            return "Manca il numero della struttura su Turismatica."
        if not idt.isdigit():
            return (
                f"«{idt}» non è un numero. Su Turismatica lo trovi "
                "nell'indirizzo della pagina dei movimenti, dopo «idStruttura=»."
            )
        return None


def cartella_impostazioni() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "UploaderTurismatica"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "uploader-turismatica"


def percorso_file() -> Path:
    return cartella_impostazioni() / NOME_FILE


def carica(percorso: Path | None = None) -> list[Struttura]:
    """Le strutture salvate. **Mai un'eccezione**: un file corrotto o assente
    dà una lista vuota, perché il rimedio (ridichiarare la struttura) l'utente
    ce l'ha, mentre da un errore all'avvio non esce."""
    p = percorso or percorso_file()
    try:
        dati = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(dati, list):
        return []
    out: list[Struttura] = []
    for voce in dati:
        if not isinstance(voce, dict):
            continue
        try:
            out.append(
                Struttura(
                    id_turismatica=str(voce["id_turismatica"]),
                    etichetta=str(voce.get("etichetta", "")),
                    sorgente=str(voce.get("sorgente", "")),
                )
            )
        except KeyError:
            continue
    return out


def salva(strutture: list[Struttura], percorso: Path | None = None) -> None:
    """Scrive l'elenco. **Scrittura atomica** (file temporaneo + ``replace``):
    se il PC si spegne a metà, il vecchio elenco resta intero invece di
    diventare mezzo file che poi non si rilegge."""
    p = percorso or percorso_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    testo = json.dumps([asdict(s) for s in strutture], indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(testo)
        os.replace(tmp, p)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise
