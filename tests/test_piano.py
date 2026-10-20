"""Il piano prima di caricare, e lo stato dei giorni letto sul portale."""
from __future__ import annotations

from datetime import date, datetime

from uploader_turismatica.piano import (
    StatoGiorno,
    StatoMese,
    costruisci,
    elenco_giorni,
    stato_dalle_righe,
)
from uploader_turismatica.portale import righe_lette

OGGI = date(2026, 10, 20)
LETTO = datetime(2026, 10, 19, 18, 2)


def _settembre(mancanti: set[int]) -> StatoMese:
    return StatoMese(2026, 9, {
        g: StatoGiorno.DA_FARE if g in mancanti else StatoGiorno.CARICATO for g in range(1, 31)
    }, LETTO)


def test_la_frase_del_piano() -> None:
    (v,) = costruisci(
        [("12345", "Casa Lavanda", [date(2026, 9, g) for g in range(1, 31)])],
        {"12345": {"2026-09": _settembre({12, 19})}}, OGGI,
    )
    assert v.testo == "Settembre 2026, Casa Lavanda: 28 giorni già presenti, 2 da caricare (12 e 19)."
    assert v.da_caricare == [12, 19]
    assert v.periodo is not None and (v.periodo.dal, v.periodo.al) == (date(2026, 9, 12), date(2026, 9, 19))


def test_giorni_che_mancano_sul_portale_e_nello_zip_si_dicono() -> None:
    (v,) = costruisci(
        [("12345", "Casa Lavanda", [date(2026, 9, g) for g in range(1, 20)])],
        {"12345": {"2026-09": _settembre({12, 25, 26})}}, OGGI,
    )
    assert v.da_caricare == [12]
    assert v.senza_file == [25, 26]
    assert "mancano anche 25 e 26, ma nello zip non c'è il file" in v.testo


def test_tutto_gia_presente_non_ha_un_periodo() -> None:
    (v,) = costruisci(
        [("12345", "Casa Lavanda", [date(2026, 9, 3)])],
        {"12345": {"2026-09": _settembre(set())}}, OGGI,
    )
    assert v.da_caricare == [] and v.periodo is None
    assert "niente da caricare" in v.testo


def test_stato_mai_letto_si_dice_e_si_controlla_durante_il_giro() -> None:
    (v,) = costruisci([("12345", "Casa Lavanda", [date(2026, 9, 1), date(2026, 9, 2)])], {}, OGGI)
    assert v.presenti is None and v.da_caricare == [1, 2]
    assert "non l'ho ancora letto" in v.testo


def test_oggi_e_il_futuro_non_si_caricano() -> None:
    giorni = [date(2026, 10, g) for g in (18, 19, 20, 21)]
    (v,) = costruisci([("12345", "Casa Lavanda", giorni)], {}, OGGI)
    assert v.da_caricare == [18, 19] and v.futuri == [20, 21]


def test_due_mesi_nello_stesso_zip_sono_due_voci() -> None:
    giorni = [date(2026, 9, 30), date(2026, 10, 1)]
    voci = costruisci([("12345", "Casa Lavanda", giorni)], {}, OGGI)
    assert [(v.mese, v.da_caricare) for v in voci] == [(9, [30]), (10, [1])]


def test_elenco_giorni() -> None:
    assert elenco_giorni([12, 19]) == "12 e 19"
    assert elenco_giorni([3]) == "3"
    assert elenco_giorni([3, 4, 9]) == "3, 4 e 9"
    assert elenco_giorni(list(range(1, 15))) == "dal 1 al 14 (14 giorni)"


def test_mancanti_non_contano_oggi() -> None:
    m = StatoMese(2026, 10, {g: StatoGiorno.DA_FARE for g in range(1, 21)})
    assert m.mancanti(OGGI) == list(range(1, 20))


def test_stato_dalle_righe_del_portale() -> None:
    """Le righe come le legge il JavaScript: già dentro, da fare (c'è il
    pulsante), non ancora aperto (né dentro né pulsante)."""
    grezze = [
        {"celle": ["", "01/09/2026", "0", "1", "0", "1", "1"], "classi": [], "titoli": ["File caricato: a.txt"], "pulsante": True},
        {"celle": ["", "02/09/2026", "", "", "", "", ""], "classi": ["fa fa-angle-double-down"], "titoli": [], "pulsante": True},
        {"celle": ["", "03/09/2026", "", "", "", "", ""], "classi": [], "titoli": [], "pulsante": False},
        {"celle": ["", "riga senza data"], "classi": [], "titoli": []},
    ]
    righe = righe_lette(grezze)
    assert righe == [(date(2026, 9, 1), True, True), (date(2026, 9, 2), False, True),
                     (date(2026, 9, 3), False, False)]
    s = stato_dalle_righe(righe, anno=2026, mese=9, letto_il=LETTO)
    assert s.giorni == {1: StatoGiorno.CARICATO, 2: StatoGiorno.DA_FARE, 3: StatoGiorno.NON_APERTO}


def test_lo_stato_si_salva_e_si_rilegge() -> None:
    s = _settembre({12})
    assert StatoMese.dal_json(s.chiave, s.da_json()) == s
