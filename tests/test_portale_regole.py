"""Le decisioni del portale che si possono provare senza il portale.

⚠️ Il resto di `portale.py` — i selettori, `PrimeFaces.ab`, il campo file
nascosto — **non è provabile qui**, e non lo si finge con un finto browser: un
mock riprodurrebbe ciò che ho capito del portale, non il portale. Quella parte
si prova solo dal vivo, ed è nella lista del README.
"""
from __future__ import annotations

from datetime import date

from uploader_turismatica.portale import (
    MANCANTI_DI_FILA,
    ContatoreMancanti,
    stato_utilizzabile,
    tabella_sul_mese_giusto,
)


def test_si_carica_solo_su_una_struttura_validata() -> None:
    assert stato_utilizzabile("VALIDATA")
    assert stato_utilizzabile("validata ")
    assert not stato_utilizzabile("CESSATA")
    assert not stato_utilizzabile("SOSPESA")


def test_stato_non_letto_NON_ferma_il_caricamento() -> None:
    """⭐ Chi non sa, prova: fermarsi perché non si è trovata un'etichetta in
    pagina vorrebbe dire non caricare mai su un portale che cambia una classe
    CSS. Qui il tentativo costa poco, il falso negativo costa un adempimento.

    È anche ciò che sostituisce l'elenco di strutture cessate cablato: lo stato
    lo dice il portale, non una lista scritta a mano che invecchia."""
    assert stato_utilizzabile(None)


def test_la_tabella_deve_aprirsi_sul_mese_che_stiamo_caricando() -> None:
    assert tabella_sul_mese_giusto(date(2026, 9, 1), date(2026, 9, 1))
    assert tabella_sul_mese_giusto(date(2026, 9, 30), date(2026, 9, 1))
    assert not tabella_sul_mese_giusto(date(2026, 8, 31), date(2026, 9, 1))
    assert not tabella_sul_mese_giusto(date(2025, 9, 1), date(2026, 9, 1))


def test_data_non_leggibile_non_blocca() -> None:
    """L'accoppiamento vero avviene per testo della data riga per riga: questo
    controllo è una rete, non il meccanismo."""
    assert tabella_sul_mese_giusto(None, date(2026, 9, 1))


def test_tre_mancanti_di_fila_fermano_la_struttura() -> None:
    """Tre buchi consecutivi non sono tre giorni senza movimento — quelli il
    file ce l'hanno lo stesso — ma la cartella sbagliata o un download
    interrotto."""
    c = ContatoreMancanti()
    assert not c.manca()
    assert not c.manca()
    assert c.manca()
    assert MANCANTI_DI_FILA == 3


def test_un_file_trovato_azzera_il_contatore() -> None:
    """Due buchi sparsi in un mese non fermano niente: è *di fila* che conta."""
    c = ContatoreMancanti()
    c.manca()
    c.manca()
    c.trovato()
    assert not c.manca()
    assert not c.manca()
    assert c.manca()


# ─── «già caricato»: dalla tabella, non dal pulsante ─────────────────────────
# Le righe qui sotto hanno la forma della tabella vera (APPUNTI-ISTAT del job
# del Mac mini, dump del 22/09/2026): «!», Data, notte precedente, arrivi,
# partenze, presenze, unità occupate. Numeri inventati.

_CARICA = "ui-button-icon-left ui-icon ui-c fa fa-upload"
_DOCUMENTO = "ui-button-icon-left ui-icon ui-c fa fa-file-text-o"
_DA_FARE = "fa fa-angle-double-down"


def test_il_pulsante_di_caricamento_non_dice_niente() -> None:
    """⭐ Il pulsante resta anche DOPO il caricamento (serve a sostituire il
    file): un giorno dentro col pulsante è dentro, non «da caricare»."""
    from uploader_turismatica.portale import giorno_gia_caricato

    dentro = ["", "01/09/2026", "0", "0", "0", "0", "0"]
    assert giorno_gia_caricato(dentro, [_CARICA, _DOCUMENTO])


def test_il_documento_o_la_scritta_bastano() -> None:
    from uploader_turismatica.portale import giorno_gia_caricato

    vuote = ["", "02/09/2026", "3", "", "", "", ""]
    assert giorno_gia_caricato(vuote, [_DOCUMENTO])
    assert giorno_gia_caricato(vuote, [_CARICA], ["File caricato: 02092026.txt"])


def test_i_valori_anche_tutti_zero_dicono_dentro() -> None:
    """Un giorno corretto a mano sul portale perde il documento, ma resta
    dentro: i valori del movimento ci sono, anche a zero."""
    from uploader_turismatica.portale import giorno_gia_caricato

    assert giorno_gia_caricato(["", "03/09/2026", "0", "0", "0", "0", "0"], [_CARICA])


def test_il_giorno_che_il_portale_non_ha_non_e_caricato() -> None:
    """⭐ Il rovescio del vecchio criterio: il giorno che il portale non apre
    ancora non ha il pulsante, e veniva contato «già caricato»."""
    from uploader_turismatica.portale import giorno_gia_caricato

    # solo «presenze notte precedente» (la calcola il portale) e la doppia freccia
    prossimo = ["", "04/09/2026", "2", "", "", "", ""]
    assert not giorno_gia_caricato(prossimo, [_DA_FARE])
    assert not giorno_gia_caricato(prossimo, [_CARICA])
    assert not giorno_gia_caricato(["", "05/09/2026", "", "", "", "", ""], [])
    # valori pieni ma con la doppia freccia: il portale lo chiede ancora
    assert not giorno_gia_caricato(["", "06/09/2026", "1", "1", "0", "2", "1"], [_DA_FARE])
