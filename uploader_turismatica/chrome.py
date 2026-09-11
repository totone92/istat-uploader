"""Avvio di Chrome, su un PC che non sappiamo com'è messo.

⚠️ **Niente ``webdriver_manager`` e niente percorso di Chrome cablato**, che
erano le due cose dello script originale destinate a rompersi su un PC altrui:

* il percorso ``/Applications/Google Chrome.app/...`` è macOS, e su Windows non
  esiste;
* ``webdriver_manager`` scarica il ChromeDriver *lui*, ed è la parte che si
  rompe al primo aggiornamento di Chrome — il PC si aggiorna da solo, il driver
  no, e da lì in poi l'app non parte più con un messaggio che non dice niente.

Dal 2022 Selenium ha **Selenium Manager** dentro di sé: guarda quale Chrome è
installato, scarica il driver giusto e lo tiene in cache. Non è una libreria in
più da gestire — è il comportamento predefinito quando non gli si dice niente.
Per questo qui si passa il minimo indispensabile: **meno gli si dice, meno c'è
da tenere allineato**.

Cosa può ancora andare storto, e cosa ne dice l'app:

* **Chrome non è installato** — non c'è rimedio automatico: si dice di
  installarlo;
* **prima accensione senza rete** — Selenium Manager deve scaricare il driver
  la prima volta. Succede in ufficio dietro un proxy aziendale;
* **antivirus che blocca il driver appena scaricato** — raro, e si vede perché
  Chrome non si apre affatto.

Tutti e tre danno lo stesso sintomo (Chrome non si apre) e messaggi
incomprensibili: qui si traducono in una frase sola con la cosa da provare.
"""
from __future__ import annotations

import logging

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options

log = logging.getLogger(__name__)


class ChromeNonDisponibile(Exception):
    """Chrome non si è aperto. Il messaggio è già per l'utente."""


def apri_chrome() -> webdriver.Chrome:
    """Apre una finestra di Chrome pronta per il portale.

    ⚠️ **Mai headless**: l'utente deve *vedere* la pagina per fare SPID. Un
    Chrome invisibile qui non è un'ottimizzazione, è l'app che non funziona."""
    opzioni = Options()
    opzioni.add_argument("--window-size=1600,1000")
    # Il portale è JSF e apre dialog: una finestra piccola li taglia e i click
    # finiscono su elementi sovrapposti.
    opzioni.add_argument("--start-maximized")
    # Toglie la barra "Chrome è controllato da un software di test", che a un
    # albergatore sembra un errore.
    opzioni.add_experimental_option("excludeSwitches", ["enable-automation"])
    opzioni.add_experimental_option("useAutomationExtension", False)
    try:
        # Nessun ``Service(...)``, nessun ``binary_location``: ci pensa
        # Selenium Manager. Vedi la docstring del modulo.
        return webdriver.Chrome(options=opzioni)
    except WebDriverException as exc:
        log.exception("Chrome non si è aperto")
        raise ChromeNonDisponibile(_spiega(exc)) from exc


def _spiega(exc: WebDriverException) -> str:
    testo = str(exc).lower()
    if "cannot find chrome binary" in testo or "no chrome binary" in testo:
        return (
            "Non trovo Google Chrome su questo computer.\n\n"
            "Installa Chrome da google.com/chrome e riprova. "
            "(Edge e Firefox non vanno bene: il portale è stato provato con "
            "Chrome.)"
        )
    if "unable to obtain" in testo or "could not download" in testo:
        return (
            "Chrome c'è, ma non sono riuscito a scaricare il componente che "
            "serve a guidarlo.\n\n"
            "Di solito è la connessione: controlla di essere online e riprova. "
            "Se sei in ufficio dietro una rete aziendale, prova da casa o col "
            "telefono in hotspot — serve solo la prima volta."
        )
    return (
        "Non sono riuscito ad aprire Chrome.\n\n"
        "Controlla che Chrome sia installato e aggiornato, poi riprova. "
        "Se non si apre comunque, riavvia il computer.\n\n"
        f"(dettaglio tecnico: {str(exc).splitlines()[0][:200]})"
    )
