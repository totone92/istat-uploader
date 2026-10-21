"""Una sessione sul portale: Chrome aperto, il gestore entra con SPID/CIE, poi
letture (le strutture, lo stato dei giorni) o caricamenti.

``Portale`` è l'interfaccia che usa il flusso dell'app (``api.Api``): i test
ne usano una finta, l'app ``SessioneSelenium``. Così il flusso intero —
riconoscimento, scelte, riepilogo, piano, giro — si prova senza browser, e la
meccanica del portale resta tutta in ``portale.py``.

⚠️ **Le letture sono sole letture**: aprono pagine, leggono tabelle, al più
cambiano il mese mostrato. Mai un clic su qualcosa che scriva.
"""
from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from uploader_turismatica import riconoscimento
from uploader_turismatica.chrome import apri_chrome
from uploader_turismatica.esito import EsitoStruttura
from uploader_turismatica.periodo import Periodo
from uploader_turismatica.piano import StatoMese, stato_dalle_righe
from uploader_turismatica.portale import (
    PREHOME_URL,
    Copie,
    apri_movimenti,
    apri_portale,
    carica_struttura,
    leggi_mese,
    pagina,
    sembra_dentro,
)
from uploader_turismatica.riconoscimento import StrutturaTrovata
from uploader_turismatica.sorgente import Sorgente

log = logging.getLogger(__name__)

#: Quanto aspettare la tendina delle strutture in ``prehome`` (secondi).
ATTESA_ELENCO_S = 20.0


@dataclass
class LetturaStrutture:
    strutture: list[StrutturaTrovata]
    #: La copia ripulita della pagina, se la lettura non ha trovato niente.
    copia_pagina: Path | None = None


@dataclass
class LetturaMesi:
    #: ``AAAA-MM`` → stato letto (solo i mesi che si sono potuti leggere).
    mesi: dict[str, StatoMese] = field(default_factory=dict)
    #: Il problema, in parole da gestore ('' se tutto letto).
    avviso: str = ""
    #: L'intestazione della pagina dei movimenti (nome, comune, tipologia,
    #: CIR, CIN), se si è aperta.
    struttura: StrutturaTrovata | None = None


class Portale(Protocol):
    def apri(self) -> None: ...
    def dentro(self) -> bool: ...
    def leggi_strutture(self) -> LetturaStrutture: ...
    def leggi_mesi(
        self, id_turismatica: str, mesi: Sequence[date], *, strutture_note: Collection[str],
    ) -> LetturaMesi: ...
    def carica(
        self, *, id_turismatica: str, etichetta: str, sorgente: Sorgente,
        periodo: Periodo | None, prova: bool, strutture_note: Collection[str],
        comunica: date | None, avanzamento: Callable[[str], None],
    ) -> EsitoStruttura: ...
    def chiudi(self) -> None: ...


class SessioneSelenium:
    """Il portale vero, attraverso Chrome."""

    def __init__(self, cartella_copie: Path, ora: Callable[[], datetime]) -> None:
        self._copie = Copie(cartella_copie, ora)
        self._ora = ora
        self._driver: WebDriver | None = None

    @property
    def driver(self) -> WebDriver:
        assert self._driver is not None, "prima apri()"
        return self._driver

    def apri(self) -> None:
        self._driver = apri_chrome()
        apri_portale(self._driver)

    def dentro(self) -> bool:
        return self._driver is not None and sembra_dentro(self._driver)

    def leggi_strutture(self) -> LetturaStrutture:
        """L'elenco da ``prehome.xhtml`` («Seleziona la struttura su cui vuoi
        operare»), dove il portale lo mostra dopo l'accesso. Se lì non c'è
        (un account con una struttura sola potrebbe saltare la scelta), dalla
        pagina in cui si è atterrati e dai link che parlano di strutture (al
        più tre, solo ``href`` veri)."""
        atterrata = self._sorgente()
        visitate = [PREHOME_URL]
        with contextlib.suppress(WebDriverException):
            self.driver.get(PREHOME_URL)
        pagina = self._aspetta_elenco()
        trovate = riconoscimento.strutture(pagina)
        if not trovate:
            pagina = atterrata
            trovate = riconoscimento.strutture(pagina)
        if not trovate:
            candidati = riconoscimento.link_da_seguire(pagina, self._url())
            for url in candidati:
                if url in visitate:
                    continue
                visitate.append(url)
                try:
                    self.driver.get(url)
                except WebDriverException:
                    continue
                pagina = self._sorgente()
                trovate = riconoscimento.strutture(pagina)
                if trovate:
                    break
        if trovate:
            log.info("strutture lette dal portale: %s",
                     ", ".join(s.id_turismatica for s in trovate))
            return LetturaStrutture(trovate)
        copia = self._copie.salva("pagina-strutture", pagina)
        log.warning("elenco delle strutture non letto; copia della pagina: %s",
                    copia.name if copia else "non salvata")
        return LetturaStrutture([], copia)

    def leggi_mesi(
        self, id_turismatica: str, mesi: Sequence[date], *, strutture_note: Collection[str],
    ) -> LetturaMesi:
        out = LetturaMesi()
        problema = apri_movimenti(
            self.driver, id_turismatica, strutture_note=strutture_note, copie=self._copie,
        )
        out.struttura = pagina(self.driver).struttura
        if problema is not None:
            # La copia della pagina l'ha già salvata ``apri_movimenti``.
            out.avviso = problema
            log.warning("struttura %s: %s", id_turismatica, problema)
            return out
        for mese in mesi:
            letto = leggi_mese(self.driver, mese, copie=self._copie)
            if letto.righe:
                stato = stato_dalle_righe(
                    [(r.giorno, r.caricato, bool(r.id_carica)) for r in letto.righe],
                    anno=mese.year, mese=mese.month, letto_il=self._ora(),
                    chiuso=letto.chiuso, invio_possibile=letto.invio_possibile,
                )
                out.mesi[stato.chiave] = stato
            elif letto.chiuso:
                stato = StatoMese(mese.year, mese.month, letto_il=self._ora(), chiuso=True)
                out.mesi[stato.chiave] = stato
            if letto.problema is not None:
                log.warning("struttura %s, %s: %s", id_turismatica, f"{mese:%m/%Y}", letto.problema)
                if not letto.chiuso:
                    out.avviso = letto.problema
        return out

    def carica(
        self, *, id_turismatica: str, etichetta: str, sorgente: Sorgente,
        periodo: Periodo | None, prova: bool, strutture_note: Collection[str],
        comunica: date | None, avanzamento: Callable[[str], None],
    ) -> EsitoStruttura:
        return carica_struttura(
            self.driver, id_turismatica=id_turismatica, etichetta=etichetta,
            sorgente=sorgente, periodo=periodo, prova=prova,
            strutture_note=strutture_note, comunica=comunica, avanzamento=avanzamento,
            copie=self._copie,
        )

    def chiudi(self) -> None:
        if self._driver is not None:
            with contextlib.suppress(Exception):
                self._driver.quit()
            self._driver = None

    # ── interni ──────────────────────────────────────────────────────────────

    def _aspetta_elenco(self) -> str:
        """La pagina di ``prehome`` quando la tendina delle strutture c'è
        davvero. Appena entrati il portale può essere ancora a metà (prima prova
        del 20/10: elenco non letto al primo avvio, letto al secondo): si
        rilegge ogni mezzo secondo per ``ATTESA_ELENCO_S`` e poi si prende
        quello che c'è."""
        fine = time.monotonic() + ATTESA_ELENCO_S
        while True:
            pagina = self._sorgente()
            if riconoscimento.strutture(pagina) or time.monotonic() >= fine:
                return pagina
            time.sleep(0.5)

    def _sorgente(self) -> str:
        try:
            return self.driver.page_source or ""
        except WebDriverException:
            return ""

    def _url(self) -> str:
        try:
            return self.driver.current_url or ""
        except WebDriverException:
            return ""
