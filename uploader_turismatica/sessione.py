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
    apri_movimenti,
    apri_portale,
    carica_struttura,
    leggi_mese,
    sembra_dentro,
)
from uploader_turismatica.riconoscimento import StrutturaTrovata
from uploader_turismatica.sorgente import Sorgente

log = logging.getLogger(__name__)


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


class Portale(Protocol):
    def apri(self) -> None: ...
    def dentro(self) -> bool: ...
    def leggi_strutture(self) -> LetturaStrutture: ...
    def leggi_mesi(
        self, id_turismatica: str, mesi: Sequence[date], *, strutture_note: Collection[str],
    ) -> LetturaMesi: ...
    def carica(
        self, *, id_turismatica: str, etichetta: str, sorgente: Sorgente,
        periodo: Periodo, prova: bool, strutture_note: Collection[str],
        avanzamento: Callable[[str], None],
    ) -> EsitoStruttura: ...
    def chiudi(self) -> None: ...


class SessioneSelenium:
    """Il portale vero, attraverso Chrome."""

    def __init__(self, cartella_copie: Path, ora: Callable[[], datetime]) -> None:
        self._cartella_copie = cartella_copie
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
        """L'elenco dalla pagina in cui il gestore è atterrato; se lì non c'è,
        dalla pagina d'ingresso e dai link che parlano di strutture (al più
        tre, solo ``href`` veri)."""
        visitate: list[str] = []
        pagina = self._sorgente()
        trovate = riconoscimento.strutture(pagina)
        if not trovate:
            candidati = [PREHOME_URL, *riconoscimento.link_da_seguire(pagina, self._url())]
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
        copia = self._salva_copia("pagina-strutture", pagina)
        log.warning("elenco delle strutture non letto; copia della pagina: %s",
                    copia.name if copia else "non salvata")
        return LetturaStrutture([], copia)

    def leggi_mesi(
        self, id_turismatica: str, mesi: Sequence[date], *, strutture_note: Collection[str],
    ) -> LetturaMesi:
        out = LetturaMesi()
        for mese in mesi:
            problema = apri_movimenti(
                self.driver, id_turismatica, mese, strutture_note=strutture_note,
            )
            righe = leggi_mese(self.driver)
            # Anche se il mese voluto non si è raggiunto, quello mostrato si
            # legge lo stesso: è comunque un'informazione vera.
            for giorno_mese in {(g.year, g.month) for g, _, _ in righe}:
                stato = stato_dalle_righe(
                    righe, anno=giorno_mese[0], mese=giorno_mese[1], letto_il=self._ora(),
                )
                out.mesi[stato.chiave] = stato
            if problema is not None:
                out.avviso = problema
                log.warning("struttura %s, %s: %s", id_turismatica, f"{mese:%m/%Y}", problema)
                if not righe:
                    self._salva_copia(f"pagina-movimenti-{id_turismatica}", self._sorgente())
                    break
        return out

    def carica(
        self, *, id_turismatica: str, etichetta: str, sorgente: Sorgente,
        periodo: Periodo, prova: bool, strutture_note: Collection[str],
        avanzamento: Callable[[str], None],
    ) -> EsitoStruttura:
        return carica_struttura(
            self.driver, id_turismatica=id_turismatica, etichetta=etichetta,
            sorgente=sorgente, periodo=periodo, prova=prova,
            strutture_note=strutture_note, avanzamento=avanzamento,
        )

    def chiudi(self) -> None:
        if self._driver is not None:
            with contextlib.suppress(Exception):
                self._driver.quit()
            self._driver = None

    # ── interni ──────────────────────────────────────────────────────────────

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

    def _salva_copia(self, nome: str, pagina: str) -> Path | None:
        """La copia **ripulita** (``riconoscimento.ripulisci``) accanto al
        registro, da mandare a chi sistema la lettura."""
        if not pagina:
            return None
        try:
            self._cartella_copie.mkdir(parents=True, exist_ok=True)
            p = self._cartella_copie / f"{nome}-{self._ora():%Y%m%d-%H%M%S}.html"
            p.write_text(riconoscimento.ripulisci(pagina), encoding="utf-8")
            return p
        except OSError:
            log.exception("copia della pagina non salvata")
            return None
