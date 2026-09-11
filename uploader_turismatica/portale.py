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
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

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

from uploader_turismatica.esito import Esito, EsitoStruttura
from uploader_turismatica.periodo import Periodo
from uploader_turismatica.sorgente import Sorgente

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
    periodo: Periodo,
    avanzamento: Avanzamento | None = None,
) -> EsitoStruttura:
    """Carica i giorni del periodo per **una** struttura.

    Non solleva per i problemi di quella struttura: li mette nell'esito. Il
    chiamante passa alla successiva — una struttura rotta non deve togliere il
    giro alle altre."""
    def dillo(msg: str) -> None:
        log.info("[%s] %s", etichetta, msg)
        if avanzamento is not None:
            avanzamento(msg)

    esito = EsitoStruttura(etichetta=etichetta, id_turismatica=id_turismatica)
    esito.non_riconosciuti = list(sorgente.non_riconosciuti)

    dillo(f"apro la pagina dei movimenti di {etichetta}")
    driver.get(MOVIMENTI_URL.format(id_turismatica))
    attesa = WebDriverWait(driver, 30)

    stato = _stato_struttura(driver)
    if not stato_utilizzabile(stato):
        esito.saltata = (
            f"sul portale risulta «{stato}», la pagina dei movimenti non esiste"
        )
        dillo(f"salto: {esito.saltata}")
        return esito

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, _TABELLA))
        )
    except TimeoutException:
        esito.saltata = (
            "la tabella dei movimenti non si è aperta"
            + (f" (stato «{stato}»)" if stato else "")
        )
        dillo(f"salto: {esito.saltata}")
        return esito

    prima = _prima_data_in_tabella(driver)
    if not tabella_sul_mese_giusto(prima, periodo.dal):
        assert prima is not None
        esito.saltata = (
            f"il portale mostra {prima:%m/%Y}, non {periodo.dal:%m/%Y} — "
            "apri tu il mese giusto e rilancia"
        )
        dillo(f"salto: {esito.saltata}")
        return esito

    contatore = ContatoreMancanti()
    for giorno in periodo.giorni:
        file = sorgente.file_del(giorno)
        if file is None:
            esito.segna(giorno, Esito.FILE_MANCANTE)
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
            esito.segna(giorno, _carica_giorno(driver, attesa, giorno, file))
        except Exception as exc:            # noqa: BLE001 — un giorno non ferma il mese
            log.warning("[%s] %s: %s", etichetta, f"{giorno:%d/%m/%Y}", exc)
            esito.segna(giorno, Esito.NON_RIUSCITO)
        time.sleep(PAUSA_FRA_GIORNI_S)

    return esito


def _carica_giorno(
    driver: WebDriver, attesa: WebDriverWait, giorno: date, file: Path,
) -> Esito:
    """Carica il file di **un** giorno. Ritorna l'esito di quel giorno.

    ⚠️ Le righe si rileggono a ogni giro: dopo un upload PrimeFaces ricostruisce
    la tabella e i riferimenti presi prima sono ``stale``."""
    bottone = _bottone_upload_della_riga(driver, giorno)
    if bottone is None:
        # Nessun bottone di upload su quella riga: il giorno è già caricato (o
        # il portale non lo consente). Non è un errore, ed è la ragione per cui
        # rilanciare sullo stesso mese è innocuo.
        return Esito.GIA_CARICATO

    # Il dialog si apre da JS: il click "normale" sul bottone non basta, perché
    # è PrimeFaces a dover eseguire il suo ciclo (``ps:true`` = partial submit,
    # ``u:`` = cosa aggiornare, ``onco:`` = che fare dopo la risposta).
    bid = bottone.get_attribute("id")
    driver.execute_script(
        "PrimeFaces.ab({"
        f"s:'{bid}',p:'{bid}',u:'movimentiTabView:uploadFileDialog',"
        "ps:true,onco:function(){PF('uploadFileDialog').show();}});"
    )
    attesa.until(EC.visibility_of_element_located(_DIALOG))

    # Il campo file è nascosto (``display:none``): Selenium non scrive su un
    # elemento invisibile, quindi lo si rende visibile e poi gli si passa il
    # percorso. È il modo standard di caricare un file senza toccare la finestra
    # di dialogo del sistema operativo — che Selenium non può guidare.
    campo = attesa.until(EC.presence_of_element_located(_CAMPO_FILE))
    driver.execute_script("arguments[0].style.display='block';", campo)
    campo.send_keys(str(file.resolve()))

    for tentativo in range(TENTATIVI_CARICA):
        try:
            carica = attesa.until(EC.element_to_be_clickable(_BOTTONE_CARICA))
            driver.execute_script("arguments[0].click();", carica)
            # La chiusura del dialog è la conferma: il portale non dà altro.
            attesa.until(EC.invisibility_of_element_located(_DIALOG))
            return Esito.CARICATO
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

    _chiudi_dialog(driver)
    return Esito.NON_RIUSCITO


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
