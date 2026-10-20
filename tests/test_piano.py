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


def test_stato_dalle_righe_della_pagina_vera() -> None:
    """La pagina dei movimenti vera (ottobre 2026, nessun giorno inserito): il
    1° ha il bottone di caricamento, gli altri aspettano il precedente."""
    from pathlib import Path

    from uploader_turismatica.pagina_movimenti import leggi_pagina

    p = leggi_pagina((Path(__file__).parent / "fixtures/turismatica/movimenti.html")
                     .read_text(encoding="utf-8"))
    righe = [(r.giorno, r.caricato, bool(r.id_carica)) for r in p.righe]
    s = stato_dalle_righe(righe, anno=2026, mese=10, letto_il=LETTO)
    assert s.giorni[1] is StatoGiorno.DA_FARE
    assert all(s.giorni[g] is StatoGiorno.NON_APERTO for g in range(2, 21))
    assert s.mancanti(OGGI) == list(range(1, 20))


def test_un_mese_chiuso_non_ha_niente_da_caricare() -> None:
    m = StatoMese(2026, 9, {g: StatoGiorno.CARICATO for g in range(1, 31)}, LETTO, chiuso=True)
    (v,) = costruisci([("12345", "Casa Lavanda", [date(2026, 9, 3)])], {"12345": {"2026-09": m}}, OGGI)
    assert v.chiuso and v.da_caricare == [] and v.periodo is None and not v.comunicabile
    assert "già chiuso sul portale" in v.testo
    assert m.comunicazione(OGGI) == "comunicato"


def test_quando_si_puo_chiedere_la_comunicazione_mensile() -> None:
    """Mese concluso, ancora aperto, entro il 5 del mese dopo, e ogni giorno o
    già sul portale o fra quelli da caricare."""
    tutti = [date(2026, 9, g) for g in range(1, 31)]
    (v,) = costruisci([("12345", "Casa Lavanda", tutti)], {"12345": {"2026-09": _settembre({12})}},
                      date(2026, 10, 3))
    assert v.comunicabile
    # oltre il 5 ottobre: no
    (v,) = costruisci([("12345", "Casa Lavanda", tutti)], {"12345": {"2026-09": _settembre({12})}},
                      date(2026, 10, 6))
    assert not v.comunicabile
    # manca un giorno sul portale e nello zip non c'è: no
    (v,) = costruisci([("12345", "Casa Lavanda", tutti[:-1])],
                      {"12345": {"2026-09": _settembre({30})}}, date(2026, 10, 3))
    assert not v.comunicabile
    # il mese in corso: no
    (v,) = costruisci([("12345", "Casa Lavanda", [date(2026, 10, 1)])], {}, date(2026, 10, 3))
    assert not v.comunicabile


def test_lo_stato_della_comunicazione() -> None:
    assert StatoMese(2026, 10).comunicazione(OGGI) == "in_corso"
    assert StatoMese(2026, 9).comunicazione(date(2026, 10, 5)) == "da_comunicare"
    assert StatoMese(2026, 9).comunicazione(date(2026, 10, 6)) == "scaduta"
    assert StatoMese(2026, 12).comunicazione(date(2027, 1, 2)) == "da_comunicare"


def test_lo_stato_si_salva_e_si_rilegge() -> None:
    s = _settembre({12})
    assert StatoMese.dal_json(s.chiave, s.da_json()) == s
    c = StatoMese(2026, 8, {}, LETTO, chiuso=True, invio_possibile=False)
    assert StatoMese.dal_json(c.chiave, c.da_json()) == c
