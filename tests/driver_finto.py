"""Un driver Selenium finto che serve le pagine VERE del portale.

Serve a far passare i test dal codice vero di ``sessione.SessioneSelenium`` e
``portale.py`` — stesse chiamate, stesse firme — invece che da un doppio di
``Portale`` scritto a parte. È così che è scappato il guasto della v1.3.0: il
doppio aveva la firma giusta, il codice vero chiamava ``apri_movimenti`` con un
argomento di troppo, e lo si è scoperto sul PC di Marco.

Cosa fa:

* ``get(url)``: ``prehome.xhtml`` → la copia vera di prehome;
  ``movimentoospiti.xhtml?idStruttura=N`` → la copia vera dei movimenti **come
  la mostra Chrome dopo il JavaScript** (``movimenti-dopo-js.html``: PrimeFaces
  aggiunge l'etichetta della colonna in ogni cella — il guasto della v1.3.1),
  con il numero 12345 sostituito da N (intestazione, CIR, CIN, link: coerenti);
* con ``ricorda_scelta=True`` imita un portale che **ignora** l'indirizzo e
  apre la struttura scelta l'ultima volta in prehome, finché non se ne sceglie
  un'altra con la tendina e «Accedi»;
* il dialog di caricamento si apre con ``PrimeFaces.ab`` e si chiude col suo
  bottone di chiusura;
* le schede dinamiche non cambiano niente: della scheda «Movimento periodo
  chiuso» non abbiamo una copia vera, e inventarla proverebbe solo ciò che
  abbiamo immaginato.

In modalità vera «Carica» aggiunge alla riga il segno «File caricato» e passa il
bottone al giorno dopo. Con ``carica_accettato=False`` il dialog si chiude e la
riga non cambia (il guasto che la conferma deve scoprire); con ``tabella_vecchia``
i segni si vedono solo riaprendo la pagina; con ``scade_dopo=N`` la sessione
finisce dopo N caricamenti, e ogni pagina diventa il login finché non si
chiama ``rientra``.

Ogni ``execute_script`` e ogni bottone premuto restano in ``self.registro``.

⚠️ Il finto non è Chrome: selettori e JavaScript li prova ``test_chrome_vero.py``.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from uploader_turismatica.portale import MOVIMENTI_URL, PREHOME_URL

CARTELLA = Path(__file__).parent / "fixtures" / "turismatica"
_PREHOME = (CARTELLA / "prehome.html").read_text(encoding="utf-8")
_MOVIMENTI = (CARTELLA / "movimenti-dopo-js.html").read_text(encoding="utf-8")
#: La struttura selezionata nella copia vera di prehome.
SCELTA_INIZIALE = "12341"
LOGIN_URL = "https://identity.example/spid/login"
_LOGIN = "<html><head><title>Accesso</title></head><body>Accedi con SPID</body></html>"
#: Le righe della copia vera dei movimenti: 01-20 ottobre 2026.
_PRIMO_GIORNO = date(2026, 10, 1)
_RIGHE = 20


def movimenti_di(id_turismatica: str) -> str:
    return _MOVIMENTI.replace("12345", id_turismatica.zfill(5))


class ElementoFinto:
    def __init__(self, driver: DriverFinto, chi: str) -> None:
        self._driver, self.chi = driver, chi

    def is_displayed(self) -> bool:
        if self.chi == "movimentiTabView:uploadFileDialog":
            return self._driver.dialog_aperto
        return True

    def is_enabled(self) -> bool:
        return True

    def send_keys(self, testo: str) -> None:
        self._driver.registro.append(f"send_keys:{Path(testo).name}")

    def get_attribute(self, nome: str) -> str:
        return self.chi if nome == "id" else ""

    @property
    def text(self) -> str:
        return ""


class DriverFinto:
    def __init__(self, *, ricorda_scelta: bool = False, prehome_lenta: int = 0,
                 carica_accettato: bool = True, tabella_vecchia: bool = False,
                 scade_dopo: int | None = None, caricati: set[date] | None = None) -> None:
        self._url = "about:blank"
        self._pagina = ""
        self.ricorda_scelta = ricorda_scelta
        self.scelta = SCELTA_INIZIALE
        #: Quante letture di prehome restituiscono la pagina ancora vuota.
        self.prehome_lenta = prehome_lenta
        self.dialog_aperto = False
        self.registro: list[str] = []
        self.carica_accettato = carica_accettato
        self.tabella_vecchia = tabella_vecchia
        self.scade_dopo = scade_dopo
        self.scaduta = False
        self.caricati: set[date] = set(caricati or ())
        #: I giorni che la pagina aperta mostra caricati (``tabella_vecchia``).
        self._mostrati: set[date] = set(self.caricati)
        self.pressioni_carica = 0

    def rientra(self) -> None:
        self.scaduta = False
        self._url, self._pagina = PREHOME_URL, _PREHOME
        self.registro.append("rientro")

    def _primo_aperto(self) -> date:
        return next(_PRIMO_GIORNO.replace(day=g) for g in range(1, _RIGHE + 1)
                    if _PRIMO_GIORNO.replace(day=g) not in self.caricati)

    def _con_i_segni(self, html: str) -> str:
        """I segni che il portale metterebbe sulle righe dei giorni caricati."""
        visti = self.caricati if not self.tabella_vecchia else self._mostrati
        if not visti or "tblMovimenti_data" not in html:
            return html
        primo_aperto = next((g for g in range(1, _RIGHE + 1)
                             if _PRIMO_GIORNO.replace(day=g) not in visti), None)
        for g in range(1, _RIGHE + 1):
            testa = f'<tr data-ri="{g - 1}" '
            i = html.find(testa, html.find("tblMovimenti_data"))
            fine = html.find(">", i) + 1
            if _PRIMO_GIORNO.replace(day=g) in visti:
                coda = html.find("</tr>", fine)
                riga = html[fine:coda].replace("fa-upload", "fa-sostituisci")
                html = (html[:fine] + '<span title="File caricato: finto.txt"></span>'
                        + riga + html[coda:])
            elif g == primo_aperto:
                html = (html[:fine] + f'<button id="carica-{g}"><span class="fa-upload"></span></button>'
                        + html[fine:])
        return html

    # ── navigazione ─────────────────────────────────────────────────────────

    def get(self, url: str) -> None:
        self.registro.append(f"get:{url}")
        self._mostrati = set(self.caricati)
        if self.scaduta:
            self._url, self._pagina = LOGIN_URL, _LOGIN
            return
        self._url = url
        if url == PREHOME_URL:
            self._pagina = _PREHOME
            return
        m = re.search(r"idStruttura=(\d+)", url)
        if m is not None:
            ident = self.scelta if self.ricorda_scelta else m.group(1)
            self._pagina = movimenti_di(ident)
            return
        self._pagina = "<html><body></body></html>"

    @property
    def current_url(self) -> str:
        return LOGIN_URL if self.scaduta else self._url

    @property
    def page_source(self) -> str:
        if self.scaduta:
            return _LOGIN
        if self._url == PREHOME_URL and self.prehome_lenta > 0:
            self.prehome_lenta -= 1
            return "<html><body><div class='caricamento'></div></body></html>"
        return self._con_i_segni(self._pagina)

    @property
    def title(self) -> str:
        m = re.search(r"<title>([^<]*)</title>", self._pagina)
        return m.group(1) if m else ""

    def quit(self) -> None:
        self.registro.append("quit")

    # ── elementi ────────────────────────────────────────────────────────────

    def find_element(self, by: str, valore: str) -> ElementoFinto:
        return ElementoFinto(self, valore)

    def find_elements(self, by: str, valore: str) -> list[ElementoFinto]:
        return [ElementoFinto(self, valore)]

    # ── JavaScript ──────────────────────────────────────────────────────────

    def execute_script(self, script: str, *argomenti: Any) -> Any:
        if "document.body.innerText" in script and self.scaduta:
            return "Accedi con SPID"
        if 'select[id$="_input"]' in script:                      # scelta in prehome
            ident = str(argomenti[0])
            self.registro.append(f"scegli:{ident}")
            if f'value="{ident}"' not in self._pagina:
                return "assente"
            self.scelta = ident
            self._url = MOVIMENTI_URL.format(ident)
            self._pagina = movimenti_di(ident)
            return "ok"
        if "PF('tabView')" in script:
            self.registro.append(f"scheda:{argomenti[0]}")
            return None
        if "document.body.innerText" in script:
            return re.sub(r"<[^>]+>", " ", self._pagina)
        if "uploadFileDialog" in script and "PrimeFaces.ab" in script:
            self.registro.append("apri_dialog")
            self.dialog_aperto = True
            return None
        if "getElementById(arguments[0]).click()" in script:
            self.registro.append(f"premi:{argomenti[0]}")
            return None
        if script.startswith("arguments[0].click()"):
            elemento = argomenti[0]
            chi = getattr(elemento, "chi", "")
            self.registro.append(f"click:{chi}")
            if "titlebar-close" in chi:
                self.dialog_aperto = False
            if "ui-fileupload-upload" in chi:
                self.pressioni_carica += 1
                self.dialog_aperto = False
                if self.carica_accettato:
                    self.caricati.add(self._primo_aperto())
                if self.scade_dopo is not None and len(self.caricati) >= self.scade_dopo:
                    self.scade_dopo, self.scaduta = None, True
            return None
        if "comunicazione telematica mensile" in script:
            return None
        self.registro.append("script")
        return None
