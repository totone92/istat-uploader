"""La pagina dei movimenti di una struttura, letta dal suo HTML — logica pura.

Tutto ciò che il programma deve **sapere** della pagina si ricava da qui, e
qui si prova sulle copie vere (``tests/fixtures/turismatica/movimenti.html``).
A Selenium restano i clic: un bottone si preme **per id**, e l'id lo dà questa
lettura. Così la regola che decide «già caricato / da caricare» è la stessa nei
test e sul portale, invece di vivere in un JavaScript che si prova solo dal vivo.

Com'è fatta la pagina (ottobre 2026):

* ``movimentiTabView`` è un TabView PrimeFaces **dinamico** (il contenuto di
  una scheda arriva quando la si apre). Schede: «Comunicazioni telematiche»,
  «Movimento periodo chiuso», «Movimento periodo aperto», «Chiusure
  temporanee». Si guarda solo il pannello **attivo** (``aria-hidden="false"``).
* Nel periodo aperto: i bottoni ``monthButtonText``/``monthButtonNoText``
  («Mese precedente»/«Mese successivo», icone ``fa-arrow-left/right``),
  **disattivati** (``ui-state-disabled``) quando di là non c'è un mese aperto.
* La tabella ``movimentiTabView:tblMovimenti``: «!», Data, Presenze notte
  precedente, Arrivi, Partenze, Presenze, Unità occupate, poi i bottoni,
  riconoscibili dal ``title``: «inserisci i dati…» (``fa-pencil``), «carica da
  FILE…» (``fa-upload``), «file caricato» (``fa-file-text-o``), «nessun nuovo
  movimento fino a questo giorno» (``fa-angle-double-down``). Il bottone di
  caricamento c'è **solo sul primo giorno non ancora inserito**: i giorni si
  caricano in fila.
* Sotto, «Azioni» → «Invia comunicazione telematica mensile», attivo solo a
  mese concluso (fino al 5 del mese dopo).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from uploader_turismatica.riconoscimento import (
    Nodo,
    StrutturaTrovata,
    albero,
    intestazione,
)

_DATA = re.compile(r"^\s*(\d{2}/\d{2}/\d{4})\s*$")
_MESI_IT = (
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
    "agosto", "settembre", "ottobre", "novembre", "dicembre",
)
SCHEDA_APERTO = "movimento periodo aperto"
SCHEDA_CHIUSO = "movimento periodo chiuso"
INVIO_MENSILE = "invia comunicazione telematica mensile"


#: Le colonne dei valori del movimento nella tabella del portale: «!», Data,
#: Presenze notte precedente, **Arrivi, Partenze, Presenze, Unità occupate**,
#: poi le icone.
_VALORI = slice(3, 7)


def giorno_gia_caricato(
    celle: list[str], classi: list[str], titoli: list[str] | None = None,
) -> bool:
    """Il portale ha già il movimento di questo giorno?

    ⚠️ **Il pulsante di caricamento NON lo dice** — era il criterio di prima, ed
    è sbagliato: il pulsante **resta anche dopo**, perché serve a sostituire il
    file (APPUNTI-ISTAT del job del Mac mini, 22/09/2026: la verifica diceva
    «non caricato» di otto giorni che il portale aveva preso davvero). Peggio,
    al rovescio: un giorno che il portale non apre ancora (manca il
    precedente) non ha il pulsante, e veniva contato «già caricato» — un
    adempimento mancante dichiarato a posto.

    I segni veri, letti dalla tabella dopo un caricamento riuscito:

    * la scritta **«File caricato: <nome>»** (la mette il portale);
    * l'icona del **documento** (``fa-file…``), che c'è solo sui giorni inviati;
    * i **valori del movimento** (arrivi, partenze, presenze, unità occupate)
      presenti **anche se tutti zero**, e senza la doppia freccia
      (``fa-angle-double-down``) che il portale mette sui giorni che non ha.
      «Presenze notte precedente» no: quella la calcola il portale da sé.

    Un giorno corretto a mano dall'interfaccia perde il documento ma resta
    dentro: per questo contano anche i valori."""
    testi = [*celle, *(titoli or [])]
    if any("file caricato" in t.lower() for t in testi):
        return True
    if any("fa-file" in c for c in classi):
        return True
    da_fare = any("fa-angle-double-down" in c for c in classi)
    valori = [c.strip() for c in celle[_VALORI]]
    return len(valori) == 4 and all(valori) and not da_fare


@dataclass
class RigaPortale:
    giorno: date
    #: Celle nella forma fissa: «!», Data, notte precedente, Arrivi, Partenze,
    #: Presenze, Unità occupate — qualunque sia l'ordine delle colonne in pagina.
    celle: list[str]
    classi: list[str]
    titoli: list[str]
    #: L'id del bottone «carica da FILE», se la riga ce l'ha.
    id_carica: str = ""

    @property
    def caricato(self) -> bool:
        return giorno_gia_caricato(self.celle, self.classi, self.titoli)

    @property
    def grezza(self) -> tuple[list[str], list[str], list[str]]:
        return self.celle, self.classi, self.titoli


@dataclass
class Bottone:
    id: str
    attivo: bool


@dataclass
class PaginaMovimenti:
    struttura: StrutturaTrovata | None
    #: Testo della scheda aperta, in minuscolo ('' se la pagina non ha schede).
    scheda: str = ""
    #: Testo della scheda → indice (``data-index``), per aprirla.
    schede: dict[str, int] = field(default_factory=dict)
    righe: list[RigaPortale] = field(default_factory=list)
    #: «Mese precedente» / «Mese successivo» nella scheda aperta.
    indietro: Bottone | None = None
    avanti: Bottone | None = None
    invio_mensile: Bottone | None = None
    #: Il mese scritto fra le frecce («Ottobre 2026»), se c'è.
    titolo_mese: date | None = None

    @property
    def mese(self) -> date | None:
        """Il primo giorno del mese mostrato: dalle righe, o dal titolo."""
        if self.righe:
            g = self.righe[0].giorno
            return g.replace(day=1)
        return self.titolo_mese

    def riga(self, giorno: date) -> RigaPortale | None:
        return next((r for r in self.righe if r.giorno == giorno), None)

    @property
    def frecce(self) -> bool:
        return self.indietro is not None or self.avanti is not None


def _classi(n: Nodo) -> list[str]:
    return n.attrs.get("class", "").split()


def _attivo(n: Nodo) -> bool:
    return "disabled" not in n.attrs and "ui-state-disabled" not in _classi(n)


def _pannello_attivo(radice: Nodo) -> Nodo | None:
    for n in radice.discendenti():
        if "ui-tabs-panel" in _classi(n) and n.attrs.get("aria-hidden") == "false":
            return n
    return None


def _schede(radice: Nodo) -> tuple[str, dict[str, int]]:
    attiva, tutte = "", {}
    for n in radice.discendenti():
        if n.tag != "li" or "ui-tabs-header" not in _classi(n):
            continue
        testo = n.testo().lower()
        try:
            tutte[testo] = int(n.attrs.get("data-index", ""))
        except ValueError:
            continue
        if n.attrs.get("aria-selected") == "true" or "ui-state-active" in _classi(n):
            attiva = testo
    return attiva, tutte


def _colonne(tabella: Nodo | None) -> dict[str, int]:
    """Nome della colonna → posizione, dalle intestazioni (``aria-label`` o testo)."""
    if tabella is None:
        return {}
    out: dict[str, int] = {}
    for riga in (n for n in tabella.discendenti() if n.tag == "tr"):
        celle = [c for c in riga.figli if isinstance(c, Nodo) and c.tag in ("th", "td")]
        if not celle or not all(c.tag == "th" for c in celle):
            continue
        for i, c in enumerate(celle):
            nome = (c.attrs.get("aria-label") or c.testo()).strip().lower()
            if nome and nome not in out:
                out[nome] = i
        return out
    return out


#: Le colonne che servono, nella forma fissa che si aspetta ``giorno_gia_caricato``.
_FORMA = ("", "data", "presenze notte precedente", "arrivi", "partenze", "presenze",
          "unità occupate")


def _riga(tr: Nodo, colonne: dict[str, int]) -> RigaPortale | None:
    celle = [c for c in tr.figli if isinstance(c, Nodo) and c.tag == "td"]
    testi = [c.testo() for c in celle]
    pos_data = colonne.get("data")
    if pos_data is None or pos_data >= len(testi) or not _DATA.match(testi[pos_data]):
        pos_data = next((i for i, t in enumerate(testi) if _DATA.match(t)), None)
    if pos_data is None:
        return None
    m = _DATA.match(testi[pos_data])
    assert m is not None
    try:
        giorno = datetime.strptime(m.group(1), "%d/%m/%Y").date()  # noqa: DTZ007
    except ValueError:
        return None
    if all(k in colonne for k in _FORMA[2:]):
        forma = ["", m.group(1)] + [
            testi[colonne[k]] if colonne[k] < len(testi) else "" for k in _FORMA[2:]
        ]
    else:
        # Senza intestazioni riconoscibili: la posizione della tabella vera.
        forma = (["", m.group(1)] + testi[pos_data + 1:pos_data + 6] + [""] * 5)[:7]
    discendenti = tr.discendenti()
    classi = [d.attrs["class"] for d in discendenti if "fa-" in d.attrs.get("class", "")]
    titoli = [d.attrs["title"] for d in discendenti if d.attrs.get("title")]
    id_carica = next(
        (d.attrs.get("id", "") for d in discendenti
         if d.tag == "button" and any("fa-upload" in x.attrs.get("class", "")
                                      for x in d.discendenti())),
        "",
    )
    return RigaPortale(giorno, forma, classi, titoli, id_carica)


def _righe(pannello: Nodo) -> list[RigaPortale]:
    """Le righe datate della prima tabella del pannello che ne ha."""
    for corpo in (n for n in pannello.discendenti() if n.tag == "tbody"):
        tabella = corpo.antenato("table")
        colonne = _colonne(tabella)
        righe = [
            r for tr in corpo.figli
            if isinstance(tr, Nodo) and tr.tag == "tr" and (r := _riga(tr, colonne)) is not None
        ]
        if righe:
            return righe
    return []


def _bottone_mese(pannello: Nodo, verso: str) -> Bottone | None:
    icona = "fa-arrow-left" if verso == "indietro" else "fa-arrow-right"
    trovati = [
        b for b in pannello.discendenti()
        if b.tag == "button"
        and {"monthButtonText", "monthButtonNoText"} & set(_classi(b))
        and any(icona in d.attrs.get("class", "") for d in b.discendenti())
    ]
    if not trovati:
        return None
    # Il bottone col testo prima («Mese precedente»): l'altro è il gemello
    # per schermi stretti, stesso comando.
    trovati.sort(key=lambda b: "monthButtonText" not in _classi(b))
    attivi = [b for b in trovati if _attivo(b)]
    scelto = attivi[0] if attivi else trovati[0]
    return Bottone(scelto.attrs.get("id", ""), _attivo(scelto))


def _titolo_mese(pannello: Nodo) -> date | None:
    for n in pannello.discendenti():
        if "ui-panel-content" not in _classi(n):
            continue
        m = re.fullmatch(r"\s*([A-Za-z]+)\s+(\d{4})\s*", n.testo())
        if m and m.group(1).lower() in _MESI_IT:
            return date(int(m.group(2)), _MESI_IT.index(m.group(1).lower()) + 1, 1)
    return None


def _invio(pannello: Nodo) -> Bottone | None:
    for b in pannello.discendenti():
        if b.tag == "button" and INVIO_MENSILE in b.testo().lower():
            return Bottone(b.attrs.get("id", ""), _attivo(b))
    return None


def leggi_pagina(pagina: str) -> PaginaMovimenti:
    radice = albero(pagina)
    scheda, schede = _schede(radice)
    pannello = _pannello_attivo(radice) or radice
    return PaginaMovimenti(
        struttura=intestazione(pagina),
        scheda=scheda,
        schede=schede,
        righe=_righe(pannello),
        indietro=_bottone_mese(pannello, "indietro"),
        avanti=_bottone_mese(pannello, "avanti"),
        invio_mensile=_invio(pannello),
        titolo_mese=_titolo_mese(pannello),
    )


def verso(mostrato: date | None, voluto: date) -> str | None:
    """Da che parte andare: ``indietro``, ``avanti`` o ``None`` (ci siamo, o
    non si sa quale mese è mostrato)."""
    if mostrato is None or (mostrato.year, mostrato.month) == (voluto.year, voluto.month):
        return None
    return "indietro" if (voluto.year, voluto.month) < (mostrato.year, mostrato.month) else "avanti"


def mese_nel_dialogo(testo: str) -> date | None:
    """Il mese che il dialogo di conferma dice di comunicare («…per il mese
    Ottobre 2026…»). Serve a non comunicare il mese sbagliato."""
    m = re.search(r"per il mese\s+([A-Za-z]+)\s+(\d{4})", testo, re.IGNORECASE)
    if m is None or m.group(1).lower() not in _MESI_IT:
        return None
    return date(int(m.group(2)), _MESI_IT.index(m.group(1).lower()) + 1, 1)
