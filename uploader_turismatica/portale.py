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

Il portale vero (pagine di ottobre 2026, in ``tests/fixtures/turismatica/``):
cosa si **legge** sta in ``pagina_movimenti`` (Python, provato sulle copie);
qui restano i clic — per id, con l'id trovato da quella lettura.

* l'elenco delle strutture è in ``prehome.xhtml``; per entrare in una si va
  diretti a ``movimentoospiti.xhtml?idStruttura=…`` e, se il portale apre
  un'altra struttura o nessuna tabella, si passa da ``prehome`` come il
  gestore (tendina, «Accedi»): ``apri_movimenti``;
* i mesi: le frecce si muovono solo fra i mesi **aperti**; un mese prima di
  quelli è nel «periodo chiuso» e si legge da quella scheda (``leggi_mese``);
* la comunicazione mensile è l'ultimo passo, solo se chiesta
  (``invia_comunicazione``).

⚠️ **«Nessun nuovo movimento fino a questo giorno» NON si usa.** Il portale
spiega che registra «nessun arrivo e nessuna partenza» dall'ultimo giorno
compilato **fino** a quello scelto, confermando presenze e unità occupate
dell'ultimo giorno. Equivale a un file a zero movimenti solo se anche le unità
occupate restano uguali — e il file del gestionale può dire altro (un ospite
che cambia camera). In più copre un intervallo intero in un gesto: un errore
vale molti giorni. Il file del giorno dice esattamente cosa c'è: si carica
quello, uno per giorno, anche quando è vuoto.

⚠️ **Il login NON si automatizza**: qui dentro non c'è una riga che provi a
entrare. Si apre la pagina e si aspetta (``attendi_accesso``).
"""
from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from selenium.common.exceptions import (
    ElementClickInterceptedException,
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
from uploader_turismatica.pagina_movimenti import (
    SCHEDA_APERTO,
    SCHEDA_CHIUSO,
    PaginaMovimenti,
    RigaPortale,
    giorno_gia_caricato,
    leggi_pagina,
    mese_nel_dialogo,
    verso,
)
from uploader_turismatica.periodo import MESI, Periodo, fine_mese
from uploader_turismatica.sorgente import Sorgente, blocco_modalita_vera

log = logging.getLogger(__name__)

PREHOME_URL = "https://turismatica.regione.umbria.it/ntojsf/private/prehome.xhtml"
MOVIMENTI_URL = (
    "https://turismatica.regione.umbria.it/ntojsf/private/OSR/movimento/"
    "movimentoospiti.xhtml?idStruttura={}"
)

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
    periodo: Periodo | None,
    prova: bool,
    strutture_note: Collection[str],
    comunica: date | None,
    avanzamento: Avanzamento | None = None,
) -> EsitoStruttura:
    """Carica i giorni del periodo per **una** struttura — o, con ``prova``,
    arriva fino all'ultimo passo di ogni giorno e non lo fa (``carica_giorno``).

    ``comunica`` (il primo del mese, o ``None``): **ultimo passo**, la
    comunicazione telematica mensile di quel mese (``invia_comunicazione``).
    Si tenta solo se nessun giorno è andato storto. Non ha default: la chiede
    il gestore, con una conferma sua, e dimenticarla non deve volerla dire.

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

    if periodo is not None:
        _carica_giorni(driver, esito, id_turismatica=id_turismatica, etichetta=etichetta,
                       sorgente=sorgente, periodo=periodo, prova=prova,
                       strutture_note=strutture_note, dillo=dillo)
    if comunica is not None and esito.saltata is None:
        if esito.quanti(Esito.NON_RIUSCITO) or esito.quanti(Esito.FILE_MANCANTE):
            esito.comunicazione = ("comunicazione mensile non inviata: prima vanno "
                                   "sistemati i giorni non caricati.")
        else:
            dillo(f"comunicazione mensile di {MESI[comunica.month - 1]} {comunica.year}")
            esito.comunicazione_riuscita, esito.comunicazione = invia_comunicazione(
                driver, id_turismatica, comunica, prova=prova, strutture_note=strutture_note,
            )
    return esito


def _carica_giorni(
    driver: WebDriver, esito: EsitoStruttura, *, id_turismatica: str, etichetta: str,
    sorgente: Sorgente, periodo: Periodo, prova: bool, strutture_note: Collection[str],
    dillo: Callable[[str], None],
) -> None:
    dillo(f"apro la pagina dei movimenti di {etichetta}")
    problema = apri_movimenti(driver, id_turismatica, strutture_note=strutture_note)
    if problema is None:
        etichetta_mese = f"{MESI[periodo.dal.month - 1]} {periodo.dal.year}"
        raggiunto = vai_al_mese(driver, periodo.dal)
        if raggiunto is Raggiunto.CHIUSO:
            problema = messaggi.mese_chiuso(etichetta_mese)
        elif raggiunto is Raggiunto.NO:
            mostrato = pagina(driver).mese
            problema = messaggi.mese_non_raggiunto(
                f"{MESI[mostrato.month - 1]} {mostrato.year}" if mostrato else "un altro mese",
                etichetta_mese,
            )
    if problema is not None:
        esito.saltata = problema
        dillo(f"salto: {problema}")
        return

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
        # Per testo della data, mai per posizione: sbagliare riga vuol dire
        # dichiarare il movimento di un giorno su un altro.
        r = pagina(self.driver).riga(giorno)
        return r.grezza if r is not None else None

    def apri_dialog(self, giorno: date) -> bool:
        r = pagina(self.driver).riga(giorno)
        if r is None or not r.id_carica:
            return False
        # Il dialog si apre da JS: il click "normale" sul bottone non basta,
        # perché è PrimeFaces a dover eseguire il suo ciclo (``ps:true`` =
        # partial submit, ``u:`` = cosa aggiornare, ``onco:`` = che fare dopo
        # la risposta). È la chiamata che il bottone vero ha nel suo onclick.
        bid = r.id_carica
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


def pagina(driver: WebDriver) -> PaginaMovimenti:
    """La pagina com'è adesso, letta in Python (``pagina_movimenti``)."""
    try:
        return leggi_pagina(driver.page_source or "")
    except WebDriverException:
        return PaginaMovimenti(struttura=None)


def _aspetta_pagina(
    driver: WebDriver, condizione: Callable[[PaginaMovimenti], bool], secondi: float,
) -> PaginaMovimenti | None:
    """Rilegge la pagina finché ``condizione`` è vera (o scade il tempo)."""
    fine = time.monotonic() + secondi
    while True:
        p = pagina(driver)
        if condizione(p):
            return p
        if time.monotonic() >= fine:
            return None
        time.sleep(0.5)


def _sulla_struttura(p: PaginaMovimenti, id_turismatica: str) -> bool | None:
    """La pagina è quella della struttura voluta? ``None`` = non lo dice."""
    if p.struttura is None or not p.struttura.id_turismatica:
        return None
    return p.struttura.id_turismatica == id_turismatica


#: Sceglie la struttura nella tendina di ``prehome.xhtml`` e preme «Accedi».
#: È navigazione, non scrittura: è ciò che fa il gestore per entrare in una
#: struttura. Prima il widget PrimeFaces (aggiorna anche l'etichetta e il
#: valore che il modulo invia), poi, se non c'è, la ``<select>`` nascosta.
_JS_SCEGLI_STRUTTURA = r"""
const id = arguments[0];
const sel = [...document.querySelectorAll('select[id$="_input"]')]
  .find(s => [...s.options].some(o => o.value === id));
if (!sel) return 'assente';
const menu = sel.id.slice(0, -'_input'.length);
let fatto = false;
if (window.PrimeFaces && PrimeFaces.widgets) {
  for (const k in PrimeFaces.widgets) {
    const w = PrimeFaces.widgets[k];
    if (w && w.id === menu && typeof w.selectValue === 'function') { w.selectValue(id); fatto = true; }
  }
}
if (!fatto) { sel.value = id; sel.dispatchEvent(new Event('change', {bubbles: true})); }
const modulo = sel.closest('form') || document;
const accedi = [...modulo.querySelectorAll('button')].find(b => /accedi/i.test(b.textContent || ''));
if (!accedi) return 'senza-accedi';
accedi.click();
return 'ok';
"""


def _entra_da_prehome(driver: WebDriver, id_turismatica: str) -> bool:
    """Entra nella struttura dalla pagina di scelta, come farebbe il gestore.
    ``True`` se dopo si è sulla sua pagina dei movimenti."""
    driver.get(PREHOME_URL)
    try:
        esito = driver.execute_script(_JS_SCEGLI_STRUTTURA, id_turismatica)
    except WebDriverException as exc:
        log.warning("scelta della struttura in prehome non riuscita: %s", _in_breve(exc))
        return False
    log.info("struttura %s scelta da prehome: %s", id_turismatica, esito)
    if esito != "ok":
        return False
    with contextlib.suppress(TimeoutException, WebDriverException):
        WebDriverWait(driver, 20).until(lambda d: "prehome" not in (d.current_url or ""))
    if "movimentoospiti" not in _url(driver):
        driver.get(MOVIMENTI_URL.format(id_turismatica))
    return _aspetta_pagina(
        driver, lambda p: bool(p.righe) and _sulla_struttura(p, id_turismatica) is not False, 15,
    ) is not None


def apri_movimenti(
    driver: WebDriver, id_turismatica: str, *, strutture_note: Collection[str],
) -> str | None:
    """Apre la pagina dei movimenti della struttura. ``None`` se è pronta;
    altrimenti il messaggio per il gestore (cosa è successo e cosa fare).

    Prima l'indirizzo diretto (``?idStruttura=…``). Se la pagina che si apre
    è di **un'altra** struttura — il portale potrebbe ricordare quella scelta in
    ``prehome`` invece di seguire l'indirizzo — si passa da ``prehome`` come il
    gestore: tendina, «Accedi». Una pagina che non dice di chi è si accetta
    (``_sulla_struttura`` → ``None``): l'indirizzo l'abbiamo scritto noi."""
    driver.get(MOVIMENTI_URL.format(id_turismatica))
    p = _aspetta_pagina(driver, lambda p: bool(p.righe) or p.struttura is not None, 15)
    if p is not None and _sulla_struttura(p, id_turismatica) is False:
        log.warning(
            "l'indirizzo diretto ha aperto la struttura %s invece di %s: passo da prehome",
            p.struttura.id_turismatica if p.struttura else "?", id_turismatica,
        )
        _entra_da_prehome(driver, id_turismatica)
        p = pagina(driver)
    elif p is None or not p.righe:
        log.info("pagina dei movimenti di %s senza tabella: provo da prehome", id_turismatica)
        if _entra_da_prehome(driver, id_turismatica):
            p = pagina(driver)
    if p is not None and p.struttura is not None and not stato_utilizzabile(p.struttura.stato or None):
        return messaggi.struttura_non_attiva(id_turismatica, p.struttura.stato)
    if p is None or not p.righe:
        return messaggi.perche_movimenti_non_aperti(
            id_turismatica,
            url=_url(driver), testo_pagina=_testo_visibile(driver),
            strutture_note=strutture_note,
        )
    if _sulla_struttura(p, id_turismatica) is False:
        return messaggi.struttura_diversa(id_turismatica)
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


def _premi(driver: WebDriver, id_elemento: str) -> None:
    """Preme un bottone per id. Il bottone l'ha trovato ``pagina_movimenti``."""
    driver.execute_script("document.getElementById(arguments[0]).click();", id_elemento)


MAX_PASSI_MESE = 13


class Raggiunto(StrEnum):
    #: La tabella mostra il mese voluto.
    SI = "si"
    #: Il mese voluto è **prima** dei mesi aperti: sta nel «periodo chiuso».
    CHIUSO = "chiuso"
    NO = "no"


def vai_al_mese(driver: WebDriver, voluto: date) -> Raggiunto:
    """Porta la scheda «Movimento periodo aperto» sul mese voluto, con le
    frecce «Mese precedente/successivo».

    Le frecce si muovono **solo fra i mesi aperti**: sul portale vero sono
    disattivate quando di là non c'è niente di aperto. Se il mese voluto è
    prima e «Mese precedente» è spento, il mese è nel periodo chiuso
    (``Raggiunto.CHIUSO``): si legge da quella scheda, non dalle frecce."""
    for _ in range(MAX_PASSI_MESE):
        p = pagina(driver)
        direzione = verso(p.mese, voluto)
        if direzione is None:
            return Raggiunto.SI if p.mese is not None else Raggiunto.NO
        bottone = p.indietro if direzione == "indietro" else p.avanti
        if bottone is None:
            log.warning("frecce del mese non trovate (verso %s)", direzione)
            return Raggiunto.NO
        if not bottone.attivo:
            return Raggiunto.CHIUSO if direzione == "indietro" else Raggiunto.NO
        prima = p.mese
        _premi(driver, bottone.id)
        if _aspetta_pagina(driver, lambda q, m=prima: q.mese not in (None, m), 15) is None:
            log.warning("il mese non è cambiato dopo «%s»", direzione)
            return Raggiunto.NO
    return Raggiunto.SI if verso(pagina(driver).mese, voluto) is None else Raggiunto.NO


def apri_scheda(driver: WebDriver, nome: str) -> PaginaMovimenti | None:
    """Apre una scheda del TabView dei movimenti (``nome`` in minuscolo) e
    aspetta che il suo contenuto arrivi: il TabView è dinamico."""
    p = pagina(driver)
    indice = p.schede.get(nome)
    if indice is None:
        log.warning("scheda «%s» non trovata", nome)
        return None
    if p.scheda != nome:
        try:
            driver.execute_script(
                "const i = arguments[0];"
                "if (window.PF && PF('tabView')) { PF('tabView').select(i); return; }"
                "document.querySelectorAll('#movimentiTabView .ui-tabs-header')[i].click();",
                indice,
            )
        except WebDriverException as exc:
            log.warning("scheda «%s» non aperta: %s", nome, _in_breve(exc))
            return None
    return _aspetta_pagina(driver, lambda q: q.scheda == nome and bool(q.righe), 20)


@dataclass
class MeseLetto:
    """Un mese di una struttura com'è sul portale."""

    righe: list[RigaPortale] = field(default_factory=list)
    #: Il mese sta nel «periodo chiuso»: comunicato, non si carica più.
    chiuso: bool = False
    #: «Invia comunicazione telematica mensile» è premibile (solo periodo aperto).
    invio_possibile: bool | None = None
    problema: str | None = None


def leggi_mese(driver: WebDriver, voluto: date) -> MeseLetto:
    """Il mese voluto, dalla pagina dei movimenti già aperta. Sola lettura:
    frecce del mese e schede, nient'altro."""
    raggiunto = vai_al_mese(driver, voluto)
    etichetta = f"{MESI[voluto.month - 1]} {voluto.year}"
    if raggiunto is Raggiunto.SI:
        p = pagina(driver)
        return MeseLetto(
            [r for r in p.righe if (r.giorno.year, r.giorno.month) == (voluto.year, voluto.month)],
            invio_possibile=p.invio_mensile.attivo if p.invio_mensile else None,
        )
    if raggiunto is Raggiunto.CHIUSO:
        p = apri_scheda(driver, SCHEDA_CHIUSO)
        if p is not None and verso(p.mese, voluto) is not None:
            # Anche il periodo chiuso può avere le sue frecce: stessa regola.
            vai_al_mese(driver, voluto)
            p = pagina(driver)
        righe = [] if p is None else [
            r for r in p.righe if (r.giorno.year, r.giorno.month) == (voluto.year, voluto.month)
        ]
        # Si torna sul periodo aperto: è lì che lavora il resto del giro.
        apri_scheda(driver, SCHEDA_APERTO)
        if not righe:
            return MeseLetto(chiuso=True, problema=messaggi.mese_chiuso_non_letto(etichetta))
        return MeseLetto(righe, chiuso=True)
    mostrato = pagina(driver).mese
    return MeseLetto(problema=messaggi.mese_non_raggiunto(
        f"{MESI[mostrato.month - 1]} {mostrato.year}" if mostrato else "un altro mese", etichetta,
    ))


# ─── la comunicazione telematica mensile ─────────────────────────────────────

#: Il dialogo di conferma della comunicazione aperto adesso: il suo testo e
#: l'id del «Sì, procedi» **dentro di lui** (nella pagina ce ne sono altri tre,
#: di altri dialoghi — uno elimina i movimenti).
_JS_DIALOGO_INVIO = r"""
for (const d of document.querySelectorAll('.ui-confirm-dialog, .ui-dialog')) {
  const titolo = (d.querySelector('.ui-dialog-title') || {}).textContent || '';
  if (!/comunicazione telematica mensile/i.test(titolo)) continue;
  const visibile = d.offsetParent !== null || getComputedStyle(d).display !== 'none';
  if (!visibile) continue;
  const si = [...d.querySelectorAll('button')].find(b => /s[iì],?\s*procedi/i.test(b.textContent || ''));
  const no = [...d.querySelectorAll('button')].find(b => /no,?\s*annulla/i.test(b.textContent || ''));
  return {testo: d.textContent || '', si: si ? si.id : '', no: no ? no.id : ''};
}
return null;
"""


def invia_comunicazione(
    driver: WebDriver, id_turismatica: str, mese: date, *, prova: bool,
    strutture_note: Collection[str],
) -> tuple[bool, str]:
    """La comunicazione telematica mensile di ``mese``. ``(riuscita, frase)``.

    ⚠️ **Dopo, i dati del mese non si modificano più** (lo dice il portale nel
    dialogo). Per questo: solo a mese concluso, solo se **ogni giorno** del
    mese risulta inserito, solo se il dialogo nomina **quel** mese — e in prova
    ci si ferma prima di premere «Invia». La verifica è rileggere la pagina:
    il mese deve essere uscito dal periodo aperto."""
    etichetta = f"{MESI[mese.month - 1]} {mese.year}"
    problema = apri_movimenti(driver, id_turismatica, strutture_note=strutture_note)
    if problema is not None:
        return False, problema
    if vai_al_mese(driver, mese) is not Raggiunto.SI:
        return False, f"{etichetta} non è fra i mesi aperti: niente da comunicare."
    p = pagina(driver)
    mancano = mancanti_del_mese(p.righe, mese)
    if mancano:
        return False, (f"non invio la comunicazione di {etichetta}: sul portale mancano "
                       f"ancora {len(mancano)} giorni (il primo è il {mancano[0]}).")
    if p.invio_mensile is None or not p.invio_mensile.attivo:
        return False, (f"il portale non permette ancora la comunicazione di {etichetta} "
                       "(si fa a mese concluso, entro il 5 del mese dopo).")
    if prova:
        return True, f"comunicazione di {etichetta} pronta: in modalità vera la invierei."
    _premi(driver, p.invio_mensile.id)
    dialogo = None
    with contextlib.suppress(TimeoutException, WebDriverException):
        dialogo = WebDriverWait(driver, 15).until(
            lambda d: d.execute_script(_JS_DIALOGO_INVIO) or False
        )
    if not isinstance(dialogo, dict) or not dialogo.get("si"):
        return False, f"il portale non ha chiesto la conferma per {etichetta}: non ho inviato niente."
    nel_dialogo = mese_nel_dialogo(str(dialogo.get("testo", "")))
    if nel_dialogo != mese:
        if dialogo.get("no"):
            _premi(driver, str(dialogo["no"]))
        log.warning("dialogo della comunicazione per %s, atteso %s", nel_dialogo, mese)
        return False, (f"il portale proponeva di comunicare un altro mese invece di "
                       f"{etichetta}: ho annullato.")
    log.info("struttura=%s comunicazione mensile %s: premo «Sì, procedi»",
             id_turismatica, f"{mese:%m/%Y}")
    _premi(driver, str(dialogo["si"]))
    time.sleep(2)
    # La verifica: il mese non è più fra quelli aperti.
    apri_movimenti(driver, id_turismatica, strutture_note=strutture_note)
    if vai_al_mese(driver, mese) is Raggiunto.CHIUSO:
        log.info("struttura=%s comunicazione mensile %s: confermata", id_turismatica, f"{mese:%m/%Y}")
        return True, f"comunicazione di {etichetta} inviata."
    log.warning("struttura=%s comunicazione mensile %s: non confermata", id_turismatica, f"{mese:%m/%Y}")
    return False, (f"ho premuto «Sì, procedi» per {etichetta} ma il mese risulta ancora "
                   "aperto: controlla sul portale nella scheda «Comunicazioni telematiche».")


def mancanti_del_mese(righe: Sequence[RigaPortale], mese: date) -> list[int]:
    """I giorni del mese che sul portale non risultano inseriti (pura)."""
    fine = fine_mese(mese.year, mese.month).day
    dentro = {r.giorno.day for r in righe
              if (r.giorno.year, r.giorno.month) == (mese.year, mese.month) and r.caricato}
    return [g for g in range(1, fine + 1) if g not in dentro]


def _chiudi_dialog(driver: WebDriver) -> None:
    """Chiude il dialog rimasto aperto dopo un fallimento. Se resta aperto, il
    giorno dopo non trova la tabella e fallisce anche lui: un errore si porta
    dietro tutto il mese."""
    with contextlib.suppress(WebDriverException):
        driver.execute_script(
            "arguments[0].click();", driver.find_element(*_CHIUDI_DIALOG),
        )
