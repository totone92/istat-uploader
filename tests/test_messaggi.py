"""I messaggi dicono cosa è successo e cosa fare, in parole da gestore."""
from __future__ import annotations

import pytest

from uploader_turismatica import messaggi
from uploader_turismatica.messaggi import perche_movimenti_non_aperti

URL_MOVIMENTI = "https://turismatica.regione.umbria.it/ntojsf/private/OSR/movimento/movimentoospiti.xhtml?idStruttura=123"


def test_il_caso_della_prima_prova_dice_perche() -> None:
    """Il numero 123 scritto a mano non era fra le strutture dell'account: il
    vecchio «la tabella dei movimenti non si è aperta» non lo diceva."""
    m = perche_movimenti_non_aperti("123", url=URL_MOVIMENTI, testo_pagina="",
                                    strutture_note={"12345", "23456"})
    assert m.startswith("La struttura 123 non è fra quelle del tuo account Turismatica")


def test_il_portale_che_nega_l_accesso_vuol_dire_non_tua() -> None:
    m = perche_movimenti_non_aperti("123", url=URL_MOVIMENTI,
                                    testo_pagina="Utente non autorizzato alla struttura",
                                    strutture_note=set())
    assert "non è fra quelle del tuo account" in m


@pytest.mark.parametrize(("url", "testo"), [
    ("https://idp.esempio.it/login?x=1", ""),
    (URL_MOVIMENTI, "La sessione è scaduta. Accedi con SPID"),
])
def test_sessione_finita(url: str, testo: str) -> None:
    m = perche_movimenti_non_aperti("12345", url=url, testo_pagina=testo, strutture_note={"12345"})
    assert m == messaggi.uscito_dal_portale()


def test_quando_non_si_sa_lo_si_dice_con_la_cosa_da_fare() -> None:
    m = perche_movimenti_non_aperti("12345", url=URL_MOVIMENTI, testo_pagina="",
                                    strutture_note={"12345"})
    assert "Riprova fra qualche minuto" in m and "Dettagli" in m


@pytest.mark.parametrize("testo", [
    messaggi.struttura_non_tua("1"),
    messaggi.uscito_dal_portale(),
    messaggi.struttura_non_attiva("1", "CESSATA"),
    messaggi.movimenti_non_aperti("1"),
    messaggi.mese_non_raggiunto("ottobre 2026", "settembre 2026"),
    messaggi.strutture_non_lette("C:\\x\\pagina.html"),
])
def test_nessun_messaggio_parla_da_programmatore(testo: str) -> None:
    for parola in ("tabella", "selettore", "timeout", "exception", "driver", "none"):
        assert parola not in testo.lower()
