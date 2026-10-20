"""Cos'è successo, detto a un albergatore.

Il riepilogo finale è la sola cosa che l'utente legge davvero, e non è un log:
un log racconta *cosa ha fatto il programma*, questo deve dire **cosa manca
ancora da fare**. Per questo le categorie non sono «ok / errore» ma quattro, e
ognuna ha un rimedio diverso:

* **caricato** — fatto adesso;
* **già caricato** — c'era di già. Non è un errore e non va contato come tale:
  rilanciare sullo stesso mese dev'essere innocuo, altrimenti l'utente non lo
  rifà mai quando invece serve;
* **file mancante** — il .txt di quel giorno non c'era. Il rimedio è in
  HostLab (riscaricare), non qui;
* **non riuscito** — il portale non l'ha accettato. Il rimedio è riprovare, e
  se insiste guardare quel giorno a mano.

E una quinta, che esiste solo in **modalità prova**: **da caricare** — il
giorno è arrivato fino all'ultimo passo (dialog aperto, file scelto, «Carica»
pronto) e lì ci si è fermati. Non è «caricato», e il riepilogo non deve
lasciarlo intendere: è l'elenco di ciò che *partirebbe*.

⚠️ **«Non riuscito» non si fonde con «già caricato»**, che è la tentazione
naturale quando si conta solo il successo: sono la stessa riga non toccata con
due significati opposti — uno è a posto, l'altro è un adempimento che manca.
È lo stesso errore del contatore che si autodichiara riuscito mentre il lavoro
va perso.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class Esito(StrEnum):
    CARICATO = "caricato"
    GIA_CARICATO = "gia_caricato"
    FILE_MANCANTE = "file_mancante"
    NON_RIUSCITO = "non_riuscito"
    #: Solo in modalità prova: tutto pronto, «Carica» NON premuto.
    DA_CARICARE = "da_caricare"


@dataclass
class EsitoStruttura:
    """Come è andata per una struttura."""

    etichetta: str
    id_turismatica: str
    giorni: dict[date, Esito] = field(default_factory=dict)
    #: Perché la struttura è stata saltata **per intero**, se lo è stata.
    saltata: str | None = None
    #: Nomi di file che non dichiarano una data: quasi sempre la cartella sbagliata.
    non_riconosciuti: list[str] = field(default_factory=list)
    #: Il nome del file usato per ogni giorno toccato: in prova è la risposta
    #: a «cosa avresti caricato?», e il nome è anche ciò che dichiara la data.
    file: dict[date, str] = field(default_factory=dict)

    def segna(self, giorno: date, esito: Esito, file: str | None = None) -> None:
        self.giorni[giorno] = esito
        if file is not None:
            self.file[giorno] = file

    def quanti(self, esito: Esito) -> int:
        return sum(1 for e in self.giorni.values() if e is esito)

    def elenco(self, esito: Esito) -> list[date]:
        return sorted(g for g, e in self.giorni.items() if e is esito)

    @property
    def tutto_a_posto(self) -> bool:
        return self.saltata is None and not (
            self.quanti(Esito.NON_RIUSCITO) or self.quanti(Esito.FILE_MANCANTE)
        )


def _giorni(date_: list[date], massimo: int = 8) -> str:
    """Le date in chiaro. Oltre ``massimo`` si dice quante sono e basta: un
    elenco di trenta date non lo legge nessuno, e nasconde le due che contano."""
    if len(date_) > massimo:
        return f"{len(date_)} giorni (dal {date_[0]:%d/%m} al {date_[-1]:%d/%m})"
    return ", ".join(f"{d:%d/%m}" for d in date_)


def riepilogo(
    esiti: list[EsitoStruttura], periodo_etichetta: str, *, prova: bool,
) -> str:
    """Il testo finale. Nessun codice, nessuna riga di log: per ogni struttura
    cosa è a posto e **cosa resta da fare**.

    ⚠️ ``prova`` **non ha default**: un riepilogo di prova letto come uno vero
    farebbe credere caricato un mese che non lo è. In prova (e solo lì) si
    elencano i file giorno per giorno: è la cosa da controllare prima del giro
    vero."""
    if not esiti:
        return "Non c'era niente da caricare."

    righe: list[str] = []
    if prova:
        righe += [
            "MODALITÀ PROVA — NON HO CARICATO NIENTE.",
            "Ecco cosa avrei caricato. Il portale è rimasto com'era.",
            "",
        ]
    righe += [f"Periodo: {periodo_etichetta}", ""]
    da_fare: list[str] = []

    for e in esiti:
        if e.saltata:
            righe.append(f"■ {e.etichetta} — non fatta: {e.saltata}")
            da_fare.append(f"{e.etichetta}: {e.saltata}")
            righe.append("")
            continue

        fatti = e.quanti(Esito.CARICATO)
        gia = e.quanti(Esito.GIA_CARICATO)
        pronti = e.quanti(Esito.DA_CARICARE)
        parti = []
        if fatti:
            parti.append(f"{fatti} giorni caricati")
        if pronti:
            parti.append(f"{pronti} giorni da caricare")
        if gia:
            parti.append(f"{gia} già c'erano")
        righe.append(f"■ {e.etichetta} — " + (", ".join(parti) if parti else "niente da fare"))
        if prova:
            for g in e.elenco(Esito.DA_CARICARE):
                righe.append(f"   · {g:%d/%m/%Y}  ←  {e.file.get(g, '?')}")

        mancanti = e.elenco(Esito.FILE_MANCANTE)
        if mancanti:
            righe.append(f"   · manca il file di: {_giorni(mancanti)}")
            da_fare.append(
                f"{e.etichetta}: riscarica da HostLab i giorni mancanti "
                f"({_giorni(mancanti)}) e rilancia."
            )
        falliti = e.elenco(Esito.NON_RIUSCITO)
        if falliti:
            righe.append(f"   · NON caricati: {_giorni(falliti)}")
            da_fare.append(
                f"{e.etichetta}: riprova per {_giorni(falliti)}. Se non passa "
                "nemmeno al secondo giro, caricali a mano dal portale."
            )
        if e.non_riconosciuti:
            righe.append(
                f"   · {len(e.non_riconosciuti)} file nella cartella non sono "
                "movimenti giornalieri (li ho ignorati)"
            )
        righe.append("")

    if prova:
        righe.append(
            "Se l'elenco è giusto: passa alla MODALITÀ VERA e rilancia. "
            "I giorni che già c'erano li salto anche lì."
        )
        if da_fare:
            righe.append("")
    if not da_fare:
        if not prova:
            righe.append("Tutto a posto: non resta niente da fare.")
    else:
        righe.append("DA FARE:")
        righe.extend(f"  {i}. {r}" for i, r in enumerate(da_fare, 1))
    return "\n".join(righe).strip()
