"""L'estensione vera, in un Chromium vero con profilo dedicato, guidata dal server MCP di
DevTools, contro il banco (``banco.py``): manifest e indirizzi sono quelli che si pubblicano."""
from __future__ import annotations

import base64
import contextlib
import io
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from banco import (  # noqa: E402
    ARGOMENTI_CHROMIUM,
    DIST,
    ESTENSIONE,
    FIXTURE,
    FUORI,
    HOSTLAB,
    HOSTLAB_B,
    RADICE,
    TURISMATICA,
    Banco,
    contenuto_giorno,
    zip_del_mese,
)
from mcp_devtools import DevTools, Errore  # noqa: E402

sys.path.insert(0, str(RADICE / "scripts"))
from zip_di_prova import GiornoTolm, RigaProvenienza, rendi  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("/snap/bin/chromium") is None, reason="serve Chromium")

SRC = ESTENSIONE / "src"
PORTALE = "https://turismatica.regione.umbria.it/ntojsf/private/prehome.xhtml"
SCHERMATA = '() => document.getElementById("app").dataset.schermata'
TESTO = '() => document.getElementById("app").innerText'


@pytest.fixture(scope="session")
def banco() -> Iterator[Banco]:
    b = Banco()
    b.accendi()
    yield b
    b.spegni()


@pytest.fixture(scope="session")
def devtools(banco: Banco) -> Iterator[DevTools]:
    d = DevTools(RADICE, RADICE / "dist" / "profilo-prove", ARGOMENTI_CHROMIUM)
    yield d
    d.chiudi()


@pytest.fixture(scope="session")
def id_estensione(devtools: DevTools) -> str:
    m = re.search(r"Id: (\w+)", devtools.chiama("install_extension", path=str(SRC)))
    assert m
    return m[1]


class Giro:
    """Una scheda dell'estensione e quella del portale, in un browser pulito fra un test e l'altro."""

    def __init__(self, d: DevTools, b: Banco, ext: str) -> None:
        self.d, self.b, self.ext = d, b, ext
        self.url = f"chrome-extension://{ext}/carica.html"

    def pulisci(self) -> None:
        for n, u in self.d.pagine().items():
            if u != "about:blank":
                with contextlib.suppress(Errore):
                    self.d.chiama("close_page", pageId=n)
        self.b.azzera()

    def apri(self) -> int:
        self.d.chiama("new_page", url=self.url)
        self.pagina = self.trova(self.url)
        self.d.valuta(self.pagina, "() => { localStorage.clear(); return true; }")
        return self.pagina

    def trova(self, pezzo: str, secondi: float = 15) -> int:
        fine = time.monotonic() + secondi
        while True:
            for n, u in self.d.pagine().items():
                if pezzo in u:
                    return n
            if time.monotonic() > fine:
                raise Errore(f"pagina non trovata: {pezzo} in {self.d.pagine()}")
            time.sleep(0.2)

    def schermata(self, nome: str, secondi: float = 60) -> str:
        self.d.aspetta(self.pagina, f'() => document.getElementById("app").dataset.schermata === "{nome}"',
                       secondi, f"schermata {nome}, sono su {self.d.valuta(self.pagina, TESTO)!r}")
        return str(self.d.valuta(self.pagina, TESTO))

    def premi(self, azione: str) -> None:
        self.d.valuta(self.pagina, f"""() => {{ document.querySelector('[data-azione="{azione}"]').click(); return true; }}""")

    def conferma_modale(self) -> None:
        self.d.valuta(self.pagina, """() => { document.querySelector('#modale button').click(); return true; }""")

    def trascina(self, byte: bytes, nome: str = "mese.zip") -> None:
        self.d.valuta(self.pagina, """(z, nome) => {
          const by = Uint8Array.from(atob(z), (c) => c.charCodeAt(0));
          const dt = new DataTransfer();
          dt.items.add(new File([by], nome, { type: "application/zip" }));
          document.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt }));
          return true; }""", base64.b64encode(byte).decode(), nome)

    def entra_con_spid_finto(self) -> None:
        """Il gestore entra: la sessione si accende e la sua scheda torna nell'area privata."""
        self.b.dentro = True
        self.d.chiama("navigate_page", pageId=self.trova("turismatica."), type="url", url=PORTALE)

    def fino_al_piano(self, byte: bytes | None = None) -> str:
        self.trascina(byte if byte is not None else zip_del_mese())
        self.schermata("spid")
        self.entra_con_spid_finto()
        return self.schermata("piano")

    def registro(self) -> str:
        return str(self.d.valuta(self.pagina, """async () => {
          const orig = URL.createObjectURL;
          let testo = null;
          URL.createObjectURL = (b) => { testo = b; return orig.call(URL, b); };
          document.querySelector('#apri-dettagli').click();
          document.querySelector('[data-azione="scarica-registro"]').click();
          URL.createObjectURL = orig;
          document.querySelector('#dettagli').close();
          return await testo.text(); }"""))


@pytest.fixture
def giro(devtools: DevTools, banco: Banco, id_estensione: str) -> Iterator[Giro]:
    g = Giro(devtools, banco, id_estensione)
    g.pulisci()
    yield g
    g.pulisci()


def _quasi_pieno(b: Banco, fino: int = 26) -> None:
    b.caricati["12345"] = {g: f"vecchio{g}.txt" for g in range(1, fino + 1)}


def test_manifest_permessi_minimi() -> None:
    m = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    assert m["manifest_version"] == 3
    assert m["permissions"] == ["scripting"]
    assert m["host_permissions"] == ["https://turismatica.regione.umbria.it/*", "https://*.umbriaround.it/*"]
    assert [c["matches"] for c in m["content_scripts"]] == [["https://*.umbriaround.it/*"]]
    assert "optional_host_permissions" not in m
    for lato, nome in m["icons"].items():
        firma = (SRC / nome).read_bytes()
        assert int.from_bytes(firma[16:20]) == int(lato)


def test_niente_verso_fortitudo_nel_codice() -> None:
    testo = "\n".join(p.read_text(encoding="utf-8") for p in SRC.rglob("*.js"))
    assert set(re.findall(r"https?://[\w.-]+", testo)) == {"https://turismatica.regione.umbria.it"}
    # Le sole chiamate di rete sono il ritiro del pacchetto; niente telemetria.
    assert re.findall(r"\b(fetch|XMLHttpRequest|sendBeacon|WebSocket|EventSource)\b", testo) == ["fetch"]
    assert "fetch(" in (SRC / "hostlab.js").read_text(encoding="utf-8")


def test_si_installa_e_si_apre_dall_icona(giro: Giro) -> None:
    assert "Istat Uploader per Turismatica" in giro.d.chiama("list_extensions")
    # Il comando di prova non sveglia il service worker: lo si aspetta acceso.
    fine = time.monotonic() + 10
    while "sfondo.js" not in giro.d.chiama("list_pages") and time.monotonic() < fine:
        time.sleep(0.2)
    time.sleep(1)
    giro.d.chiama("trigger_extension_action", id=giro.ext)
    giro.pagina = giro.trova(giro.url)
    assert "Trascina qui lo zip" in giro.schermata("benvenuto")


def test_si_ferma_alla_schermata_di_login(giro: Giro) -> None:
    giro.apri()
    giro.trascina(zip_del_mese())
    assert "Entra con SPID o CIE" in giro.schermata("spid")
    portale = giro.trova("turismatica.")
    giro.d.aspetta(portale, '() => document.body.innerText.includes("Accedi con SPID")', 15)
    time.sleep(2)
    assert "login.xhtml" in giro.d.pagine()[portale]
    assert giro.d.valuta(giro.pagina, SCHERMATA) == "spid"
    assert not [r for r in giro.b.richieste if r[0] == "POST" and "/private/" in r[2]]


def test_zip_storto_si_dice(giro: Giro) -> None:
    giro.apri()
    giro.trascina(b"non sono uno zip", "foto.zip")
    testo = giro.schermata("benvenuto")
    giro.d.aspetta(giro.pagina, '() => !!document.querySelector(".avviso.errore")', 5)
    assert "foto.zip" in str(giro.d.valuta(giro.pagina, TESTO)), testo


def test_prova_non_carica_niente_e_dice_cosa_caricherebbe(giro: Giro) -> None:
    _quasi_pieno(giro.b)
    giro.apri()
    piano = giro.fino_al_piano()
    assert "26 giorni già presenti, 5 da caricare (27, 28, 29, 30 e 31)" in piano
    assert "Modalità prova" in str(giro.d.valuta(giro.pagina, "() => document.body.innerText"))
    giro.premi("avvia")
    esito = giro.schermata("esito", 90)
    assert "NON HO CARICATO NIENTE" in esito
    assert "5 giorni da caricare, 26 già c'erano" in esito
    assert "27/10/2026  ←  schedine_istat_IT054039B403012345_20261027.txt" in esito
    assert "31/10/2026  ←  schedine_istat_IT054039B403012345_20261031.txt" in esito
    assert giro.b.caricamenti == []
    # e il portale non ha ricevuto un solo POST di caricamento, solo l'apertura del dialog
    assert sorted(giro.b.caricati["12345"]) == list(range(1, 27))


def test_vera_doppia_conferma_salta_i_presenti_e_carica_i_byte_giusti(giro: Giro) -> None:
    _quasi_pieno(giro.b)
    giro.apri()
    giro.fino_al_piano()
    assert giro.d.valuta(giro.pagina, """() => !!document.querySelector('[data-azione="avvia"]')""")
    # Prima conferma: la modalità.
    giro.premi("passa-vera")
    assert "Passo alla modalità vera" in str(giro.d.valuta(giro.pagina, "() => document.getElementById('modale').innerText"))
    giro.conferma_modale()
    giro.d.aspetta(giro.pagina, """() => !!document.querySelector('[data-azione="avvia-vera"]')""", 5)
    # Seconda: il giro. Annullare non carica niente.
    giro.premi("avvia-vera")
    giro.d.valuta(giro.pagina, """() => { [...document.querySelectorAll('#modale button')].at(-1).click(); return 1; }""")
    time.sleep(1)
    assert giro.b.caricamenti == [] and giro.d.valuta(giro.pagina, SCHERMATA) == "piano"
    giro.premi("avvia-vera")
    assert "Carico DAVVERO sul portale" in str(giro.d.valuta(giro.pagina, "() => document.getElementById('modale').innerText"))
    giro.conferma_modale()
    esito = giro.schermata("esito", 150)
    assert "5 giorni caricati" in esito and "Tutto a posto" in esito
    assert [c["giorno"] for c in giro.b.caricamenti] == [27, 28, 29, 30, 31]
    for c in giro.b.caricamenti:
        assert c["struttura"] == "12345"
        assert c["byte"] == contenuto_giorno("TENANT A", c["giorno"]), "i byte devono arrivare intatti"
        assert c["file"] == f"schedine_istat_IT054039B403012345_202610{c['giorno']}.txt"
    # Rilanciare è innocuo.
    giro.premi("ricomincia")
    giro.schermata("benvenuto")
    n = len(giro.b.caricamenti)
    piano = giro.fino_al_piano_gia_dentro()
    assert "31 giorni già presenti, niente da caricare" in piano
    assert "Avvia la prova" not in piano or "comunicazione mensile" in piano
    assert "Carica davvero" not in piano, "ricominciando si torna in prova"
    assert len(giro.b.caricamenti) == n


def _fino_al_piano_gia_dentro(self: Giro) -> str:
    self.trascina(zip_del_mese())
    return self.schermata("piano")


Giro.fino_al_piano_gia_dentro = _fino_al_piano_gia_dentro  # type: ignore[attr-defined]


def test_sessione_scaduta_a_meta_mette_in_pausa_e_riprende(giro: Giro) -> None:
    _quasi_pieno(giro.b)
    giro.b.scade_dopo = 2
    giro.apri()
    giro.fino_al_piano()
    giro.premi("passa-vera")
    giro.conferma_modale()
    giro.d.aspetta(giro.pagina, """() => !!document.querySelector('[data-azione="avvia-vera"]')""", 5)
    giro.premi("avvia-vera")
    giro.conferma_modale()
    assert "ti ha fatto uscire" in giro.schermata("spid", 90)
    assert len(giro.b.caricamenti) == 2
    giro.entra_con_spid_finto()
    esito = giro.schermata("esito", 150)
    assert "5 giorni caricati" in esito
    assert [c["giorno"] for c in giro.b.caricamenti] == [27, 28, 29, 30, 31], "nessun giorno due volte"


#: I nomi veri dei file nello zip di HostLab: scaricati da beb (id della struttura su beb)
#: e generati da HostLab per chi non ha beb (CIN, o «hostlab» se il CIN non c'è).
_FORMATI_HOSTLAB = {
    "beb": "schedine_istat_99001_202610{g:02d}.txt",
    "generato_cin": "schedine_istat_IT054039B403012345_202610{g:02d}.txt",
    "generato_senza_cin": "schedine_istat_hostlab_202610{g:02d}.txt",
}


def _file_tolm(g: int) -> bytes:
    """Un giorno nel tracciato vero, col renderer copiato da HostLab; numeri inventati."""
    return rendi("TENANT A", GiornoTolm(
        giorno=date(2026, 10, g), presenti_notte_precedente=2, arrivati=3, partiti=2,
        presenti_notte=3, camere_occupate=2,
        righe=(RigaProvenienza("PG", "PERUGIA", 1, 2), RigaProvenienza("RM", "ROMA", 2, 0)),
    ))


@pytest.mark.parametrize("formato", sorted(_FORMATI_HOSTLAB))
def test_i_file_di_hostlab_e_di_beb_si_caricano_intatti(giro: Giro, formato: str) -> None:
    _quasi_pieno(giro.b)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for g in range(1, 32):
            z.writestr(_FORMATI_HOSTLAB[formato].format(g=g), _file_tolm(g))
    giro.apri()
    assert "26 giorni già presenti, 5 da caricare" in giro.fino_al_piano(buf.getvalue())
    giro.premi("passa-vera")
    giro.conferma_modale()
    giro.d.aspetta(giro.pagina, """() => !!document.querySelector('[data-azione="avvia-vera"]')""", 5)
    giro.premi("avvia-vera")
    giro.conferma_modale()
    assert "5 giorni caricati" in giro.schermata("esito", 150)
    assert [c["giorno"] for c in giro.b.caricamenti] == [27, 28, 29, 30, 31]
    for c in giro.b.caricamenti:
        assert c["struttura"] == "12345"
        assert c["file"] == _FORMATI_HOSTLAB[formato].format(g=c["giorno"])
        assert c["byte"] == _file_tolm(c["giorno"])


def test_il_buco_nei_file_ferma_il_giro(giro: Giro) -> None:
    giro.b.caricati["12345"] = {g: "v.txt" for g in range(1, 26)}
    giro.apri()
    byte = zip_del_mese(dal=28, al=31)
    giro.fino_al_piano(byte)
    giro.premi("avvia")
    esito = giro.schermata("esito", 60)
    assert "Manca il file del 26/10/2026" in esito
    assert giro.b.caricamenti == []


def test_abbinamento_chiesto_se_non_e_certo_e_ricordato(giro: Giro) -> None:
    _quasi_pieno(giro.b)
    giro.apri()
    giro.trascina(zip_del_mese(nome="NOME STRANO", codice="ALTRO1", dal=27))
    giro.schermata("spid")
    giro.entra_con_spid_finto()
    assert "a quale delle tue strutture" in giro.schermata("abbina", 60)
    giro.d.valuta(giro.pagina, """() => { document.querySelector('.a-scelta').value = '12345';
      document.querySelector('[data-azione="conferma-abbina"]').click(); return 1; }""")
    assert "26 giorni già presenti" in giro.schermata("piano", 60)
    ricordati = giro.d.valuta(giro.pagina, '() => localStorage.getItem("istat-uploader")')
    assert "ALTRO1" in str(ricordati) and "NOME STRANO" in str(ricordati)
    assert "inventato" not in str(ricordati), "in locale non restano i file"
    giro.premi("ricomincia")
    giro.schermata("benvenuto")
    giro.trascina(zip_del_mese(nome="NOME STRANO", codice="ALTRO1", dal=27))
    assert "26 giorni già presenti" in giro.schermata("piano", 60)


def test_zip_di_prova_mai_in_vera(giro: Giro) -> None:
    giro.apri()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("PROVA.txt", "x")
        z.writestr("schedine_istat_PROVA_20261030.txt", "STRUTTURA DI PROVA".ljust(255) + "\r\n")
    giro.trascina(buf.getvalue())
    giro.schermata("spid")
    giro.entra_con_spid_finto()
    giro.schermata("abbina", 60)
    giro.d.valuta(giro.pagina, """() => { document.querySelector('.a-scelta').value = '12345';
      document.querySelector('[data-azione="conferma-abbina"]').click(); return 1; }""")
    assert "zip di prova" in giro.schermata("piano", 60)
    giro.premi("passa-vera")
    giro.conferma_modale()
    giro.d.aspetta(giro.pagina, """() => !!document.querySelector('[data-azione="avvia-vera"]')""", 5)
    giro.premi("avvia-vera")
    giro.conferma_modale()
    time.sleep(1)
    assert "zip di prova" in str(giro.d.valuta(giro.pagina, "() => document.getElementById('modale').innerText"))
    assert giro.b.caricamenti == []


def test_registro_senza_dati_personali(giro: Giro) -> None:
    _quasi_pieno(giro.b)
    giro.apri()
    giro.fino_al_piano()
    giro.premi("avvia")
    giro.schermata("esito", 90)
    registro = giro.registro()
    assert "giro: inizio" in registro and "esito=da_caricare" in registro
    assert "inventato" not in registro, "il contenuto dei file non ci va"
    assert "RSSMRA" not in registro
    # Solo i due domini del manifest, e nient'altro, ha visto richieste dal browser.
    assert {h for _m, h, _p in giro.b.richieste} <= {TURISMATICA, HOSTLAB, HOSTLAB_B, FUORI}
    rete = giro.d.chiama("list_network_requests", pageId=giro.pagina)
    domini = set(re.findall(r"https?://([\w.-]+)", rete))
    assert domini <= {TURISMATICA, HOSTLAB}, rete


def test_dal_tasto_di_hostlab(giro: Giro) -> None:
    _quasi_pieno(giro.b)
    giro.d.chiama("new_page", url=f"https://{HOSTLAB}/report")
    h = giro.trova(HOSTLAB)
    assert giro.d.valuta(h, "() => document.documentElement.dataset.istatUploader")
    giro.d.valuta(h, "() => { document.getElementById('tasto').click(); return 1; }")
    giro.d.aspetta(h, "() => document.getElementById('esito').textContent === 'estensione'", 15)
    giro.pagina = giro.trova(giro.url)
    giro.schermata("spid", 20)
    assert giro.d.valuta(giro.pagina, "() => location.hash") == "", "il gettone non resta nell'indirizzo"
    assert len(giro.b.ritiri) == 1
    r = giro.b.ritiri[0]
    assert r["cookie"] is None, "al ritiro non vanno cookie di HostLab"
    giro.entra_con_spid_finto()
    piano = giro.schermata("piano", 60)
    assert "Da HostLab: TENANT A · ottobre 2026" in piano
    assert "26 giorni già presenti" in piano
    # La modalità non cambia perché arriva da HostLab.
    assert giro.d.valuta(giro.pagina, """() => !!document.querySelector('[data-azione="avvia"]')""")


def test_ogni_tenant_ritira_dal_proprio_indirizzo(giro: Giro) -> None:
    giro.d.chiama("new_page", url=f"https://{HOSTLAB_B}/report")
    h = giro.trova(HOSTLAB_B)
    giro.d.valuta(h, "() => { document.getElementById('tasto').click(); return 1; }")
    giro.d.aspetta(h, "() => document.getElementById('esito').textContent === 'estensione'", 15)
    giro.pagina = giro.trova(giro.url)
    giro.schermata("spid", 20)
    assert [r["host"] for r in giro.b.ritiri] == [HOSTLAB_B]


def test_fuori_da_umbriaround_il_ponte_non_c_e(giro: Giro) -> None:
    giro.d.chiama("new_page", url=f"https://{FUORI}/report")
    h = giro.trova(FUORI)
    assert not giro.d.valuta(h, "() => document.documentElement.dataset.istatUploader")
    giro.d.valuta(h, """() => { window.postMessage({tipo:"istat-uploader:carica", gettone:"9.""" + "c" * 43 + """"}, location.origin); return 1; }""")
    time.sleep(1)
    assert giro.url not in giro.d.pagine().values() and giro.b.ritiri == []


def test_gettone_scaduto_lo_dice_hostlab(giro: Giro) -> None:
    giro.apri()
    h_url = f"https://{HOSTLAB}/report"
    giro.d.chiama("new_page", url=h_url)
    h = giro.trova(HOSTLAB)
    giro.d.valuta(h, """() => { window.postMessage({tipo:"istat-uploader:carica", gettone:"9.""" + "c" * 43 + """"}, location.origin); return 1; }""")
    giro.d.aspetta(giro.pagina, """() => document.getElementById("app").dataset.schermata === "errore" """, 15)
    assert "scaduto" in str(giro.d.valuta(giro.pagina, TESTO))


def test_un_gettone_storto_non_passa(giro: Giro) -> None:
    giro.apri()
    giro.d.chiama("new_page", url=f"https://{HOSTLAB}/report")
    h = giro.trova(HOSTLAB)
    n = len(giro.b.ritiri)
    risposta = giro.d.valuta(h, """() => new Promise((ok) => {
      window.addEventListener("message", (e) => { if (e.data?.tipo === "istat-uploader:risposta") ok(e.data); });
      window.postMessage({tipo:"istat-uploader:carica", gettone:"https://male.example"}, location.origin); })""")
    assert risposta["ok"] is False  # type: ignore[index]
    assert len(giro.b.ritiri) == n


def test_hostlab_senza_estensione_propone_l_exe(giro: Giro, id_estensione: str) -> None:
    giro.d.chiama("uninstall_extension", id=id_estensione)
    try:
        giro.d.chiama("new_page", url=f"https://{HOSTLAB}/report")
        h = giro.trova(HOSTLAB)
        assert not giro.d.valuta(h, "() => document.documentElement.dataset.istatUploader")
        giro.d.valuta(h, "() => { document.getElementById('tasto').click(); return 1; }")
        giro.d.aspetta(h, "() => document.getElementById('esito').textContent === 'proposta'", 10)
        assert giro.d.valuta(h, "() => !document.getElementById('proposta').hidden")
        # Il gettone non si chiede finché non serve.
        assert not giro.b.gettoni
    finally:
        m = re.search(r"Id: (\w+)", giro.d.chiama("install_extension", path=str(SRC)))
        assert m and m[1] == id_estensione


def test_comunicazione_mensile_in_prova_e_vera(giro: Giro) -> None:
    giro.b.caricati["12345"] = {g: "v.txt" for g in range(1, 32)}
    giro.apri()
    risposta = giro.d.valuta(giro.pagina, """async () => {
      const { SessionePortale } = await import("./portale.js");
      const { Registro } = await import("./logica/registro.js");
      const s = new SessionePortale(new Registro());
      await s.apri();
      globalThis.s = s;
      return true; }""")
    assert risposta
    giro.entra_con_spid_finto()
    time.sleep(1)
    prova = giro.d.valuta(giro.pagina, """() => s.inviaComunicazione("12345", "2026-10-01", {prova:true, struttureNote:new Set()})""")
    assert prova[0] is True and "in modalità vera la invierei" in prova[1]  # type: ignore[index]
    assert not giro.b.chiusi
    vera = giro.d.valuta(giro.pagina, """() => s.inviaComunicazione("12345", "2026-10-01", {prova:false, struttureNote:new Set()})""")
    assert vera == [True, "comunicazione di ottobre 2026 inviata."], vera
    assert giro.b.chiusi == {"12345"}


def test_comunicazione_mese_sbagliato_annulla(giro: Giro) -> None:
    giro.b.caricati["12345"] = {g: "v.txt" for g in range(1, 32)}
    giro.apri()
    giro.d.valuta(giro.pagina, """async () => {
      const { SessionePortale } = await import("./portale.js");
      const { Registro } = await import("./logica/registro.js");
      globalThis.s = new SessionePortale(new Registro());
      await s.apri(); return 1; }""")
    giro.entra_con_spid_finto()
    time.sleep(1)
    # La fixture nomina ottobre: chiedere settembre deve fermarsi prima di tutto.
    r = giro.d.valuta(giro.pagina, """() => s.inviaComunicazione("12345", "2026-09-01", {prova:false, struttureNote:new Set()})""")
    assert r[0] is False  # type: ignore[index]
    assert not giro.b.chiusi


def test_lettura_uguale_a_quella_dell_uploader(giro: Giro) -> None:
    """Le stesse copie, lette dal Python dell'uploader e dal JavaScript dell'estensione."""
    from uploader_turismatica.pagina_movimenti import leggi_pagina
    from uploader_turismatica.riconoscimento import strutture

    giro.apri()
    for nome in ("movimenti.html", "movimenti-dopo-js.html"):
        html = (FIXTURE / "turismatica" / nome).read_text(encoding="utf-8")
        js = giro.d.valuta(giro.pagina, """async (h) => {
          const l = await import("./logica/lettura.js");
          return l.leggiPagina(l.documento(h), h); }""", html)
        py = leggi_pagina(html)
        assert js["mese"] == py.mese.isoformat()
        assert js["scheda"] == py.scheda and js["schede"] == py.schede
        assert [r["giorno"] for r in js["righe"]] == [r.giorno.isoformat() for r in py.righe]
        assert [r["celle"] for r in js["righe"]] == [r.celle for r in py.righe]
        assert [r["caricato"] for r in js["righe"]] == [r.caricato for r in py.righe]
        assert [r["idCarica"] for r in js["righe"]] == [r.id_carica for r in py.righe]
        assert js["struttura"]["cin"] == py.struttura.cin and js["struttura"]["id"] == py.struttura.id_turismatica
        assert js["struttura"]["nome"] == py.struttura.nome and js["struttura"]["stato"] == py.struttura.stato
        assert js["invioMensile"] == {"id": py.invio_mensile.id, "attivo": py.invio_mensile.attivo}
        assert js["indietro"] == {"id": py.indietro.id, "attivo": py.indietro.attivo}
    html = (FIXTURE / "turismatica" / "prehome.html").read_text(encoding="utf-8")
    js = giro.d.valuta(giro.pagina, """async (h) => {
      const l = await import("./logica/lettura.js");
      return l.strutture(l.documento(h), h); }""", html)
    assert [(s["id"], s["nome"]) for s in js] == [(s.id_turismatica, s.nome) for s in strutture(html)]


def test_copia_ripulita(giro: Giro) -> None:
    giro.apri()
    html = ('<html><body><table><tr><th>Codice fiscale</th><th>Nome</th></tr>'
            '<tr><td>RSSMRA80A01H501U</td><td>x</td></tr></table>'
            '<input name="a" value="segreto"><p>Scrivi a mario@example.com o 3331234567</p>'
            '<a href="/x;jsessionid=abc?token=zzz">y</a></body></html>')
    r = str(giro.d.valuta(giro.pagina, """async (h) => {
      const l = await import("./logica/lettura.js"); return l.ripulisci(h); }""", html))
    for segreto in ("RSSMRA80A01H501U", "segreto", "mario@example.com", "3331234567", "jsessionid", "zzz"):
        assert segreto not in r, segreto


def test_configurazione_mcp_mai_un_profilo_personale() -> None:
    cfg = json.loads((RADICE / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["chrome-devtools"]
    args = cfg["args"]
    assert "--categoryExtensions" in args
    assert not any("autoConnect" in a or "browserUrl" in a for a in args), "mai agganciarsi a un Chromium già aperto"
    assert f"--userDataDir={RADICE}/dist/profilo-prove" in args
    assert "--executablePath=/snap/bin/chromium" in args
    assert {f"--chromeArg={a}" for a in ARGOMENTI_CHROMIUM} <= set(args), "solo il banco, niente rete vera"


def test_il_pacchetto_contiene_solo_l_estensione_e_si_installa(giro: Giro) -> None:
    subprocess.run([sys.executable, str(ESTENSIONE / "strumenti" / "pacchetto.py")], check=True, capture_output=True)
    versione = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))["version"]
    z = RADICE / "dist" / f"istat-uploader-estensione-{versione}.zip"
    with zipfile.ZipFile(z) as f:
        nomi = set(f.namelist())
        assert "manifest.json" in nomi and "carica.html" in nomi
        assert not [n for n in nomi if n.endswith((".py", ".md", ".mjs")) or "test" in n or ".claude" in n]
        assert nomi == {str(p.relative_to(SRC)) for p in SRC.rglob("*") if p.is_file()}
        estratto = DIST / "dal-pacchetto"
        shutil.rmtree(estratto, ignore_errors=True)
        f.extractall(estratto)
    m = re.search(r"Id: (\w+)", giro.d.chiama("install_extension", path=str(estratto)))
    assert m
    giro.d.chiama("new_page", url=f"chrome-extension://{m[1]}/carica.html")
    pagina = giro.trova(f"{m[1]}/carica.html")
    assert giro.d.valuta(pagina, SCHERMATA) == "benvenuto"
    giro.d.chiama("uninstall_extension", id=m[1])


def test_schermate_per_la_scheda_store(giro: Giro) -> None:
    """Le immagini per la dashboard, con dati inventati, a 1280×800."""
    destinazione = ESTENSIONE / "scheda-store"
    destinazione.mkdir(exist_ok=True)
    giro.b.caricati["12345"] = {g: f"v{g}.txt" for g in range(1, 27)}
    giro.apri()
    giro.d.chiama("take_screenshot", pageId=giro.pagina, filePath=str(destinazione / "1-benvenuto.png"))
    giro.fino_al_piano()
    giro.d.chiama("take_screenshot", pageId=giro.pagina, filePath=str(destinazione / "2-piano.png"))
    giro.premi("avvia")
    giro.schermata("esito", 90)
    giro.d.chiama("take_screenshot", pageId=giro.pagina, filePath=str(destinazione / "3-esito.png"))
    for f in destinazione.glob("*.png"):
        assert f.stat().st_size > 1000
    assert DIST.exists()
