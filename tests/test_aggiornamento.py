"""L'avviso di versione nuova: solo un avviso, e senza rete non succede niente."""
from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from uploader_turismatica import aggiornamento
from uploader_turismatica.aggiornamento import NuovaVersione, cerca, piu_nuova
from uploader_turismatica.api import Api

PAGINA = "https://github.com/totone92/istat-uploader/releases/tag/v1.5.0"


@pytest.mark.parametrize(("etichetta", "attesa"), [
    ("v1.5.0", "1.5.0"), ("1.5.0", "1.5.0"), ("v1.4.10", "1.4.10"), ("v2.0.0", "2.0.0"),
    ("v1.4.0", None), ("v1.3.9", None), ("v1.5.0-rc1", None), ("ultima", None),
])
def test_si_segnala_solo_una_versione_piu_nuova(etichetta: str, attesa: str | None) -> None:
    trovata = piu_nuova({"tag_name": etichetta, "html_url": PAGINA}, "1.4.0")
    assert (trovata.versione if trovata else None) == attesa


@pytest.mark.parametrize("dati", [
    None, [], {}, {"tag_name": "v9.0.0"}, {"tag_name": 9, "html_url": PAGINA},
    {"tag_name": "v9.0.0", "html_url": "https://altrove.example/virus.exe"},
])
def test_una_risposta_strana_non_segnala_niente(dati: object) -> None:
    assert piu_nuova(dati, "1.4.0") is None


class _Server:
    def __init__(self, stato: int, corpo: bytes) -> None:
        class Gestore(BaseHTTPRequestHandler):
            def log_message(self, *_: object) -> None:
                pass

            def do_GET(self) -> None:
                self.send_response(stato)
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                self.wfile.write(corpo)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Gestore)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def servi() -> Iterator[type[_Server]]:
    yield _Server


def test_cerca_legge_la_risposta_di_github(servi: type[_Server]) -> None:
    corpo = json.dumps({"tag_name": "v99.0.0", "html_url": PAGINA}).encode()
    assert cerca(servi(200, corpo).url) == NuovaVersione("99.0.0", PAGINA)


@pytest.mark.parametrize(("stato", "corpo"), [(404, b"{}"), (500, b""), (200, b"non json")])
def test_con_un_errore_non_succede_niente(servi: type[_Server], stato: int, corpo: bytes) -> None:
    assert cerca(servi(stato, corpo).url) is None


def test_senza_rete_non_succede_niente() -> None:
    assert cerca("http://127.0.0.1:9/", attesa_s=0.5) is None


def _api(tmp_path: Path, **argomenti: object) -> Api:
    return Api(portale=lambda: None,  # type: ignore[arg-type,return-value]
               percorso_configurazione=tmp_path / "c.json", percorso_registro=None,
               oggi=lambda: date(2026, 11, 1), ora=lambda: datetime(2026, 11, 1),
               **argomenti)  # type: ignore[arg-type]


def _aspetta_versione(a: Api) -> str:
    fine = time.monotonic() + 3
    while not a.stato()["nuova_versione"] and time.monotonic() < fine:
        time.sleep(0.01)
    return str(a.stato()["nuova_versione"])


def test_la_versione_nuova_arriva_nello_stato_senza_ridisegnare(tmp_path: Path) -> None:
    aperti: list[str] = []
    a = _api(tmp_path, cerca_versione=lambda: NuovaVersione("1.5.0", PAGINA),
             apri_indirizzo=aperti.append)
    rev = a.stato()["rev"]
    assert _aspetta_versione(a) == "1.5.0"
    assert a.stato()["rev"] == rev              # non perde ciò che il gestore sta scrivendo
    a.apri_nuova_versione()
    assert aperti == [PAGINA]


def test_un_controllo_che_esplode_non_disturba(tmp_path: Path) -> None:
    def rotto() -> NuovaVersione | None:
        raise OSError("niente rete")

    a = _api(tmp_path, cerca_versione=rotto, apri_indirizzo=lambda _u: None)
    time.sleep(0.05)
    assert a.stato()["nuova_versione"] == ""
    a.apri_nuova_versione()                     # nessun link: non succede niente


def test_l_indirizzo_e_quello_del_repository_pubblico() -> None:
    assert aggiornamento.ULTIMA_RELEASE.endswith("/repos/totone92/istat-uploader/releases/latest")
