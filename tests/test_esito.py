"""Il riepilogo per l'albergatore: cosa manca da fare, non cosa ha fatto il programma."""
from __future__ import annotations

from datetime import date

from uploader_turismatica.esito import Esito, EsitoStruttura, riepilogo


def _e(etichetta: str = "Il Melograno") -> EsitoStruttura:
    return EsitoStruttura(etichetta=etichetta, id_turismatica="12345")


def test_tutto_bene_lo_dice_e_non_elenca_niente() -> None:
    e = _e()
    for g in range(1, 4):
        e.segna(date(2026, 9, g), Esito.CARICATO)
    testo = riepilogo([e], "settembre 2026", prova=False)
    assert "3 giorni caricati" in testo
    assert "Tutto a posto" in testo
    assert "DA FARE" not in testo


def test_gia_caricato_non_e_un_errore() -> None:
    """⭐ Rilanciare sullo stesso mese dev'essere innocuo: se «già c'era»
    comparisse come problema, l'utente non rilancerebbe mai — nemmeno quando
    serve."""
    e = _e()
    for g in range(1, 4):
        e.segna(date(2026, 9, g), Esito.GIA_CARICATO)
    testo = riepilogo([e], "settembre 2026", prova=False)
    assert "3 già c'erano" in testo
    assert "Tutto a posto" in testo
    assert e.tutto_a_posto


def test_non_riuscito_e_file_mancante_NON_si_fondono() -> None:
    """⚠️ Sono la stessa riga non toccata con due significati opposti, e due
    rimedi diversi: uno si risolve in HostLab, l'altro sul portale."""
    e = _e()
    e.segna(date(2026, 9, 1), Esito.FILE_MANCANTE)
    e.segna(date(2026, 9, 2), Esito.NON_RIUSCITO)
    testo = riepilogo([e], "settembre 2026", prova=False)
    assert "manca il file di: 01/09" in testo
    assert "NON caricati: 02/09" in testo
    assert "riscarica da HostLab" in testo
    assert "riprova per" in testo
    assert not e.tutto_a_posto


def test_una_struttura_saltata_finisce_nelle_cose_da_fare() -> None:
    e = _e("Agriturismo Le Ginestre")
    e.saltata = "sul portale risulta «CESSATA», la pagina dei movimenti non esiste"
    testo = riepilogo([e], "settembre 2026", prova=False)
    assert "non fatta" in testo
    assert "CESSATA" in testo
    assert "DA FARE" in testo


def test_una_struttura_rotta_non_nasconde_le_altre() -> None:
    buona, rotta = _e("Il Melograno"), _e("Le Querce")
    buona.segna(date(2026, 9, 1), Esito.CARICATO)
    rotta.saltata = "la tabella dei movimenti non si è aperta"
    testo = riepilogo([buona, rotta], "settembre 2026", prova=False)
    assert "Il Melograno — 1 giorni caricati" in testo
    assert "Le Querce — non fatta" in testo


def test_tante_date_non_diventano_un_muro() -> None:
    """Un elenco di trenta date non lo legge nessuno, e nasconde le due che
    contano."""
    e = _e()
    for g in range(1, 21):
        e.segna(date(2026, 9, g), Esito.FILE_MANCANTE)
    testo = riepilogo([e], "settembre 2026", prova=False)
    assert "20 giorni (dal 01/09 al 20/09)" in testo
    assert "05/09" not in testo


def test_il_riepilogo_non_contiene_gergo() -> None:
    """Niente nomi di file, codici, né righe di log: lo legge un albergatore."""
    e = _e()
    e.segna(date(2026, 9, 1), Esito.CARICATO)
    e.segna(date(2026, 9, 2), Esito.NON_RIUSCITO)
    e.non_riconosciuti = ["appunti.txt"]
    testo = riepilogo([e], "settembre 2026", prova=False).lower()
    for parola in ("traceback", "exception", "none", "null", ".txt\n", "selenium",
                   "primefaces", "xhtml", "idstruttura"):
        assert parola not in testo


def test_niente_da_caricare_lo_dice_e_basta() -> None:
    assert riepilogo([], "settembre 2026", prova=False) == "Non c'era niente da caricare."
