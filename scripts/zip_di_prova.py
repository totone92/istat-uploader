"""Lo zip di prova: un mese di file ISTAT inventati, per provare l'app su un PC
dove non c'è nessun file vero.

    python scripts/zip_di_prova.py dist/prova-settembre-2026.zip

Lo costruisce il workflow e lo allega alla Release accanto all'.exe: **non si
committa**. Dentro:

* un file per ogni giorno di settembre 2026, ``schedine_istat_PROVA_<AAAAMMGG>.txt``
  (il nome che l'app riconosce), con numeri **inventati** ma coerenti fra loro
  e la struttura «STRUTTURA DI PROVA»;
* ``PROVA.txt``, il marcatore: se l'app lo trova, la modalità vera è bloccata
  per quello zip (``sorgente.Sorgente.di_prova``).

Il contenuto è il tracciato «TOLM» di Turismatica, reso da :func:`rendi`, che è
**la copia esatta** del renderer di HostLab (``hostlab/turismatica/tolm.py``):
lì è provato byte per byte contro i file di beb che il portale accetta, qui un
test esige che la copia dia gli stessi byte di un giorno reso da HostLab
(``tests/fixtures/tolm_hostlab_20260903.txt``). Nessun dato vero in nessuno dei
due.
"""
from __future__ import annotations

import random
import sys
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

NOME_STRUTTURA = "STRUTTURA DI PROVA"
MARCATORE = "PROVA.txt"
ANNO, MESE = 2026, 9
NOME_ZIP = "prova-settembre-2026.zip"
CAMERE = 4

TESTO_MARCATORE = """\
ZIP DI PROVA — Istat Uploader

Questi file sono INVENTATI: struttura «STRUTTURA DI PROVA», numeri a caso.
Servono a provare il programma in MODALITÀ PROVA, che arriva fino a «Carica»
e non carica niente.

Finché questo file è nello zip (o nella cartella), la modalità vera è
bloccata: non vanno mai caricati sul portale.
"""

# ─── il renderer: COPIA di hostlab/turismatica/tolm.py (non modificarla qui) ──

A_CAPO = "\r\n"
LARGHEZZA_NOME_STRUTTURA = 255
LARGHEZZA_SIGLA = 5
LARGHEZZA_NOME = 35
LARGHEZZA_NUMERO = 5
INTESTAZIONE_TABELLA = "Provenienza".ljust(LARGHEZZA_SIGLA + 1 + LARGHEZZA_NOME) + "|ARR. |PAR. |"

_ETICHETTE = (
    "Presenti notte precedente",
    "Arrivati.................",
    "Totale...................",
    "Partiti..................",
    "Presenti nella notte.....",
)
_CAMERE = "CAMERE OCCUPATE="
_GIORNO = "ARRIVATI E PARTITI DEL GIORNO "


@dataclass(frozen=True)
class RigaProvenienza:
    sigla: str
    nome: str
    arrivati: int
    partiti: int


@dataclass(frozen=True)
class GiornoTolm:
    giorno: date
    presenti_notte_precedente: int
    arrivati: int
    partiti: int
    presenti_notte: int
    camere_occupate: int
    righe: tuple[RigaProvenienza, ...]

    @property
    def totale(self) -> int:
        return self.presenti_notte_precedente + self.arrivati


def rendi(nome_struttura: str, g: GiornoTolm) -> bytes:
    """Il file del giorno, byte per byte come quelli che il portale accetta."""
    numeri = (
        g.presenti_notte_precedente, g.arrivati, g.totale, g.partiti,
        g.presenti_notte,
    )
    righe = [
        nome_struttura[:LARGHEZZA_NOME_STRUTTURA].ljust(LARGHEZZA_NOME_STRUTTURA),
        "",
        *(f"{etichetta}  {n}" for etichetta, n in zip(_ETICHETTE, numeri, strict=True)),
        f"{_CAMERE}{g.camere_occupate}",
        f"{_GIORNO}{g.giorno:%d-%m-%Y}",
        "",
        INTESTAZIONE_TABELLA,
        *(
            f"{r.sigla:<{LARGHEZZA_SIGLA}}|{r.nome[:LARGHEZZA_NOME]:<{LARGHEZZA_NOME}}"
            f"|{r.arrivati:>{LARGHEZZA_NUMERO}}|{r.partiti:>{LARGHEZZA_NUMERO}}|"
            for r in g.righe
        ),
    ]
    return A_CAPO.join(righe).encode("utf-8")


# ─── il mese inventato ────────────────────────────────────────────────────────

#: Province della griglia ufficiale (sigla, nome come nella griglia).
_PROVENIENZE = (
    ("BO", "BOLOGNA"), ("FI", "FIRENZE"), ("MI", "MILANO"), ("NA", "NAPOLI"),
    ("PG", "PERUGIA"), ("RM", "ROMA"), ("TO", "TORINO"), ("TR", "TERNI"),
)


@dataclass(frozen=True)
class _Gruppo:
    provenienza: tuple[str, str]
    persone: int
    partenza: date


def _righe(arrivi: list[_Gruppo], partenze: list[_Gruppo]) -> tuple[RigaProvenienza, ...]:
    conti: dict[tuple[str, str], list[int]] = {}
    for g in arrivi:
        conti.setdefault(g.provenienza, [0, 0])[0] += g.persone
    for g in partenze:
        conti.setdefault(g.provenienza, [0, 0])[1] += g.persone
    return tuple(
        RigaProvenienza(s, n, a, p) for (s, n), (a, p) in sorted(conti.items())
    )


def mese_inventato(seme: int = 2026) -> list[GiornoTolm]:
    """Settembre 2026 di una struttura immaginaria da ``CAMERE`` camere: gruppi
    di 1–3 persone che arrivano e ripartono. Deterministico (stesso seme, stessi
    file), e coerente come un mese vero: presenti di stanotte = presenti di ieri
    + arrivati − partiti, le provenienze sommano agli arrivati e ai partiti, le
    camere non superano ``CAMERE``. Si parte da una struttura vuota il 31/08."""
    caso = random.Random(seme)
    primo = date(ANNO, MESE, 1)
    giorni: list[GiornoTolm] = []
    in_casa: list[_Gruppo] = []
    giorno = primo
    while giorno.month == MESE:
        partiti = [g for g in in_casa if g.partenza == giorno]
        in_casa = [g for g in in_casa if g.partenza != giorno]
        prec = sum(g.persone for g in in_casa) + sum(g.persone for g in partiti)
        arrivati: list[_Gruppo] = []
        for _ in range(caso.randint(0, 2)):
            if len(in_casa) >= CAMERE:
                break
            gruppo = _Gruppo(
                provenienza=caso.choice(_PROVENIENZE),
                persone=caso.randint(1, 3),
                partenza=giorno + timedelta(days=caso.randint(1, 4)),
            )
            in_casa.append(gruppo)
            arrivati.append(gruppo)
        a = sum(g.persone for g in arrivati)
        p = sum(g.persone for g in partiti)
        giorni.append(GiornoTolm(
            giorno=giorno, presenti_notte_precedente=prec, arrivati=a, partiti=p,
            presenti_notte=prec + a - p, camere_occupate=len(in_casa),
            righe=_righe(arrivati, partiti),
        ))
        giorno += timedelta(days=1)
    return giorni


def nome_file(g: date) -> str:
    return f"schedine_istat_PROVA_{g:%Y%m%d}.txt"


def zip_di_prova(destinazione: Path) -> Path:
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destinazione, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(MARCATORE, TESTO_MARCATORE.replace("\n", A_CAPO))
        for g in mese_inventato():
            zf.writestr(nome_file(g.giorno), rendi(NOME_STRUTTURA, g))
    return destinazione


if __name__ == "__main__":
    uscita = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist") / NOME_ZIP
    print(zip_di_prova(uscita))
