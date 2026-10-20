"""La configurazione salvata: cosa c'è dentro, e soprattutto cosa no."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from uploader_turismatica import configurazione
from uploader_turismatica.configurazione import Configurazione, StrutturaConf
from uploader_turismatica.piano import StatoGiorno, StatoMese


def _conf() -> Configurazione:
    return Configurazione(
        strutture=[StrutturaConf(
            "12345", "CASA LAVANDA", "PERUGIA", "Affittacamere", "VALIDATA",
            mesi={"2026-09": StatoMese(2026, 9, {1: StatoGiorno.CARICATO, 2: StatoGiorno.DA_FARE},
                                        datetime(2026, 10, 19, 18, 2))},
        )],
        quante="una", alias={"id:99001": "12345"}, aggiornata_il=datetime(2026, 10, 19, 18, 3),
    )


def test_si_salva_e_si_rilegge_uguale(tmp_path: Path) -> None:
    p = configurazione.salva(_conf(), tmp_path / "c.json")
    assert configurazione.carica(p) == _conf()


def test_dentro_ci_sono_solo_strutture_giorni_e_abbinamenti(tmp_path: Path) -> None:
    """Niente credenziali, e non per filtro: non ce ne sono."""
    p = configurazione.salva(_conf(), tmp_path / "c.json")
    dati = json.loads(p.read_text(encoding="utf-8"))
    assert set(dati) == {"versione", "quante", "aggiornata_il", "strutture", "alias"}
    assert set(dati["strutture"][0]) == {
        "id_turismatica", "nome", "comune", "tipologia", "stato_portale", "cir", "cin", "manuale",
        "mesi", "avviso",
    }
    testo = p.read_text(encoding="utf-8").lower()
    for parola in ("password", "spid", "token", "codice_fiscale", "cookie"):
        assert parola not in testo


def test_primo_avvio_file_rotto_o_versione_vecchia_vuol_dire_ricollegare(tmp_path: Path) -> None:
    assert configurazione.carica(tmp_path / "manca.json") is None
    (tmp_path / "rotto.json").write_text("{", encoding="utf-8")
    assert configurazione.carica(tmp_path / "rotto.json") is None
    # la versione 1 era un elenco di strutture scritte a mano: non si migra
    (tmp_path / "v1.json").write_text('[{"id_turismatica": "123", "etichetta": "UCI"}]')
    assert configurazione.carica(tmp_path / "v1.json") is None
