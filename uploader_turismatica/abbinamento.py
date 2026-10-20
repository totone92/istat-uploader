"""Quali file vanno a quale struttura — da soli quando è certo, chiedendo
quando non lo è. **Non si indovina mai.**

Ogni file ISTAT porta due indizi:

* **il nome della struttura**, nella prima riga (riempito a 255 caratteri). È
  il nome che scrive chi genera il file (beb.it, HostLab), che **non è detto
  sia quello del portale**: «Casa Lavanda» da una parte, «CASA LAVANDA S.R.L.»
  dall'altra;
* **l'id nel nome del file**, ``schedine_istat_<id>_<AAAAMMGG>.txt``. ⚠️ **Non
  è il numero Turismatica**: è l'id della struttura su beb.it, o il CIN in
  HostLab. Confrontarlo col numero Turismatica sarebbe proprio indovinare —
  due numeri di sistemi diversi possono coincidere per caso. **Il CIN invece
  il portale lo mostra** (intestazione dei movimenti): un file che porta nel
  nome esattamente il CIN di una struttura è di quella struttura.

Quindi la regola, in ordine:

1. lo **zip di prova** non si abbina mai da solo (la sua struttura non esiste);
2. ciò che il gestore ha già **confermato una volta** (``alias``: id nel nome
   o nome nel file → numero Turismatica) vale da lì in poi;
3. il **CIN** nel nome del file uguale al CIN letto sul portale — **solo se**
   la lettura ha confermato su **tutte** le strutture del gestore che il CIN
   contiene il numero Turismatica (ultime 6 cifre, zeri davanti:
   ``IT054039B403012345`` ↔ ``12345``; :func:`cin_affidabile`). Una sola
   struttura che non torna, o senza CIN letto, e il CIN non abbina niente;
4. un nome nel file **uguale** (a meno di maiuscole, accenti e punteggiatura)
   al nome di **una sola** struttura del portale;
5. tutto il resto si **chiede**, con le strutture più somiglianti in cima. Anche
   quando il gestore ha una struttura sola: la proposta è pronta, ma il clic è
   suo. Due gruppi diversi che finirebbero sulla stessa struttura si chiedono
   entrambi.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from uploader_turismatica.sorgente import STRUTTURA_DI_PROVA, data_dal_nome

_ID_NEL_NOME = re.compile(r"^schedine_istat_(.+)_\d{8}\.txt$", re.IGNORECASE)
_PAROLE_VUOTE = frozenset({
    "SRL", "SAS", "SNC", "SPA", "DI", "DEL", "DELLA", "LA", "IL", "LE", "LO",
    "B", "BB", "BNB", "E", "AND", "THE",
})


def normalizza(nome: str) -> str:
    """Maiuscole, senza accenti, la punteggiatura diventa spazio, spazi singoli."""
    senza_accenti = "".join(
        c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c)
    )
    return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", senza_accenti).upper().split())


def _parole(nome: str) -> set[str]:
    return {p for p in normalizza(nome).split() if p not in _PAROLE_VUOTE}


def somiglianza(a: str, b: str) -> float:
    """Quante parole in comune, da 0 a 1. Serve **solo a ordinare** le
    proposte: non abbina mai niente da sola."""
    pa, pb = _parole(a), _parole(b)
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / len(pa | pb)


def intestazione(file: Path) -> str:
    """Il nome della struttura nella prima riga del file ('' se illeggibile)."""
    try:
        with file.open("rb") as f:
            prima = f.read(300).split(b"\r\n", 1)[0].split(b"\n", 1)[0]
    except OSError:
        return ""
    for codifica in ("utf-8", "cp1252"):
        try:
            return prima.decode(codifica).strip()
        except UnicodeDecodeError:
            continue
    return ""


def id_dal_nome(nome_file: str) -> str | None:
    m = _ID_NEL_NOME.match(nome_file.strip())
    return m.group(1) if m else None


@dataclass
class Gruppo:
    """I file che dicono di essere della stessa struttura."""

    nome_nel_file: str
    id_nel_nome: str | None
    per_giorno: dict[date, Path] = field(default_factory=dict)
    di_prova: bool = False

    @property
    def chiave(self) -> str:
        return f"{normalizza(self.nome_nel_file)}|{self.id_nel_nome or ''}"

    @property
    def giorni(self) -> list[date]:
        return sorted(self.per_giorno)

    def chiavi_alias(self) -> list[str]:
        """Le chiavi con cui una conferma del gestore si ricorda."""
        chiavi = []
        if self.id_nel_nome:
            chiavi.append(f"id:{self.id_nel_nome}")
        if self.nome_nel_file:
            chiavi.append(f"nome:{normalizza(self.nome_nel_file)}")
        return chiavi


def raggruppa(file: Sequence[Path], *, marcatore_prova: bool) -> list[Gruppo]:
    """Divide i file per (nome nella prima riga, id nel nome). I file che non
    dichiarano una data restano fuori: lo dice ``Sorgente.non_riconosciuti``."""
    gruppi: dict[tuple[str, str | None], Gruppo] = {}
    for f in file:
        giorno = data_dal_nome(f.name)
        if giorno is None:
            continue
        nome = intestazione(f)
        ident = id_dal_nome(f.name)
        g = gruppi.setdefault(
            (normalizza(nome), ident),
            Gruppo(nome_nel_file=nome, id_nel_nome=ident),
        )
        g.per_giorno.setdefault(giorno, f)
        if nome.encode("utf-8", "ignore").startswith(STRUTTURA_DI_PROVA):
            g.di_prova = True
    for g in gruppi.values():
        g.di_prova = g.di_prova or marcatore_prova
    return sorted(gruppi.values(), key=lambda g: (g.nome_nel_file, g.id_nel_nome or ""))


@dataclass(frozen=True)
class StrutturaNota:
    id_turismatica: str
    nome: str
    #: Il CIN letto sul portale ('' se non letto).
    cin: str = ""


def _codice(testo: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", testo.upper())


def cin_affidabile(strutture: Sequence[StrutturaNota]) -> bool:
    """Il CIN di **ogni** struttura finisce con il suo numero Turismatica
    (ultime 6 cifre, con gli zeri davanti)? È la condizione per abbinare i
    file dal CIN: una regola vista su un campione si usa solo se la lettura
    la conferma su tutte, altrimenti non si usa per nessuna."""
    if not strutture:
        return False
    for s in strutture:
        cin = _codice(s.cin)
        if len(s.id_turismatica) > 6 or not s.id_turismatica.isdigit():
            return False
        if len(cin) < 6 or cin[-6:] != s.id_turismatica.zfill(6):
            return False
    return True


@dataclass
class Abbinamento:
    gruppo: Gruppo
    #: Il numero Turismatica scelto, o ``None`` se va chiesto.
    id_turismatica: str | None
    #: ``prova`` · ``ricordato`` · ``cin`` · ``nome`` · ``da_chiedere``
    motivo: str
    #: Le strutture da proporre, le più somiglianti prima.
    proposte: list[str] = field(default_factory=list)
    #: Perché si chiede, in parole da gestore.
    domanda: str = ""


def abbina(
    gruppi: Sequence[Gruppo],
    strutture: Sequence[StrutturaNota],
    alias: Mapping[str, str],
) -> list[Abbinamento]:
    ids = {s.id_turismatica for s in strutture}
    per_cin = (
        {_codice(s.cin): s.id_turismatica for s in strutture}
        if cin_affidabile(strutture) else {}
    )
    risultato: list[Abbinamento] = []
    for g in gruppi:
        proposte = [
            s.id_turismatica
            for s in sorted(
                strutture, key=lambda s: -somiglianza(g.nome_nel_file, s.nome),
            )
        ]
        if g.di_prova:
            risultato.append(Abbinamento(
                g, None, "prova", proposte,
                "Sono i file inventati dello zip di prova: non sono di nessuna "
                "tua struttura. Puoi abbinarli a una delle tue solo per vedere "
                "il giro in modalità prova.",
            ))
            continue
        ricordato = next(
            (alias[k] for k in g.chiavi_alias() if alias.get(k) in ids), None,
        )
        if ricordato is not None:
            risultato.append(Abbinamento(g, ricordato, "ricordato"))
            continue
        dal_cin = per_cin.get(_codice(g.id_nel_nome or ""))
        if dal_cin is not None:
            risultato.append(Abbinamento(g, dal_cin, "cin"))
            continue
        uguali = [s for s in strutture if normalizza(s.nome) == normalizza(g.nome_nel_file)]
        if len(uguali) == 1 and normalizza(g.nome_nel_file):
            risultato.append(Abbinamento(g, uguali[0].id_turismatica, "nome"))
            continue
        risultato.append(Abbinamento(
            g, None, "da_chiedere", proposte,
            f"Nei file c'è scritto «{g.nome_nel_file or 'nessun nome'}»"
            + (f" (codice {g.id_nel_nome})" if g.id_nel_nome else "")
            + ": a quale delle tue strutture appartengono?",
        ))

    # Due gruppi sulla stessa struttura: è il caso in cui un automatismo
    # caricherebbe un mese sopra l'altro. Si chiede per entrambi.
    contati: dict[str, int] = {}
    for a in risultato:
        if a.id_turismatica is not None:
            contati[a.id_turismatica] = contati.get(a.id_turismatica, 0) + 1
    for a in risultato:
        if a.id_turismatica is not None and contati[a.id_turismatica] > 1:
            a.proposte = [a.id_turismatica] + [
                i for i in (s.id_turismatica for s in strutture) if i != a.id_turismatica
            ]
            a.id_turismatica, a.motivo = None, "da_chiedere"
            a.domanda = (
                "Più gruppi di file sembrano della stessa struttura: dimmi tu "
                f"a quale va «{a.gruppo.nome_nel_file or 'questo gruppo'}»."
            )
    return risultato
