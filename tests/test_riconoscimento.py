"""Le strutture lette dalla pagina del portale, e la copia ripulita.

⚠️ Le pagine qui sotto sono **inventate**: provano le forme di ripiego
(tabella con intestazioni, link JSF con parametri, ``<select>``, schede) per un
portale che domani cambi. Le pagine **vere** sono in
``tests/fixtures/turismatica/`` e si provano in ``test_pagine_vere.py``.
"""
from __future__ import annotations

import pytest

from uploader_turismatica.riconoscimento import (
    link_da_seguire,
    ripulisci,
    strutture,
)

TABELLA_PRIMEFACES = """
<html><body>
<div id="header"><span class="nome-utente">Benvenuto MARIO ROSSI</span>
  <span class="cf-utente">RSSMRA80A01G478Z</span></div>
<form id="formStrutture" action="/ntojsf/private/prehome.xhtml;jsessionid=AB12CD34EF56">
<input type="hidden" name="javax.faces.ViewState" value="-1234567890123456789:9876543210987654321">
<div id="formStrutture:tbl" class="ui-datatable ui-widget">
<table role="grid">
 <thead><tr><th>Codice</th><th>Denominazione</th><th>Comune</th><th>Tipologia</th>
   <th>Titolare</th><th>Stato</th><th>Azioni</th></tr></thead>
 <tbody id="formStrutture:tbl_data" class="ui-datatable-data">
  <tr data-ri="0" class="ui-widget-content"><td>12345</td><td>CASA LAVANDA</td><td>PERUGIA</td>
   <td>Affittacamere</td><td>Mario Rossi</td><td>VALIDATA</td>
   <td><a href="/ntojsf/private/OSR/movimento/movimentoospiti.xhtml?idStruttura=12345">Movimenti</a></td></tr>
  <tr data-ri="1" class="ui-widget-content"><td>23456</td><td>Agriturismo Le Ginestre</td><td>ASSISI</td>
   <td>Agriturismo</td><td>Anna Bianchi</td><td>VALIDATA</td>
   <td><a href="#" onclick="PrimeFaces.ab({s:'formStrutture:tbl:1:mov',params:[{name:'idStruttura',value:'23456'}]});return false;">Movimenti</a></td></tr>
 </tbody></table></div>
<p>Assistenza: helpdesk@regione.esempio.it · tel. +39 075 1234567 · aggiornato il 01.09.2026</p>
</form></body></html>
"""

SENZA_INTESTAZIONI = """
<table><tr><td><a href="movimentoospiti.xhtml?idStruttura=777">Villa Rosa</a></td><td>SPELLO</td></tr>
<tr><td>31 - B&amp;B Il Pozzo</td><td><a href="movimentoospiti.xhtml?idStruttura=31">Apri</a></td></tr></table>
"""

SELECT_JSF = """
<select id="form:selStruttura" name="form:selStruttura">
  <option value="0">-- scegli la struttura --</option>
  <option value="12345">12345 - CASA LAVANDA</option>
  <option value="34567">B&amp;B Il Pozzo</option>
</select>
"""

SCHEDE = """
<div class="strutture">
 <div class="card struttura"><h3>Villa Rosa</h3><span>Comune: Spello</span> ·
   <span>Tipologia: Casa vacanze</span>
   <a class="ui-button" href="/ntojsf/private/OSR/movimento/movimentoospiti.xhtml?idStruttura=777">Apri</a></div>
</div>
"""


def test_tabella_primefaces_con_intestazioni() -> None:
    trovate = strutture(TABELLA_PRIMEFACES)
    assert [(s.id_turismatica, s.nome, s.comune, s.tipologia, s.stato) for s in trovate] == [
        ("23456", "Agriturismo Le Ginestre", "ASSISI", "Agriturismo", "VALIDATA"),
        ("12345", "CASA LAVANDA", "PERUGIA", "Affittacamere", "VALIDATA"),
    ]


def test_il_titolare_non_diventa_il_nome() -> None:
    assert all("Rossi" not in s.nome and "Bianchi" not in s.nome
               for s in strutture(TABELLA_PRIMEFACES))


def test_senza_intestazioni_il_nome_viene_dal_link_o_dalla_cella() -> None:
    trovate = {s.id_turismatica: s.nome for s in strutture(SENZA_INTESTAZIONI)}
    assert trovate == {"777": "Villa Rosa", "31": "B&B Il Pozzo"}


def test_una_select_di_strutture() -> None:
    assert [(s.id_turismatica, s.nome) for s in strutture(SELECT_JSF)] == [
        ("34567", "B&B Il Pozzo"), ("12345", "CASA LAVANDA"),
    ]


def test_schede_senza_tabella() -> None:
    (s,) = strutture(SCHEDE)
    assert (s.id_turismatica, s.nome, s.comune, s.tipologia) == ("777", "Villa Rosa", "Spello", "Casa vacanze")


def test_una_pagina_senza_strutture_da_una_lista_vuota() -> None:
    assert strutture("<html><body><h1>Benvenuto</h1><a href='/esci'>Esci</a></body></html>") == []


def test_i_link_da_seguire_sono_solo_href_veri_che_parlano_di_strutture() -> None:
    pagina = """<a href="/ntojsf/private/OSR/struttura/elenco.xhtml">Le mie strutture</a>
      <a href="javascript:void(0)">Strutture</a> <a href="#strutture">Strutture</a>
      <a href="/logout">Esci dalle strutture</a> <a href="/nuova-struttura">Aggiungi struttura</a>
      <a href="/ntojsf/private/profilo.xhtml">Profilo</a>"""
    assert link_da_seguire(pagina, "https://turismatica.regione.umbria.it/ntojsf/private/prehome.xhtml") == [
        "https://turismatica.regione.umbria.it/ntojsf/private/OSR/struttura/elenco.xhtml",
    ]


# ─── la copia ripulita ───────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def ripulita() -> str:
    return ripulisci(TABELLA_PRIMEFACES)


@pytest.mark.parametrize("dato", [
    "RSSMRA80A01G478Z",                      # codice fiscale
    "MARIO ROSSI", "Mario Rossi", "Anna Bianchi",   # persone
    "helpdesk@regione.esempio.it",           # email
    "1234567",                               # telefono
    "jsessionid", "AB12CD34EF56",            # sessione
    "-1234567890123456789",                  # ViewState
])
def test_la_copia_non_contiene_dati_personali(ripulita: str, dato: str) -> None:
    assert dato not in ripulita


@pytest.mark.parametrize("forma", [
    "idStruttura=12345", "idStruttura',value:'23456'", "CASA LAVANDA", "Agriturismo Le Ginestre",
    'class="ui-datatable ui-widget"', 'id="formStrutture:tbl_data"', "<th>Denominazione</th>",
    "01.09.2026",
])
def test_la_copia_conserva_la_forma_della_pagina(ripulita: str, forma: str) -> None:
    """Classi, id, intestazioni, numeri e nomi delle strutture: è ciò che
    serve per sistemare la lettura."""
    assert forma.replace("'", "&#x27;") in ripulita or forma in ripulita


def test_la_copia_si_rilegge_e_trova_le_stesse_strutture(ripulita: str) -> None:
    assert {s.id_turismatica for s in strutture(ripulita)} == {"12345", "23456"}
