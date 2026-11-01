"""L'avvio da HostLab: dal link al pacchetto, con un server HTTP vero in locale."""
from __future__ import annotations

import io
import json
import threading
import time
import zipfile
from collections.abc import Iterator
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from tests.test_flusso import DUE, ORA, PortaleFinto, _aspetta, _collega
from uploader_turismatica import __main__ as principale
from uploader_turismatica import da_hostlab as dh
from uploader_turismatica.api import Api
from uploader_turismatica.da_hostlab import Pacchetto, PacchettoNonDisponibile

GETTONE = "7." + "a" * 43
LINK = f"hostlab-turismatica://carica/{GETTONE}"


@pytest.mark.parametrize("link", [LINK, LINK + "/", LINK.upper().replace("A" * 43, "a" * 43)])
def test_il_link_buono_da_il_gettone(link: str) -> None:
    assert dh.gettone_dal_link(link) == GETTONE


@pytest.mark.parametrize("link", [
    "hostlab-turismatica://carica/",
    "hostlab-turismatica://altro/" + GETTONE,
    "hostlab-turismatica://carica/" + GETTONE + "?server=https://male.example",
    "hostlab-turismatica://carica/7.corto",
    'hostlab-turismatica://carica/7.' + "a" * 43 + '" --controllo',
    "https://male.example/" + GETTONE,
])
def test_il_link_storto_non_da_niente(link: str) -> None:
    assert dh.gettone_dal_link(link) is None


def test_col_link_gli_altri_argomenti_non_contano(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path))
    aperta: list[bool] = []
    monkeypatch.setattr("uploader_turismatica.finestra.avvia", lambda: aperta.append(True) or 0)
    monkeypatch.setattr("sys.argv", ["x", "--controllo", LINK])
    assert principale.main() == 0
    assert aperta == [True]
    assert dh.ritira() == GETTONE


def test_il_gettone_si_ritira_una_volta_e_non_se_e_vecchio(tmp_path: Path) -> None:
    assert dh.ritira(tmp_path) is None
    dh.deposita(GETTONE, tmp_path)
    assert dh.ritira(tmp_path) == GETTONE
    assert dh.ritira(tmp_path) is None
    dh.deposita(GETTONE, tmp_path)
    assert dh.ritira(tmp_path, adesso=time.time() + dh.ETA_MASSIMA_ARRIVO_S + 5) is None
    assert not (tmp_path / dh.FILE_ARRIVO).exists()


@pytest.mark.parametrize(("scritto", "atteso"), [
    ("http://192.168.122.1:8011/", "http://192.168.122.1:8011"),
    ("https://male.example", dh.SERVER),
    ("http://8.8.8.8", dh.SERVER),
    ("file:///c:/x", dh.SERVER),
])
def test_il_server_di_prova_vale_solo_in_rete_privata(
    tmp_path: Path, scritto: str, atteso: str,
) -> None:
    (tmp_path / dh.FILE_SERVER_DI_PROVA).write_text(scritto, encoding="utf-8")
    assert dh.server(tmp_path) == atteso


def test_senza_file_il_server_e_hostlab(tmp_path: Path) -> None:
    assert dh.server(tmp_path) == "https://hostlab.umbriaround.it"


class _Finto(BaseHTTPRequestHandler):
    risposta: tuple[int, bytes, dict[str, str]] = (200, b"zip", {})
    visti: list[tuple[str, str, str | None]] = []

    def do_POST(self) -> None:  # noqa: N802
        _Finto.visti.append((self.command, self.path, self.headers.get("Authorization")))
        codice, corpo, intest = _Finto.risposta
        self.send_response(codice)
        for k, v in intest.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, *_: object) -> None:
        return


@pytest.fixture
def server_finto() -> Iterator[str]:
    _Finto.visti = []
    s = HTTPServer(("127.0.0.1", 0), _Finto)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{s.server_port}"
    s.shutdown()


def test_scarica_col_gettone_nell_intestazione(server_finto: str) -> None:
    _Finto.risposta = (200, b"contenuto", {"X-Mese": "2026-10", "X-Struttura": "Casa%20Lavanda"})
    p = dh.scarica(GETTONE, base=server_finto)
    assert _Finto.visti == [("POST", dh.PERCORSO_PACCHETTO, f"Bearer {GETTONE}")]
    assert p.percorso.read_bytes() == b"contenuto"
    assert (p.struttura, p.mese) == ("Casa Lavanda", "2026-10")


def test_il_rifiuto_arriva_con_le_parole_di_hostlab(server_finto: str) -> None:
    _Finto.risposta = (410, json.dumps({"errore": "È scaduto."}).encode(), {})
    with pytest.raises(PacchettoNonDisponibile, match="È scaduto"):
        dh.scarica(GETTONE, base=server_finto)
    _Finto.risposta = (500, b"boh", {})
    with pytest.raises(PacchettoNonDisponibile, match="Carica su Turismatica"):
        dh.scarica(GETTONE, base=server_finto)


def test_senza_rete_si_dice() -> None:
    with pytest.raises(PacchettoNonDisponibile, match="connessione"):
        dh.scarica(GETTONE, base="http://127.0.0.1:9")


def _vero(cartella: Path) -> Pacchetto:
    percorso = cartella / "cartella-pacchetto" / "pacchetto-hostlab.zip"
    percorso.parent.mkdir()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for g in (1, 2, 3):
            z.writestr(f"schedine_istat_IT054_202609{g:02d}.txt",
                       "CASA LAVANDA".ljust(255) + "\r\n")
    percorso.write_bytes(buf.getvalue())
    return Pacchetto(percorso, "Casa Lavanda", "2026-09")


def _con_arrivi(a: Api, arrivi: list[str], scarica: object) -> Api:
    a._ritira_gettone = lambda: arrivi.pop() if arrivi else None
    a._scarica_pacchetto = scarica  # type: ignore[assignment]
    return a


def test_app_gia_collegata_dal_gettone_al_piano(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set(range(1, 29)))
    a = _collega(tmp_path, portale)
    assert a.stato()["schermata"] == "principale"
    p = _vero(tmp_path)
    _con_arrivi(a, [GETTONE], lambda g: p if g == GETTONE else None)

    assert a.controlla_arrivo() is True
    fine = time.monotonic() + 5
    while a.stato()["schermata"] not in ("abbina", "piano") and time.monotonic() < fine:
        time.sleep(0.01)
    s = a.stato()
    assert s["schermata"] in ("abbina", "piano")
    assert s["prova"] is True           # la modalità non cambia perché arriva da HostLab
    assert not p.percorso.exists()      # lo zip scaricato non resta in giro
    assert "caricamenti" not in s and portale.caricamenti == []
    assert a.controlla_arrivo() is False


def test_app_non_collegata_il_pacchetto_aspetta_la_conferma(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set(range(1, 29)))
    a = Api(portale=lambda: portale, percorso_configurazione=tmp_path / "configurazione.json",
            percorso_registro=None, oggi=lambda: date(2026, 10, 20), ora=lambda: ORA)
    p = _vero(tmp_path)
    _con_arrivi(a, [GETTONE], lambda _g: p)
    assert a.controlla_arrivo() is True
    a.aspetta_fine()
    dati = _aspetta(a, "benvenuto")
    assert dati["da_hostlab"] == "Casa Lavanda · settembre 2026"
    assert p.percorso.exists()

    a.collega()
    _aspetta(a, "quante")
    a.rispondi_quante("piu")
    r = _aspetta(a, "riepilogo")
    assert a.controlla_arrivo() is False     # sta aspettando una risposta
    a.conferma_strutture([s["id"] for s in r["strutture"]])
    assert a.stato()["schermata"] in ("abbina", "piano")
    assert not p.percorso.exists()


def test_il_rifiuto_si_mostra_e_senza_gettone_non_succede_niente(tmp_path: Path) -> None:
    portale = PortaleFinto(DUE, caricati_settembre=set())
    a = _collega(tmp_path, portale)

    def rifiuta(_g: str) -> Pacchetto:
        raise PacchettoNonDisponibile("È scaduto.")

    _con_arrivi(a, [], rifiuta)
    assert a.controlla_arrivo() is False
    _con_arrivi(a, [GETTONE], rifiuta)
    assert a.controlla_arrivo() is True
    assert _aspetta(a, "errore")["messaggio"] == "È scaduto."

