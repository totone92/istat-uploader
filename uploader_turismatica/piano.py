"""Lo stato dei giorni sul portale e il piano prima di caricare — logica pura.

Il piano si dice **prima** di aprire Chrome, in una frase per struttura e mese:
«Settembre 2026, Casa Lavanda: 28 giorni già presenti, 2 da caricare (12 e 19)».
Viene dallo stato letto sul portale l'ultima volta (con l'ora di lettura) e dai
file abbinati. ⚠️ **È una previsione, non una decisione**: durante il giro ogni
giorno si rilegge sul portale prima di toccarlo (``portale.carica_giorno``),
quindi un giorno caricato a mano nel frattempo si salta lo stesso.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from uploader_turismatica.periodo import MESI, Periodo, fine_mese


class StatoGiorno(StrEnum):
    #: Il portale ha il movimento di quel giorno.
    CARICATO = "caricato"
    #: Manca, e il portale lo lascia caricare.
    DA_FARE = "da_fare"
    #: Manca, e il portale non lo apre ancora (di solito manca il precedente).
    NON_APERTO = "non_aperto"


@dataclass
class StatoMese:
    anno: int
    mese: int
    #: Solo i giorni **letti** sul portale; un giorno assente è sconosciuto.
    giorni: dict[int, StatoGiorno] = field(default_factory=dict)
    letto_il: datetime | None = None

    @property
    def chiave(self) -> str:
        return f"{self.anno:04d}-{self.mese:02d}"

    @property
    def etichetta(self) -> str:
        return f"{MESI[self.mese - 1]} {self.anno}"

    def caricati(self) -> list[int]:
        return sorted(g for g, s in self.giorni.items() if s is StatoGiorno.CARICATO)

    def mancanti(self, oggi: date) -> list[int]:
        """I giorni passati che sul portale non ci sono (oggi e il futuro no:
        il movimento di un giorno si chiude a fine giornata)."""
        ultimo = _ultimo_giorno_utile(self.anno, self.mese, oggi)
        return [
            g for g in range(1, ultimo + 1)
            if self.giorni.get(g) in (StatoGiorno.DA_FARE, StatoGiorno.NON_APERTO)
        ]

    def da_json(self) -> dict[str, object]:
        return {
            "giorni": {str(g): s.value for g, s in sorted(self.giorni.items())},
            "letto_il": self.letto_il.isoformat(timespec="minutes") if self.letto_il else None,
        }

    @classmethod
    def dal_json(cls, chiave: str, dati: Mapping[str, object]) -> StatoMese:
        anno, mese = (int(x) for x in chiave.split("-"))
        giorni_raw = dati.get("giorni") or {}
        assert isinstance(giorni_raw, dict)
        letto = dati.get("letto_il")
        return cls(
            anno, mese,
            {int(g): StatoGiorno(s) for g, s in giorni_raw.items()},
            datetime.fromisoformat(letto) if isinstance(letto, str) else None,
        )


def _ultimo_giorno_utile(anno: int, mese: int, oggi: date) -> int:
    fine = fine_mese(anno, mese)
    if (anno, mese) < (oggi.year, oggi.month):
        return fine.day
    if (anno, mese) > (oggi.year, oggi.month):
        return 0
    return oggi.day - 1


def stato_dalle_righe(
    righe: Iterable[tuple[date, bool, bool]], *, anno: int, mese: int,
    letto_il: datetime,
) -> StatoMese:
    """Dalle righe lette sul portale: ``(giorno, già caricato, ha il pulsante)``."""
    s = StatoMese(anno, mese, letto_il=letto_il)
    for giorno, caricato, pulsante in righe:
        if (giorno.year, giorno.month) != (anno, mese):
            continue
        s.giorni[giorno.day] = (
            StatoGiorno.CARICATO if caricato
            else StatoGiorno.DA_FARE if pulsante
            else StatoGiorno.NON_APERTO
        )
    return s


def elenco_giorni(giorni: list[int], massimo: int = 6) -> str:
    """«12 e 19» · «3, 4 e 9» · oltre ``massimo``: «dal 3 al 28 (14 giorni)»."""
    if not giorni:
        return ""
    if len(giorni) > massimo:
        return f"dal {giorni[0]} al {giorni[-1]} ({len(giorni)} giorni)"
    if len(giorni) == 1:
        return str(giorni[0])
    return ", ".join(str(g) for g in giorni[:-1]) + f" e {giorni[-1]}"


def _giorni(n: int) -> str:
    return "1 giorno" if n == 1 else f"{n} giorni"


@dataclass
class VocePiano:
    id_turismatica: str
    nome: str
    anno: int
    mese: int
    #: I giorni che hanno un file, in questo mese.
    con_file: list[int]
    #: ``None`` = stato del portale mai letto per questo mese.
    presenti: list[int] | None
    da_caricare: list[int]
    #: Giorni passati che mancano sul portale e non hanno un file nello zip.
    senza_file: list[int]
    #: File di giorni futuri: non si caricano.
    futuri: list[int]
    letto_il: datetime | None = None

    @property
    def etichetta_mese(self) -> str:
        return f"{MESI[self.mese - 1]} {self.anno}"

    @property
    def periodo(self) -> Periodo | None:
        """I giorni da percorrere sul portale. ``None`` = niente da fare."""
        if not self.da_caricare:
            return None
        return Periodo(
            date(self.anno, self.mese, self.da_caricare[0]),
            date(self.anno, self.mese, self.da_caricare[-1]),
        )

    @property
    def testo(self) -> str:
        mese = self.etichetta_mese.capitalize()
        if self.presenti is None:
            return (
                f"{mese}, {self.nome}: {_giorni(len(self.da_caricare))} nei file. "
                "Lo stato sul portale non l'ho ancora letto: lo controllo giorno "
                "per giorno durante il giro, e salto quelli già presenti."
            )
        parti = [f"{_giorni(len(self.presenti))} già presenti"]
        if self.da_caricare:
            parti.append(f"{len(self.da_caricare)} da caricare "
                         f"({elenco_giorni(self.da_caricare)})")
        else:
            parti.append("niente da caricare")
        testo = f"{mese}, {self.nome}: " + ", ".join(parti) + "."
        if self.senza_file:
            testo += (f" Sul portale mancano anche {elenco_giorni(self.senza_file)}, "
                      "ma nello zip non c'è il file.")
        return testo


def costruisci(
    abbinati: Iterable[tuple[str, str, Iterable[date]]],
    stati: Mapping[str, Mapping[str, StatoMese]],
    oggi: date,
) -> list[VocePiano]:
    """``abbinati``: (numero Turismatica, nome, giorni con un file).
    ``stati``: numero Turismatica → chiave ``AAAA-MM`` → stato letto."""
    voci: list[VocePiano] = []
    for ident, nome, giorni in abbinati:
        per_mese: dict[tuple[int, int], list[int]] = {}
        for g in giorni:
            per_mese.setdefault((g.year, g.month), []).append(g.day)
        for (anno, mese), con_file in sorted(per_mese.items()):
            con_file.sort()
            ultimo = _ultimo_giorno_utile(anno, mese, oggi)
            utili = [g for g in con_file if g <= ultimo]
            futuri = [g for g in con_file if g > ultimo]
            stato = stati.get(ident, {}).get(f"{anno:04d}-{mese:02d}")
            if stato is None or not stato.giorni:
                voci.append(VocePiano(ident, nome, anno, mese, con_file, None,
                                      utili, [], futuri))
                continue
            presenti = stato.caricati()
            voci.append(VocePiano(
                ident, nome, anno, mese, con_file, presenti,
                [g for g in utili if g not in presenti],
                [g for g in stato.mancanti(oggi) if g not in con_file],
                futuri, stato.letto_il,
            ))
    return voci
