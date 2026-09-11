"""Il periodo da caricare — logica pura, niente I/O.

La comunicazione a Turismatica è **mensile**, e il gesto normale è «il mese
scorso». Per questo il periodo si sceglie come mese, non come due date: due
campi data per dire «settembre» sono due occasioni di sbagliare, e l'errore si
scopre davanti al portale.

L'intervallo libero resta possibile — serve a rimediare a un buco — ma è la
strada secondaria, non il default.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MESI = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
)


@dataclass(frozen=True)
class Periodo:
    """Un intervallo di giorni, estremi **inclusi**."""

    dal: date
    al: date

    def __post_init__(self) -> None:
        if self.al < self.dal:
            raise ValueError(
                f"La data di fine ({self.al:%d/%m/%Y}) è prima di quella di "
                f"inizio ({self.dal:%d/%m/%Y})."
            )

    @property
    def giorni(self) -> list[date]:
        return [self.dal + timedelta(days=i) for i in range((self.al - self.dal).days + 1)]

    @property
    def etichetta(self) -> str:
        """Come si legge a schermo. Un mese pieno si dice col suo nome."""
        if self.dal.day == 1 and self.al == fine_mese(self.dal.year, self.dal.month):
            return f"{MESI[self.dal.month - 1]} {self.dal.year}"
        return f"dal {self.dal:%d/%m/%Y} al {self.al:%d/%m/%Y}"


def fine_mese(anno: int, mese: int) -> date:
    """L'ultimo giorno del mese, senza calendar né dateutil."""
    if mese == 12:
        return date(anno, 12, 31)
    return date(anno, mese + 1, 1) - timedelta(days=1)


def mese(anno: int, mese_n: int) -> Periodo:
    return Periodo(dal=date(anno, mese_n, 1), al=fine_mese(anno, mese_n))


def mese_scorso(oggi: date | None = None) -> Periodo:
    """Il default dell'app: il mese appena chiuso.

    ⚠️ ``oggi`` è un argomento e non ``date.today()`` cablato: una funzione che
    legge l'orologio da sola non si può provare, e il 1° gennaio è proprio il
    giorno in cui l'aritmetica sbaglia (il mese scorso è di un altro anno)."""
    # noqa DTZ011: è una data di calendario, non un istante — il periodo da
    # comunicare è «il mese scorso» dove sta il PC, non in UTC.
    riferimento = oggi if oggi is not None else date.today()  # noqa: DTZ011
    ultimo = riferimento.replace(day=1) - timedelta(days=1)
    return mese(ultimo.year, ultimo.month)


def da_campi(
    per_mese: bool, *, nome_mese: str, anno: str, dal: str, al: str,
) -> Periodo:
    """Il periodo scelto nella finestra, dai campi **così come sono scritti**.

    Sta qui e non nella finestra di proposito: è l'unico punto in cui l'utente
    può digitare qualcosa di sbagliato, e la logica di un campo dentro un widget
    non si prova. Solleva ``ValueError`` con un messaggio **già leggibile**, che
    la finestra mostra così com'è — nessuna traduzione in mezzo, nessuna
    occasione di dire due cose diverse.
    """
    if per_mese:
        try:
            numero = MESI.index(nome_mese.strip().lower()) + 1
        except ValueError:
            raise ValueError(f"«{nome_mese}» non è un mese.") from None
        try:
            return mese(int(anno), numero)
        except ValueError:
            raise ValueError(f"«{anno}» non è un anno.") from None
    return Periodo(dal=_data(dal), al=_data(al))


def _data(testo: str) -> date:
    from datetime import datetime

    try:
        # noqa DTZ007: data di calendario digitata dall'utente, senza ora.
        return datetime.strptime(testo.strip(), "%d/%m/%Y").date()  # noqa: DTZ007
    except ValueError:
        raise ValueError(
            f"«{testo.strip()}» non è una data: scrivila come 01/09/2026."
        ) from None
