"""Le due pagine VERE del portale (ottobre 2026), ripulite: nomi e numeri
inventati ma coerenti fra loro — la struttura 12345 «AFFITTACAMERE CASA
LAVANDA» è la stessa nelle due.

* ``prehome.html`` — ``/ntojsf/private/prehome.xhtml``, «Seleziona la
  struttura su cui vuoi operare»;
* ``movimenti.html`` — ``…/movimentoospiti.xhtml?idStruttura=12345``, scheda
  «Movimento periodo aperto», ottobre 2026, nessun giorno ancora inserito.

È qui che si vede se la lettura regge sul portale vero: i test con le pagine
inventate (``test_riconoscimento.py``) provano le forme di ripiego.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from uploader_turismatica.abbinamento import StrutturaNota, cin_affidabile
from uploader_turismatica.pagina_movimenti import (
    SCHEDA_APERTO,
    SCHEDA_CHIUSO,
    leggi_pagina,
    mese_nel_dialogo,
    verso,
)
from uploader_turismatica.portale import mancanti_del_mese
from uploader_turismatica.riconoscimento import intestazione, ripulisci, strutture

CARTELLA = Path(__file__).parent / "fixtures" / "turismatica"


@pytest.fixture(scope="module")
def prehome() -> str:
    return (CARTELLA / "prehome.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def movimenti() -> str:
    return (CARTELLA / "movimenti.html").read_text(encoding="utf-8")


# ─── l'elenco delle strutture ────────────────────────────────────────────────


def test_l_elenco_viene_dalla_select_del_selectonemenu(prehome: str) -> None:
    trovate = {s.id_turismatica: s.nome for s in strutture(prehome)}
    assert trovate == {
        "12340": "AFFITTACAMERE IL GIRASOLE",
        "12341": "GUEST HOUSE IL MELOGRANO",          # nel portale ha uno spazio in coda
        "12345": "AFFITTACAMERE CASA LAVANDA",
        "12342": "LE STANZE DEL GLICINE",
        "12343": "LA CASA DEI TIGLI",
        "12344": "LA CORTE DEL MANDORLO",
        "12346": "LA COLLINA DEI PINI",
        "12347": "VILLA DEGLI ULIVI",
    }


def test_la_select_delle_provenienze_non_e_un_elenco_di_strutture(movimenti: str) -> None:
    """Nella pagina dei movimenti c'è un altro ``selectOneMenu``, quello delle
    provenienze: letto come elenco darebbe «AGRIGENTO», «ALESSANDRIA»…"""
    (s,) = strutture(movimenti)
    assert s.id_turismatica == "12345"


# ─── l'intestazione della pagina dei movimenti ──────────────────────────────


def test_l_intestazione_dice_chi_e_la_struttura(movimenti: str) -> None:
    s = intestazione(movimenti)
    assert s is not None
    assert (s.id_turismatica, s.nome, s.tipologia, s.comune, s.stato) == (
        "12345", "AFFITTACAMERE CASA LAVANDA", "Affittacamere", "PERUGIA", "VALIDATA")
    assert (s.cir, s.cin) == ("054039B403012345", "IT054039B403012345")


def test_la_prehome_non_ha_intestazione(prehome: str) -> None:
    assert intestazione(prehome) is None


def test_nel_campione_il_cin_contiene_il_numero_della_struttura(movimenti: str) -> None:
    s = intestazione(movimenti)
    assert s is not None
    assert cin_affidabile([StrutturaNota(s.id_turismatica, s.nome, s.cin)])


def test_la_regola_del_cin_vale_solo_se_regge_su_tutte() -> None:
    buone = [StrutturaNota("12345", "A", "IT054039B403012345"),
             StrutturaNota("7", "B", "IT054039B403000007")]
    assert cin_affidabile(buone)
    assert not cin_affidabile([*buone, StrutturaNota("23456", "C", "")])          # non letto
    assert not cin_affidabile([*buone, StrutturaNota("23456", "C", "IT054056C203099999")])
    assert not cin_affidabile([StrutturaNota("1234567", "D", "IT0540391234567")])  # 7 cifre
    assert not cin_affidabile([])


# ─── la tabella dei movimenti ────────────────────────────────────────────────


def test_le_righe_del_mese_aperto(movimenti: str) -> None:
    p = leggi_pagina(movimenti)
    assert p.scheda == SCHEDA_APERTO
    assert p.mese == date(2026, 10, 1) and p.titolo_mese == date(2026, 10, 1)
    assert [r.giorno.day for r in p.righe] == list(range(1, 21))
    primo = p.righe[0]
    assert primo.celle == ["", "01/10/2026", "3", "", "", "", ""]
    assert not primo.caricato
    assert primo.id_carica == "movimentiTabView:tblMovimenti:0:j_idt315"
    # il bottone «carica da FILE» c'è solo sul primo giorno non inserito
    assert all(not r.id_carica and not r.caricato for r in p.righe[1:])


def test_le_etichette_di_primefaces_nelle_celle_non_sono_valori(movimenti: str) -> None:
    """La stessa pagina dopo il JavaScript (``movimenti-dopo-js.html``, da
    Chrome): ogni cella porta l'etichetta della colonna. La lettura deve dare
    le stesse righe — e una cella vuota non deve leggere «Arrivi»."""
    dopo = (CARTELLA / "movimenti-dopo-js.html").read_text(encoding="utf-8")
    assert '<span class="ui-column-title">Arrivi</span></td>' in dopo
    assert leggi_pagina(dopo).righe == leggi_pagina(movimenti).righe
    assert not any(r.caricato for r in leggi_pagina(dopo).righe)


def test_un_valore_che_non_e_un_numero_non_fa_caricato() -> None:
    from uploader_turismatica.pagina_movimenti import giorno_gia_caricato
    celle = ["", "01/10/2026", "3", "Arrivi", "Partenze", "Presenze", "Unità occupate"]
    assert not giorno_gia_caricato(celle, [])
    assert giorno_gia_caricato(["", "01/10/2026", "3", "0", "1", "2", "1"], [])


def test_le_schede_e_le_frecce(movimenti: str) -> None:
    p = leggi_pagina(movimenti)
    assert p.schede[SCHEDA_CHIUSO] == 1 and p.schede[SCHEDA_APERTO] == 2
    # nel campione entrambe spente: ottobre è l'unico mese aperto
    assert p.indietro is not None and not p.indietro.attivo
    assert p.indietro.id == "movimentiTabView:j_idt279"          # quello col testo
    assert p.avanti is not None and not p.avanti.attivo


def test_il_bottone_della_comunicazione_mensile_e_spento_a_mese_in_corso(movimenti: str) -> None:
    p = leggi_pagina(movimenti)
    assert p.invio_mensile is not None
    assert p.invio_mensile.id == "movimentiTabView:j_idt334" and not p.invio_mensile.attivo


def test_frecce_accese_quando_c_e_un_mese_aperto_prima(movimenti: str) -> None:
    """Lo stesso bottone senza ``ui-state-disabled`` e ``disabled``: è come il
    portale lo mostra quando il mese prima è ancora aperto."""
    def accendi(m: re.Match[str]) -> str:
        return m.group(0).replace(" ui-state-disabled", "").replace(' disabled="disabled"', "")

    acceso = re.sub(r'<button id="movimentiTabView:j_idt279"[^>]*>', accendi, movimenti)
    p = leggi_pagina(acceso)
    assert p.indietro is not None and p.indietro.attivo
    assert p.avanti is not None and not p.avanti.attivo


def test_verso_del_mese() -> None:
    ottobre = date(2026, 10, 1)
    assert verso(ottobre, date(2026, 10, 15)) is None
    assert verso(ottobre, date(2026, 9, 1)) == "indietro"
    assert verso(ottobre, date(2026, 11, 1)) == "avanti"
    assert verso(None, date(2026, 9, 1)) is None


def test_il_mese_nel_dialogo_di_conferma(movimenti: str) -> None:
    """Il dialogo vero, nel campione: «…per il mese Ottobre 2026». Si
    comunica solo se dice il mese che vogliamo."""
    assert mese_nel_dialogo(movimenti) == date(2026, 10, 1)
    assert mese_nel_dialogo("nessun mese qui") is None


def test_giorni_mancanti_prima_della_comunicazione(movimenti: str) -> None:
    p = leggi_pagina(movimenti)
    assert mancanti_del_mese(p.righe, date(2026, 10, 1)) == list(range(1, 32))


# ─── la copia ripulita della pagina vera ────────────────────────────────────


@pytest.mark.parametrize("dato", [
    "Mario Rossi",                                     # l'operatore in testata
    "00000000-0000-0000-0000-000000000000",            # par_USER nei link dei report
    "VIEWSTATE",
])
def test_la_copia_della_pagina_vera_non_porta_dati_personali(movimenti: str, dato: str) -> None:
    assert dato not in ripulisci(movimenti)


def test_la_copia_della_pagina_vera_si_rilegge_uguale(movimenti: str, prehome: str) -> None:
    assert leggi_pagina(ripulisci(movimenti)).righe == leggi_pagina(movimenti).righe
    assert intestazione(ripulisci(movimenti)) == intestazione(movimenti)
    assert strutture(ripulisci(prehome)) == strutture(prehome)


def test_l_indirizzo_nel_registro_tiene_il_percorso_e_perde_i_segreti() -> None:
    from uploader_turismatica.riconoscimento import ripulisci_indirizzo
    url = ("https://turismatica.regione.umbria.it/ntojsf/private/OSR/movimento/"
           "movimentoospiti.xhtml?idStruttura=12345")
    assert ripulisci_indirizzo(url) == url
    sporco = "https://x.it/a/b.xhtml;jsessionid=ABC123?token=segreto&par=0f3c9a1b2d4e5f60718293a4b5c6d7e8f9"
    pulito = ripulisci_indirizzo(sporco)
    assert "ABC123" not in pulito and "segreto" not in pulito
    assert "0f3c9a1b2d4e5f60718293a4b5c6d7e8f9" not in pulito
    assert pulito.startswith("https://x.it/a/b.xhtml?")
