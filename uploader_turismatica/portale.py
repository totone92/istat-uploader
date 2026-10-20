"""La meccanica del portale Turismatica.

⚠️ **Questa è la parte costata prove sul campo, ed è portata com'era.** I
selettori, la chiamata ``PrimeFaces.ab`` che apre il dialog, il campo file
nascosto da rendere visibile prima di scriverci, i tre tentativi sul bottone
«Carica»: non sono preferenze di stile, sono il risultato di tentativi contro
un portale JSF che non si comporta come una pagina normale. **Non semplificarli
senza riprovare dal vivo.**

Cosa NON c'è più rispetto allo script originale, e perché:

* i percorsi macOS e il binario di Chrome cablato — vedi ``chrome.py``;
* gli id struttura e i nomi cartella cablati — sono dati personali, non del
  prodotto: la struttura la dichiara l'utente (``strutture.py``);
* l'elenco delle strutture cessate cablato — **lo stato lo dice il portale**
  (``VALIDATA``/``CESSATA``), e una lista scritta a mano è una seconda verità
  che invecchia da sola. Lo script originale ce l'aveva per non restare
  bloccato 30 s su una pagina che non esiste; la lettura dello stato fa lo
  stesso lavoro senza dover ricordare niente.

⚠️ **Il login NON si automatizza**: qui dentro non c'è una riga che provi a
entrare. Si apre la pagina e si aspetta (``attendi_accesso``).
"""
from __future__ import annotations

import contextlib
import logging
import re
import time
from collections.abc import Callable, Collection
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from uploader_turismatica import messaggi
from uploader_turismatica.esito import Esito, EsitoStruttura
from uploader_turismatica.periodo import MESI, Periodo
from uploader_turismatica.sorgente import Sorgente, blocco_modalita_vera

log = logging.getLogger(__name__)

PREHOME_URL = "https://turismatica.regione.umbria.it/ntojsf/private/prehome.xhtml"
MOVIMENTI_URL = (
    "https://turismatica.regione.umbria.it/ntojsf/private/OSR/movimento/"
    "movimentoospiti.xhtml?idStruttura={}"
)

#: Id della tabella dei movimenti. I due punti vanno protetti nei selettori CSS.
_TABELLA = "movimentiTabView:tblMovimenti_data"
_TABELLA_CSS = "#movimentiTabView\\:tblMovimenti_data tr"
_DIALOG = (By.ID, "movimentiTabView:uploadFileDialog")
_CAMPO_FILE = (
    By.ID, "movimentiTabView:formUploadFile:fileUploadGiornoAperto_input",
)
_BOTTONE_CARICA = (
    By.CSS_SELECTOR,
    "#movimentiTabView\\:formUploadFile .ui-fileupload-upload:not([disabled])",
)
_ANNULLA_FILE = (
    By.CSS_SELECTOR,
    "#movimentiTabView\\:formUploadFile .ui-fileupload-cancel:not([disabled])",
)
_CHIUDI_DIALOG = (
    By.CSS_SELECTOR,
    "#movimentiTabView\\:uploadFileDialog .ui-dialog-titlebar-close",
)

#: Tentativi sul bottone «Carica». ⚠️ Tre, e non uno: il click è intercettato da
#: sovrapposizioni PrimeFaces con una frequenza che si vede solo sul portale
#: vero. Era così nello script originale e resta così.
TENTATIVI_CARICA = 3

#: File mancanti di fila dopo i quali si smette con questa struttura. Il senso è
#: che tre buchi consecutivi non sono tre giorni senza movimento — quelli hanno
#: comunque il file — ma la cartella sbagliata o un download interrotto:
#: continuare per altri ventisette giorni non aggiunge informazione.
MANCANTI_DI_FILA = 3

#: Pausa fra un giorno e l'altro: il portale è un JSF che ricostruisce la
#: tabella a ogni upload. Gentile di proposito.
PAUSA_FRA_GIORNI_S = 0.5

Avanzamento = Callable[[str], None]


def registra_giorno(
    id_turismatica: str, giorno: date, esito: Esito, file: str, errore: str,
) -> None:
    """Una riga del registro per giorno: è la riga che si rimanda quando
    qualcosa non va. Solo il numero della struttura, il giorno, l'esito, il
    **nome** del file (che dichiara la data, non chi ha dormito) e l'errore —
    mai il contenuto del file né un percorso."""
    livello = logging.WARNING if esito is Esito.NON_RIUSCITO else logging.INFO
    log.log(
        livello, "struttura=%s giorno=%s esito=%s file=%s%s",
        id_turismatica, f"{giorno:%d/%m/%Y}", esito.value, file or "-",
        f" errore={errore}" if errore else "",
    )


def _in_breve(exc: BaseException) -> str:
    """Il tipo e la prima riga dell'errore: Selenium allega pagine di stack del
    driver che nel registro non servono a nessuno."""
    prima = (str(exc).splitlines() or [""])[0][:200]
    return f"{type(exc).__name__}: {prima}" if prima else type(exc).__name__


class PortaleNonRaggiungibile(Exception):
    """La pagina dei movimenti non si è aperta affatto."""


# ─── decisioni pure (provabili senza portale) ────────────────────────────────


def stato_utilizzabile(stato: str | None) -> bool:
    """Si può caricare su una struttura in questo stato?

    ``None`` ⇒ **sì**: lo stato non è stato trovato in pagina, e fermarsi per
    un'etichetta che non si è letta significherebbe non caricare mai su un
    portale che cambia una classe CSS. Chi non sa, prova — qui il tentativo
    costa poco e il falso negativo costa un adempimento."""
    return stato is None or stato.strip().upper() == "VALIDATA"


def tabella_sul_mese_giusto(prima_riga: date | None, atteso: date) -> bool:
    """La tabella si è aperta sul mese che stiamo caricando?

    Il portale ricorda l'ultimo mese guardato: se apre su un altro, le righe
    sono di giorni diversi da quelli che cerchiamo e l'accoppiamento data→riga
    caricherebbe il file sbagliato sulla riga sbagliata. ``None`` (data non
    leggibile) ⇒ si prosegue: l'accoppiamento avviene comunque **per testo
    della data**, riga per riga, quindi il rischio vero è già coperto."""
    if prima_riga is None:
        return True
    return (prima_riga.month, prima_riga.year) == (atteso.month, atteso.year)


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


class ContatoreMancanti:
    """Quanti file mancanti di fila, e quando smettere."""

    def __init__(self, soglia: int = MANCANTI_DI_FILA) -> None:
        self.soglia = soglia
        self.di_fila = 0

    def manca(self) -> bool:
        """Registra un file mancante. ``True`` se si deve smettere."""
        self.di_fila += 1
        return self.di_fila >= self.soglia

    def trovato(self) -> None:
        self.di_fila = 0


# ─── il login: si aspetta, non si fa ─────────────────────────────────────────


def apri_portale(driver: WebDriver) -> None:
    """Apre la pagina d'ingresso e **si ferma lì**."""
    driver.get(PREHOME_URL)


def sembra_dentro(driver: WebDriver) -> bool:
    """L'utente è entrato? Euristica **a favore dell'utente**: serve solo a
    proseguire da sé quando è evidente. Se sbaglia, il bottone «Sono dentro»
    c'è comunque — nessuna decisione importante dipende da questa funzione."""
    try:
        url = driver.current_url or ""
    except WebDriverException:
        return False
    return "prehome" not in url and "/private/" in url


# ─── il caricamento di una struttura ─────────────────────────────────────────


def carica_struttura(
    driver: WebDriver,
    *,
    id_turismatica: str,
    etichetta: str,
    sorgente: Sorgente,
    periodo: Periodo,
    prova: bool,
    strutture_note: Collection[str],
    avanzamento: Avanzamento | None = None,
) -> EsitoStruttura:
    """Carica i giorni del periodo per **una** struttura — o, con ``prova``,
    arriva fino all'ultimo passo di ogni giorno e non lo fa (``carica_giorno``).

    Non solleva per i problemi di quella struttura: li mette nell'esito. Il
    chiamante passa alla successiva — una struttura rotta non deve togliere il
    giro alle altre."""
    def dillo(msg: str) -> None:
        log.info("[%s] %s", etichetta, msg)
        if avanzamento is not None:
            avanzamento(msg)

    esito = EsitoStruttura(etichetta=etichetta, id_turismatica=id_turismatica)
    esito.non_riconosciuti = list(sorgente.non_riconosciuti)

    # Prima di toccare il portale: lo zip di prova non va mai in modalità vera.
    # La finestra lo ferma già prima di aprire Chrome; questo è il muro sotto.
    bloccata = blocco_modalita_vera(sorgente, prova=prova)
    if bloccata is not None:
        esito.saltata = bloccata
        dillo(f"salto: {bloccata}")
        return esito

    dillo(f"apro la pagina dei movimenti di {etichetta}")
    problema = apri_movimenti(
        driver, id_turismatica, periodo.dal, strutture_note=strutture_note,
    )
    if problema is not None:
        esito.saltata = problema
        dillo(f"salto: {problema}")
        return esito

    attesa = WebDriverWait(driver, 30)
    passi = _PassiSelenium(driver, attesa)
    contatore = ContatoreMancanti()
    for giorno in periodo.giorni:
        file = sorgente.file_del(giorno)
        if file is None:
            # Senza file, ma forse il portale ce l'ha già: allora non manca
            # niente, e non deve contare fra i «mancanti di fila».
            riga = passi.riga(giorno)
            if riga is not None and giorno_gia_caricato(*riga):
                esito.segna(giorno, Esito.GIA_CARICATO)
                registra_giorno(id_turismatica, giorno, Esito.GIA_CARICATO, "", "")
                continue
            esito.segna(giorno, Esito.FILE_MANCANTE)
            registra_giorno(id_turismatica, giorno, Esito.FILE_MANCANTE, "", "")
            if contatore.manca():
                dillo(
                    f"{MANCANTI_DI_FILA} file mancanti di fila: mi fermo con "
                    f"{etichetta}"
                )
                for restante in periodo.giorni[periodo.giorni.index(giorno) + 1:]:
                    if restante not in esito.giorni:
                        esito.segna(restante, Esito.FILE_MANCANTE)
                break
            continue
        contatore.trovato()

        dillo(f"{giorno:%d/%m/%Y}")
        try:
            risultato = carica_giorno(passi, giorno, file, prova=prova)
            errore = ""
        except Exception as exc:            # noqa: BLE001 — un giorno non ferma il mese
            risultato = Esito.NON_RIUSCITO
            errore = _in_breve(exc)
        esito.segna(giorno, risultato, file.name)
        registra_giorno(id_turismatica, giorno, risultato, file.name, errore)
        time.sleep(PAUSA_FRA_GIORNI_S)

    return esito


class Passi(Protocol):
    """I passi di **un** giorno sul portale, uno per metodo.

    Esistono come interfaccia per una ragione sola: separare *cosa si fa* (la
    sequenza, e soprattutto **se l'ultimo passo si fa**) da *come lo si fa sul
    portale* (selettori, ``PrimeFaces.ab``, il campo nascosto). La sequenza è
    nostra e si prova con un finto di **questa** interfaccia; il «come» resta
    in ``_PassiSelenium`` e si prova solo dal vivo — un finto browser
    riprodurrebbe ciò che abbiamo capito del portale, non il portale."""

    def riga(self, giorno: date) -> tuple[list[str], list[str], list[str]] | None: ...

    def apri_dialog(self, giorno: date) -> bool:
        """Apre il dialog di caricamento. ``False`` se la riga non ha il pulsante."""
        ...

    def scegli_file(self, file: Path) -> None: ...

    def pronto(self) -> bool:
        """«Carica» è premibile, cioè il portale ha accettato il file scelto."""
        ...

    def conferma(self) -> bool:
        """Preme «Carica» — **il punto di non ritorno**. ``True`` se il dialog
        si è chiuso, che è l'unica conferma che il portale dà."""
        ...

    def annulla(self) -> None:
        """Chiude il dialog senza caricare."""
        ...


def carica_giorno(passi: Passi, giorno: date, file: Path, *, prova: bool) -> Esito:
    """Il giorno, dall'inizio alla fine. Ritorna l'esito di quel giorno.

    ⚠️ **In prova si fa tutto tranne ``conferma``**: dialog aperto, file
    scelto, «Carica» pronto — poi ``annulla``. È la sola differenza fra le due
    modalità, ed è qui, in una riga, perché due percorsi scritti a parte
    finirebbero per divergere proprio nel passo che conta. ``prova`` non ha
    default: dimenticarlo non deve voler dire caricare.

    Un giorno già caricato **non si tocca in nessuna delle due**: ricaricarlo
    lo sostituirebbe (manuale della Regione), anche una correzione fatta a mano
    sul portale."""
    riga = passi.riga(giorno)
    if riga is not None and giorno_gia_caricato(*riga):
        return Esito.GIA_CARICATO
    if not passi.apri_dialog(giorno):
        # Non caricato e niente pulsante: il portale non apre ancora questo
        # giorno (di solito manca il precedente). È un adempimento che manca,
        # non «già caricato».
        log.warning("%s: non caricato e il portale non lo apre", f"{giorno:%d/%m/%Y}")
        return Esito.NON_RIUSCITO
    passi.scegli_file(file)
    if prova:
        pronto = passi.pronto()
        passi.annulla()
        return Esito.DA_CARICARE if pronto else Esito.NON_RIUSCITO
    if passi.conferma():
        return Esito.CARICATO
    passi.annulla()
    return Esito.NON_RIUSCITO


class _PassiSelenium:
    """I passi sul portale vero. ⚠️ **La meccanica è quella dello script
    originale, spostata e non riscritta**: non semplificarla senza riprovare
    dal vivo.

    Le righe si rileggono a ogni giro: dopo un upload PrimeFaces ricostruisce
    la tabella e i riferimenti presi prima sono ``stale``."""

    def __init__(self, driver: WebDriver, attesa: WebDriverWait) -> None:
        self.driver = driver
        self.attesa = attesa

    def riga(self, giorno: date) -> tuple[list[str], list[str], list[str]] | None:
        return _leggi_riga(self.driver, giorno)

    def apri_dialog(self, giorno: date) -> bool:
        bottone = _bottone_upload_della_riga(self.driver, giorno)
        if bottone is None:
            return False
        # Il dialog si apre da JS: il click "normale" sul bottone non basta,
        # perché è PrimeFaces a dover eseguire il suo ciclo (``ps:true`` =
        # partial submit, ``u:`` = cosa aggiornare, ``onco:`` = che fare dopo
        # la risposta).
        bid = bottone.get_attribute("id")  # type: ignore[attr-defined]
        self.driver.execute_script(
            "PrimeFaces.ab({"
            f"s:'{bid}',p:'{bid}',u:'movimentiTabView:uploadFileDialog',"
            "ps:true,onco:function(){PF('uploadFileDialog').show();}});"
        )
        self.attesa.until(EC.visibility_of_element_located(_DIALOG))
        return True

    def scegli_file(self, file: Path) -> None:
        # Il campo file è nascosto (``display:none``): Selenium non scrive su
        # un elemento invisibile, quindi lo si rende visibile e poi gli si
        # passa il percorso. È il modo standard di caricare un file senza
        # toccare la finestra di dialogo del sistema operativo — che Selenium
        # non può guidare. ⚠️ Scegliere il file NON carica: il fileUpload del
        # portale non è automatico, aspetta «Carica».
        campo = self.attesa.until(EC.presence_of_element_located(_CAMPO_FILE))
        self.driver.execute_script("arguments[0].style.display='block';", campo)
        campo.send_keys(str(file.resolve()))

    def pronto(self) -> bool:
        try:
            self.attesa.until(EC.element_to_be_clickable(_BOTTONE_CARICA))
            return True
        except (TimeoutException, WebDriverException) as exc:
            log.warning("«Carica» non è diventato premibile: %s", exc)
            return False

    def conferma(self) -> bool:
        for tentativo in range(TENTATIVI_CARICA):
            try:
                carica = self.attesa.until(EC.element_to_be_clickable(_BOTTONE_CARICA))
                self.driver.execute_script("arguments[0].click();", carica)
                # La chiusura del dialog è la conferma: il portale non dà altro.
                self.attesa.until(EC.invisibility_of_element_located(_DIALOG))
                return True
            except (
                StaleElementReferenceException,
                ElementClickInterceptedException,
                TimeoutException,
                WebDriverException,
            ) as exc:
                log.warning(
                    "tentativo %d/%d su «Carica» fallito: %s",
                    tentativo + 1, TENTATIVI_CARICA, exc,
                )
                time.sleep(1)
        return False

    def annulla(self) -> None:
        # Prima si toglie il file scelto (il «Annulla» del fileUpload), poi si
        # chiude il dialog: così non resta niente in coda per il giorno dopo.
        with contextlib.suppress(WebDriverException):
            for el in self.driver.find_elements(*_ANNULLA_FILE):
                self.driver.execute_script("arguments[0].click();", el)
        _chiudi_dialog(self.driver)
        with contextlib.suppress(TimeoutException, WebDriverException):
            WebDriverWait(self.driver, 10).until(
                EC.invisibility_of_element_located(_DIALOG)
            )


def apri_movimenti(
    driver: WebDriver, id_turismatica: str, mese: date, *,
    strutture_note: Collection[str],
) -> str | None:
    """Apre la pagina dei movimenti della struttura **sul mese voluto**.
    ``None`` se è pronta; altrimenti il messaggio per il gestore (cosa è
    successo e cosa fare). Sola lettura: apre, legge, al più cambia mese."""
    driver.get(MOVIMENTI_URL.format(id_turismatica))
    stato = _stato_struttura(driver)
    if not stato_utilizzabile(stato):
        assert stato is not None
        return messaggi.struttura_non_attiva(id_turismatica, stato)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, _TABELLA))
        )
    except TimeoutException:
        return messaggi.perche_movimenti_non_aperti(
            id_turismatica,
            url=_url(driver), testo_pagina=_testo_visibile(driver),
            strutture_note=strutture_note,
        )
    if not vai_al_mese(driver, mese):
        prima = _prima_data_in_tabella(driver)
        mostrato = f"{MESI[prima.month - 1]} {prima.year}" if prima else "un altro mese"
        return messaggi.mese_non_raggiunto(mostrato, f"{MESI[mese.month - 1]} {mese.year}")
    return None


def _url(driver: WebDriver) -> str:
    try:
        return driver.current_url or ""
    except WebDriverException:
        return ""


def _testo_visibile(driver: WebDriver) -> str:
    try:
        return str(driver.execute_script("return document.body ? document.body.innerText : ''"))
    except WebDriverException:
        return ""


#: Comandi che **cambiano mese** nella pagina dei movimenti: frecce del
#: calendario o del paginatore, «precedente»/«successivo». ⚠️ Mai un comando
#: che scriva: chi parla di caricare, salvare, inviare, confermare, eliminare
#: o modificare è escluso, e il dialog di caricamento è fuori dalla ricerca.
_JS_COMANDO_MESE = r"""
const verso = arguments[0];   // 'indietro' | 'avanti'
const segni = verso === 'indietro'
  ? /precedent|indietro|prev|seek-prev|angle-left|chevron-left|arrow-left|triangle-1-w|circle-triangle-w/i
  : /successiv|avanti|next|seek-next|angle-right|chevron-right|arrow-right|triangle-1-e|circle-triangle-e/i;
const vietati = /carica|upload|salva|save|invia|submit|conferm|elimin|cancell|delete|modific|nuov/i;
const dialog = document.getElementById('movimentiTabView:uploadFileDialog');
for (const el of document.querySelectorAll('a, button, [role="button"], span.ui-paginator-prev, span.ui-paginator-next')) {
  if (dialog && dialog.contains(el)) continue;
  const tabella = document.getElementById('movimentiTabView:tblMovimenti_data');
  if (tabella && tabella.contains(el)) continue;
  if (el.getAttribute('aria-disabled') === 'true' || el.classList.contains('ui-state-disabled') || el.disabled) continue;
  const icone = [...el.querySelectorAll('[class]')].map(e => e.getAttribute('class')).join(' ');
  const descr = [el.innerText, el.getAttribute('title'), el.getAttribute('aria-label'),
                 el.getAttribute('class'), icone].join(' ');
  if (vietati.test(descr)) continue;
  if (segni.test(descr)) return el;
}
return null;
"""
MAX_PASSI_MESE = 13


def vai_al_mese(driver: WebDriver, voluto: date) -> bool:
    """Porta la tabella sul mese voluto. ``True`` se ci è (o ci era già).

    Il portale ricorda l'ultimo mese guardato. Qui si cerca il comando che
    cambia mese (vedi ``_JS_COMANDO_MESE``), si preme, si aspetta che la prima
    data della tabella cambi, e si ripete al massimo ``MAX_PASSI_MESE`` volte.
    Se il comando non c'è o la data non si muove: ``False``, e il messaggio lo
    dice al gestore (che può aprire il mese a mano)."""
    for _ in range(MAX_PASSI_MESE):
        prima = _prima_data_in_tabella(driver)
        if prima is None or tabella_sul_mese_giusto(prima, voluto):
            return True
        verso = "indietro" if (voluto.year, voluto.month) < (prima.year, prima.month) else "avanti"
        try:
            comando = driver.execute_script(_JS_COMANDO_MESE, verso)
        except WebDriverException:
            return False
        if comando is None:
            log.warning("comando per cambiare mese non trovato (verso %s)", verso)
            return False
        driver.execute_script("arguments[0].click();", comando)
        try:
            WebDriverWait(driver, 15).until(
                lambda d, p=prima: _prima_data_in_tabella(d) not in (None, p)
            )
        except TimeoutException:
            log.warning("il mese non è cambiato dopo il comando (verso %s)", verso)
            return False
    return tabella_sul_mese_giusto(_prima_data_in_tabella(driver), voluto)


#: Tutte le righe del mese mostrato: data, celle, classi, titoli, pulsante.
_JS_RIGHE = r"""
const out = [];
const corpo = document.getElementById('movimentiTabView:tblMovimenti_data');
for (const tr of (corpo ? corpo.querySelectorAll('tr') : [])) {
  const td = tr.querySelectorAll('td');
  if (td.length < 2) continue;
  out.push({
    celle: [...td].map(c => (c.innerText || '').trim()),
    classi: [...tr.querySelectorAll('[class*="fa-"]')].map(e => e.getAttribute('class') || ''),
    titoli: [...tr.querySelectorAll('[title]')].map(e => e.getAttribute('title') || ''),
    pulsante: !!tr.querySelector('button .fa-upload, button[class*="upload"]'),
  });
}
return out;
"""


def righe_lette(dati: object) -> list[tuple[date, bool, bool]]:
    """Dalle righe grezze del portale: ``(giorno, già caricato, ha il
    pulsante)``. Pura: la stessa regola di ``giorno_gia_caricato``."""
    out: list[tuple[date, bool, bool]] = []
    if not isinstance(dati, list):
        return out
    for r in dati:
        if not isinstance(r, dict):
            continue
        celle = [str(x) for x in r.get("celle") or []]
        if len(celle) < 2:
            continue
        m = re.search(r"(\d{2}/\d{2}/\d{4})", celle[1])
        if m is None:
            continue
        try:
            giorno = datetime.strptime(m.group(1), "%d/%m/%Y").date()  # noqa: DTZ007
        except ValueError:
            continue
        classi = [str(x) for x in r.get("classi") or []]
        titoli = [str(x) for x in r.get("titoli") or []]
        out.append((giorno, giorno_gia_caricato(celle, classi, titoli), bool(r.get("pulsante"))))
    return out


def leggi_mese(driver: WebDriver) -> list[tuple[date, bool, bool]]:
    try:
        return righe_lette(driver.execute_script(_JS_RIGHE))
    except WebDriverException:
        return []


def _chiudi_dialog(driver: WebDriver) -> None:
    """Chiude il dialog rimasto aperto dopo un fallimento. Se resta aperto, il
    giorno dopo non trova la tabella e fallisce anche lui: un errore si porta
    dietro tutto il mese."""
    with contextlib.suppress(WebDriverException):
        driver.execute_script(
            "arguments[0].click();", driver.find_element(*_CHIUDI_DIALOG),
        )


def _stato_struttura(driver: WebDriver) -> str | None:
    """Lo stato in testata (``VALIDATA``, ``CESSATA``, …). ``None`` se assente."""
    try:
        el = driver.find_element(By.CSS_SELECTOR, "div.stato")
        testo = el.text or (el.get_attribute("class") or "").split("stato")[-1]
        return testo.strip().upper() or None
    except (NoSuchElementException, WebDriverException):
        return None


def _prima_data_in_tabella(driver: WebDriver) -> date | None:
    try:
        testo = driver.find_element(
            By.CSS_SELECTOR,
            "#movimentiTabView\\:tblMovimenti_data tr td:nth-child(2)",
        ).text.strip()
        # noqa DTZ007: è la data della riga del portale, un giorno di
        # calendario senza ora né fuso.
        return datetime.strptime(testo, "%d/%m/%Y").date()  # noqa: DTZ007
    except (NoSuchElementException, WebDriverException, ValueError):
        return None


#: La riga di un giorno in una chiamata sola: testo delle celle, classi delle
#: icone, e i ``title`` (dove il portale scrive «File caricato: …»).
_JS_RIGA = r"""
const atteso = arguments[0];
for (const tr of document.querySelectorAll('#movimentiTabView\\:tblMovimenti_data tr')) {
  const td = tr.querySelectorAll('td');
  if (td.length < 2 || !(td[1].innerText || '').trim().endsWith(atteso)) continue;
  return {
    celle: [...td].map(c => (c.innerText || '').trim()),
    classi: [...tr.querySelectorAll('[class*="fa-"]')].map(e => e.getAttribute('class') || ''),
    titoli: [...tr.querySelectorAll('[title]')].map(e => e.getAttribute('title') || ''),
  };
}
return null;
"""


def _leggi_riga(
    driver: WebDriver, giorno: date,
) -> tuple[list[str], list[str], list[str]] | None:
    """Celle, classi e titoli della riga di quel giorno, o ``None`` se non c'è.
    Per testo della data, come il bottone: mai per posizione."""
    try:
        r = driver.execute_script(_JS_RIGA, f"{giorno:%d/%m/%Y}")
    except WebDriverException:
        return None
    if not isinstance(r, dict):
        return None
    return (
        [str(x) for x in r.get("celle") or []],
        [str(x) for x in r.get("classi") or []],
        [str(x) for x in r.get("titoli") or []],
    )


def _bottone_upload_della_riga(driver: WebDriver, giorno: date) -> object | None:
    """Il bottone «carica» della riga di quel giorno, o ``None`` se non c'è.

    L'accoppiamento è **per testo della data** nella seconda colonna, non per
    posizione: la posizione dipende da come il portale ordina le righe, e
    sbagliare riga significa dichiarare il movimento di un giorno su un altro."""
    atteso = f"{giorno:%d/%m/%Y}"
    for riga in driver.find_elements(By.CSS_SELECTOR, _TABELLA_CSS):
        try:
            celle = riga.find_elements(By.TAG_NAME, "td")
            if len(celle) < 2 or not celle[1].text.strip().endswith(atteso):
                continue
            return riga.find_element(
                By.XPATH, ".//button[.//span[contains(@class,'fa-upload')]]"
            )
        except NoSuchElementException:
            return None
        except StaleElementReferenceException:
            continue
    return None
