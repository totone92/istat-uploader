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
