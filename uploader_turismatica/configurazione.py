"""Cosa l'app ricorda fra un avvio e l'altro: le strutture riconosciute sul
portale, lo stato dei loro giorni, gli abbinamenti confermati dal gestore.

⚠️ **Niente credenziali, e non per filtro: non ce ne sono.** L'accesso è
SPID/CIE e lo fa la persona nel browser. Qui dentro: numeri e nomi delle
strutture come li mostra il portale, quali giorni risultano caricati, e quale
nome di file va a quale struttura. Un test lo verifica.

Sta nella cartella dati dell'utente (``%APPDATA%\\UploaderTurismatica``), non
accanto all'.exe: l'.exe si sostituisce senza perdere niente. Si scrive **solo
dopo l'OK** del gestore sul riepilogo, e in modo atomico.

La versione 1 (``strutture.json``, strutture scritte a mano) **non si
migra**: il flusso nuovo le legge dal portale, e un numero scritto a mano è
esattamente ciò che la prima prova ha mostrato fragile.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from uploader_turismatica.piano import StatoMese
from uploader_turismatica.strutture import cartella_impostazioni

NOME_FILE = "configurazione.json"
VERSIONE = 2


@dataclass
class StrutturaConf:
    id_turismatica: str
    nome: str
    comune: str = ""
    tipologia: str = ""
    stato_portale: str = ""
    #: Inserita a mano perché la lettura automatica non l'ha trovata.
    manuale: bool = False
    #: ``AAAA-MM`` → stato dei giorni letto sul portale.
    mesi: dict[str, StatoMese] = field(default_factory=dict)
    #: L'ultimo problema incontrato leggendola, già in parole da gestore.
    avviso: str = ""

    def da_json(self) -> dict[str, object]:
        return {
            "id_turismatica": self.id_turismatica,
            "nome": self.nome,
            "comune": self.comune,
            "tipologia": self.tipologia,
            "stato_portale": self.stato_portale,
            "manuale": self.manuale,
            "mesi": {k: m.da_json() for k, m in sorted(self.mesi.items())},
            "avviso": self.avviso,
        }

    @classmethod
    def dal_json(cls, d: dict[str, object]) -> StrutturaConf:
        mesi_raw = d.get("mesi") or {}
        assert isinstance(mesi_raw, dict)
        return cls(
            id_turismatica=str(d["id_turismatica"]),
            nome=str(d.get("nome", "")),
            comune=str(d.get("comune", "")),
            tipologia=str(d.get("tipologia", "")),
            stato_portale=str(d.get("stato_portale", "")),
            manuale=bool(d.get("manuale", False)),
            mesi={k: StatoMese.dal_json(k, v) for k, v in mesi_raw.items()},
            avviso=str(d.get("avviso", "")),
        )


@dataclass
class Configurazione:
    strutture: list[StrutturaConf]
    #: La risposta a «Gestisci una struttura o più strutture?»: ``una``/``piu``.
    quante: str
    #: Abbinamenti confermati: ``id:<id nel nome del file>`` o
    #: ``nome:<nome normalizzato>`` → numero Turismatica.
    alias: dict[str, str] = field(default_factory=dict)
    aggiornata_il: datetime | None = None

    def struttura(self, id_turismatica: str) -> StrutturaConf | None:
        return next((s for s in self.strutture if s.id_turismatica == id_turismatica), None)

    def ids(self) -> frozenset[str]:
        return frozenset(s.id_turismatica for s in self.strutture)

    def da_json(self) -> dict[str, object]:
        return {
            "versione": VERSIONE,
            "quante": self.quante,
            "aggiornata_il": self.aggiornata_il.isoformat(timespec="minutes")
            if self.aggiornata_il else None,
            "strutture": [s.da_json() for s in self.strutture],
            "alias": dict(sorted(self.alias.items())),
        }

    @classmethod
    def dal_json(cls, d: object) -> Configurazione:
        if not isinstance(d, dict) or d.get("versione") != VERSIONE:
            raise ValueError("versione diversa")
        strutture_raw = d.get("strutture") or []
        alias_raw = d.get("alias") or {}
        assert isinstance(strutture_raw, list) and isinstance(alias_raw, dict)
        quando = d.get("aggiornata_il")
        return cls(
            strutture=[StrutturaConf.dal_json(s) for s in strutture_raw],
            quante=str(d.get("quante", "piu")),
            alias={str(k): str(v) for k, v in alias_raw.items()},
            aggiornata_il=datetime.fromisoformat(quando) if isinstance(quando, str) else None,
        )


def percorso_file() -> Path:
    return cartella_impostazioni() / NOME_FILE


def carica(percorso: Path | None = None) -> Configurazione | None:
    """La configurazione salvata, o ``None`` (primo avvio, file rotto o di una
    versione diversa): in tutti e tre i casi il rimedio è rifare «Collega
    Turismatica», e l'app lo propone invece di fermarsi."""
    p = percorso or percorso_file()
    try:
        dati = json.loads(p.read_text(encoding="utf-8"))
        return Configurazione.dal_json(dati)
    except (OSError, ValueError, KeyError, AssertionError, TypeError):
        return None


def salva(conf: Configurazione, percorso: Path | None = None) -> Path:
    """Scrittura atomica: se il PC si spegne a metà, resta la versione di prima."""
    p = percorso or percorso_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    testo = json.dumps(conf.da_json(), indent=2, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(testo)
        os.replace(tmp, p)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise
    return p
