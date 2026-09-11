from __future__ import annotations

from datetime import date

import pytest

from uploader_turismatica.periodo import Periodo, fine_mese, mese, mese_scorso


def test_il_default_e_il_mese_appena_chiuso() -> None:
    assert mese_scorso(date(2026, 9, 11)) == Periodo(date(2026, 8, 1), date(2026, 8, 31))


def test_il_primo_gennaio_il_mese_scorso_e_di_un_altro_anno() -> None:
    """⚠️ È il giorno in cui l'aritmetica sbaglia, ed è anche il giorno in cui
    si comunica dicembre."""
    assert mese_scorso(date(2027, 1, 1)) == Periodo(date(2026, 12, 1), date(2026, 12, 31))


def test_febbraio_bisestile() -> None:
    assert fine_mese(2028, 2) == date(2028, 2, 29)
    assert fine_mese(2026, 2) == date(2026, 2, 28)


def test_dicembre_non_sfora_nellanno_dopo() -> None:
    assert fine_mese(2026, 12) == date(2026, 12, 31)


def test_un_mese_pieno_si_dice_col_suo_nome() -> None:
    assert mese(2026, 9).etichetta == "settembre 2026"
    assert Periodo(date(2026, 9, 3), date(2026, 9, 8)).etichetta == (
        "dal 03/09/2026 al 08/09/2026"
    )


def test_le_date_al_contrario_si_rifiutano_subito() -> None:
    with pytest.raises(ValueError, match="prima di quella di inizio"):
        Periodo(dal=date(2026, 9, 10), al=date(2026, 9, 1))


def test_i_giorni_sono_inclusivi() -> None:
    assert len(Periodo(date(2026, 9, 1), date(2026, 9, 1)).giorni) == 1
    assert len(mese(2026, 9).giorni) == 30


# ─── i campi della finestra ─────────────────────────────────────────────────
#
# ⚠️ La finestra non l'ho potuta avviare (nessun display grafico in questo
# ambiente, vedi README): per questo la logica dei campi vive qui fuori e si
# prova qui, invece che dentro un widget dove non la proverebbe nessuno.

from uploader_turismatica.periodo import da_campi  # noqa: E402


def _campi(**kw):
    base = dict(nome_mese="settembre", anno="2026", dal="01/09/2026", al="30/09/2026")
    return {**base, **kw}


def test_il_mese_scelto_dalle_tendine() -> None:
    assert da_campi(True, **_campi()) == mese(2026, 9)


def test_lintervallo_digitato_a_mano() -> None:
    assert da_campi(False, **_campi(dal="03/09/2026", al="08/09/2026")) == Periodo(
        date(2026, 9, 3), date(2026, 9, 8)
    )


def test_una_data_scritta_male_lo_dice_come_scriverla() -> None:
    with pytest.raises(ValueError, match="scrivila come 01/09/2026"):
        da_campi(False, **_campi(dal="3 settembre"))
    with pytest.raises(ValueError, match="scrivila come 01/09/2026"):
        da_campi(False, **_campi(dal="2026-09-03"))


def test_il_31_di_settembre_non_passa() -> None:
    with pytest.raises(ValueError, match="non è una data"):
        da_campi(False, **_campi(al="31/09/2026"))


def test_le_date_al_contrario_arrivano_col_messaggio_giusto() -> None:
    with pytest.raises(ValueError, match="prima di quella di inizio"):
        da_campi(False, **_campi(dal="10/09/2026", al="01/09/2026"))


def test_gli_spazi_intorno_non_danno_fastidio() -> None:
    assert da_campi(False, **_campi(dal=" 03/09/2026 ", al="08/09/2026 ")) == Periodo(
        date(2026, 9, 3), date(2026, 9, 8)
    )
    assert da_campi(True, **_campi(nome_mese=" Settembre ")) == mese(2026, 9)
