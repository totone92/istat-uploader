"""Il flusso dell'app, una schermata per volta — senza finestra e senza browser.

L'interfaccia (HTML, ``ui/``) chiama questi metodi attraverso pywebview e
ridisegna da ``stato()``, che legge ogni mezzo secondo. Il lavoro lungo
(Chrome, SPID, letture, caricamenti) gira su un thread; quando serve una
risposta del gestore il thread **aspetta** la schermata successiva. Tutto ciò
che riguarda il portale passa da ``sessione.Portale``, quindi il flusso intero
si prova con un portale finto (``tests/test_flusso.py``).

Le schermate, nell'ordine in cui si incontrano:

``benvenuto`` → ``spid`` → ``lavoro`` → ``quante`` (o ``manuale`` se l'elenco
non si legge) → ``lavoro`` → ``riepilogo`` → *OK, si salva* → ``principale``
→ (zip) → ``abbina`` se serve → ``piano`` → ``spid`` → ``lavoro`` → ``esito``.

⚠️ **Si parte SEMPRE in modalità prova** (``PROVA_ALL_AVVIO``). La modalità
vera chiede due conferme nell'interfaccia, e qui non si accende senza
``confermato=True``: dimenticarlo non deve voler dire caricare.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from uploader_turismatica import __version__, configurazione, messaggi
from uploader_turismatica.abbinamento import (
    Abbinamento,
    Gruppo,
    StrutturaNota,
    abbina,
    raggruppa,
)
from uploader_turismatica.chrome import ChromeNonDisponibile
from uploader_turismatica.configurazione import Configurazione, StrutturaConf
from uploader_turismatica.esito import Esito, EsitoStruttura, riepilogo
from uploader_turismatica.periodo import MESI, fine_mese, mese_scorso
from uploader_turismatica.piano import (
    StatoGiorno,
    StatoMese,
    VocePiano,
    costruisci,
    scadenza_comunicazione,
)
from uploader_turismatica.riconoscimento import StrutturaTrovata
from uploader_turismatica.sessione import Portale
from uploader_turismatica.sorgente import (
    MARCATORE_PROVA,
    MESSAGGIO_ZIP_DI_PROVA,
    Archivio,
    SorgenteNonValida,
    apri_archivio,
    sorgente_da,
)

log = logging.getLogger(__name__)

#: La modalità con cui l'app si sveglia. ⚠️ ``True`` = prova, a ogni avvio.
PROVA_ALL_AVVIO = True
#: Ogni quanto si guarda se il gestore è entrato (secondi).
ATTESA_LOGIN_S = 1.0


class _Annullato(Exception):
    pass


@dataclass
class _Attesa:
    """Una domanda al gestore a cui il thread di lavoro aspetta risposta."""

    schermata: str
    evento: threading.Event = field(default_factory=threading.Event)
    risposta: Any = None


class Api:
    def __init__(
        self,
        *,
        portale: Callable[[], Portale],
        percorso_configurazione: Path,
        percorso_registro: Path | None,
        oggi: Callable[[], date],
        ora: Callable[[], datetime],
        scegli_file: Callable[[], str | None] | None = None,
        apri_cartella: Callable[[Path], None] | None = None,
        rapporto_computer: Callable[[], str] | None = None,
    ) -> None:
        self._portale = portale
        self._percorso_conf = percorso_configurazione
        self._registro = percorso_registro
        self._oggi = oggi
        self._ora = ora
        self._scegli_file = scegli_file
        self._apri_cartella = apri_cartella
        self._rapporto_computer = rapporto_computer

        self._lock = threading.RLock()
        self._rev = 0
        self._schermata = "benvenuto"
        self._dati: dict[str, Any] = {}
        self._prova = PROVA_ALL_AVVIO
        self._conf = configurazione.carica(percorso_configurazione)
        self._candidata: Configurazione | None = None
        self._attesa: _Attesa | None = None
        self._dentro = threading.Event()
        self._annullato = threading.Event()
        self._lavoro: threading.Thread | None = None
        self._archivio: Archivio | None = None
        self._abbinamenti: list[Abbinamento] = []
        self._piano: list[tuple[VocePiano, Gruppo]] = []
        self._ultimo_riepilogo = ""
        self._verifica: dict[str, Any] = {"in_corso": False, "testo": ""}
        if self._conf is not None:
            self._vai_principale()

    # ─── lettura dello stato (chiamata dall'interfaccia) ────────────────────

    def stato(self) -> dict[str, Any]:
        with self._lock:
            return {
                "rev": self._rev,
                "schermata": self._schermata,
                "dati": self._dati,
                "prova": self._prova,
                "versione": __version__,
                "occupato": self._lavoro is not None and self._lavoro.is_alive(),
                "verifica": dict(self._verifica),
            }

    def _mostra(self, schermata: str, dati: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._schermata = schermata
            self._dati = dati or {}
            self._rev += 1

    def _aggiorna_dati(self, **campi: Any) -> None:
        with self._lock:
            self._dati = {**self._dati, **campi}
            self._rev += 1

    # ─── collegare Turismatica / aggiornare le strutture ────────────────────

    def collega(self) -> dict[str, Any]:
        """«Collega Turismatica» al primo avvio, «Aggiorna le mie strutture»
        dopo: stesso giro, e nel secondo caso si conservano gli abbinamenti."""
        return self._avvia_lavoro(self._giro_collega)

    def sono_dentro(self) -> None:
        self._dentro.set()

    def annulla(self) -> None:
        self._annullato.set()
        with self._lock:
            if self._attesa is not None:
                self._attesa.risposta = None
                self._attesa.evento.set()

    def rispondi_quante(self, risposta: str) -> dict[str, Any]:
        if risposta not in ("una", "piu"):
            return {"errore": "Scegli una delle due risposte."}
        return self._rispondi("quante", risposta)

    def inserisci_a_mano(self, voci: list[dict[str, str]]) -> dict[str, Any]:
        pulite: list[tuple[str, str]] = []
        for v in voci:
            ident = str(v.get("id", "")).strip()
            nome = str(v.get("nome", "")).strip()
            if not ident and not nome:
                continue
            if not ident.isdigit():
                return {"errore": f"«{ident or nome}»: il numero della struttura "
                                  "è fatto di sole cifre (lo trovi dopo «idStruttura=»)."}
            pulite.append((ident, nome or f"Struttura {ident}"))
        if not pulite:
            return {"errore": "Scrivi almeno il numero di una struttura."}
        return self._rispondi("manuale", pulite)

    def _rispondi(self, schermata: str, risposta: Any) -> dict[str, Any]:
        with self._lock:
            a = self._attesa
            if a is None or a.schermata != schermata:
                return {"errore": "Questa domanda non è più aperta."}
            a.risposta = risposta
            a.evento.set()
        return {"ok": True}

    def _aspetta(self, schermata: str, dati: dict[str, Any]) -> Any:
        attesa = _Attesa(schermata)
        with self._lock:
            self._attesa = attesa
        self._mostra(schermata, dati)
        attesa.evento.wait()
        with self._lock:
            self._attesa = None
        if self._annullato.is_set() or attesa.risposta is None:
            raise _Annullato
        return attesa.risposta

    def _entra(self, portale: Portale, perche: str) -> None:
        """Apre Chrome e aspetta il gestore, **senza scadenza**."""
        self._dentro.clear()
        self._mostra("spid", {"perche": perche, "fase": "apro"})
        portale.apri()
        self._aggiorna_dati(fase="aspetto")
        while not self._annullato.is_set():
            if self._dentro.is_set() or portale.dentro():
                return
            time.sleep(ATTESA_LOGIN_S)
        raise _Annullato

    def _giro_collega(self) -> None:
        aggiornamento = self._conf is not None
        portale = self._portale()
        try:
            self._entra(portale, "aggiorna" if aggiornamento else "collega")
            self._mostra("lavoro", {"titolo": "Leggo le tue strutture sul portale",
                                    "dettaglio": "Solo lettura: non tocco niente."})
            lettura = portale.leggi_strutture()
            trovate = lettura.strutture
            manuale = False
            if not trovate:
                voci = self._aspetta("manuale", {
                    "messaggio": messaggi.strutture_non_lette(
                        str(lettura.copia_pagina) if lettura.copia_pagina else None),
                    "copia": str(lettura.copia_pagina) if lettura.copia_pagina else "",
                })
                trovate = [StrutturaTrovata(i, n) for i, n in voci]
                manuale = True
                quante = "una" if len(trovate) == 1 else "piu"
            else:
                quante = self._aspetta("quante", {
                    "trovate": [self._trovata(s) for s in trovate],
                    "proposta": "una" if len(trovate) == 1 else "piu",
                })
            note = {s.id_turismatica for s in trovate} if not manuale else set()
            mesi = self._mesi_da_leggere()
            strutture: list[StrutturaConf] = []
            for i, s in enumerate(trovate, 1):
                if self._annullato.is_set():
                    raise _Annullato
                self._mostra("lavoro", {
                    "titolo": "Guardo quali giorni ci sono già",
                    "dettaglio": f"{s.nome or s.id_turismatica} — "
                                 + " e ".join(f"{MESI[m.month - 1]}" for m in mesi),
                    "passo": i, "totale": len(trovate),
                })
                letti = portale.leggi_mesi(s.id_turismatica, mesi, strutture_note=note)
                # L'intestazione dei movimenti completa ciò che l'elenco non
                # dice (comune, tipologia, CIR, CIN). Il nome resta quello
                # dell'elenco, se c'era: è quello che il gestore ha scelto.
                t = letti.struttura if (
                    letti.struttura is not None
                    and letti.struttura.id_turismatica in ("", s.id_turismatica)
                ) else None
                strutture.append(StrutturaConf(
                    id_turismatica=s.id_turismatica,
                    nome=s.nome or (t.nome if t else "") or f"Struttura {s.id_turismatica}",
                    comune=s.comune or (t.comune if t else ""),
                    tipologia=s.tipologia or (t.tipologia if t else ""),
                    stato_portale=s.stato or (t.stato if t else ""),
                    cir=t.cir if t else "", cin=t.cin if t else "",
                    manuale=manuale, mesi=letti.mesi, avviso=letti.avviso,
                ))
            portale.chiudi()
            self._candidata = Configurazione(
                strutture=strutture, quante=quante,
                alias=dict(self._conf.alias) if self._conf else {},
                aggiornata_il=self._ora(),
            )
            self._mostra("riepilogo", {
                "quante": quante,
                "aggiornamento": aggiornamento,
                "manuale": manuale,
                "strutture": [self._vista_struttura(s) for s in strutture],
            })
        except _Annullato:
            self._torna_indietro()
        except ChromeNonDisponibile as exc:
            self._errore(str(exc))
        finally:
            portale.chiudi()

    def conferma_strutture(self, ids: list[str]) -> dict[str, Any]:
        """L'OK sul riepilogo: **solo da qui** la configurazione si salva."""
        with self._lock:
            c = self._candidata
            if c is None or self._schermata != "riepilogo":
                return {"errore": "Non c'è niente da confermare."}
            tenute = [s for s in c.strutture if s.id_turismatica in set(ids)]
            if not tenute:
                return {"errore": "Tieni almeno una struttura."}
            c.strutture = tenute
            try:
                configurazione.salva(c, self._percorso_conf)
            except OSError as exc:
                return {"errore": f"Non riesco a salvare la configurazione: {exc}"}
            self._conf, self._candidata = c, None
        log.info("strutture confermate: %s", ", ".join(s.id_turismatica for s in tenute))
        self._vai_principale()
        return {"ok": True}

    # ─── la schermata principale ─────────────────────────────────────────────

    def _vai_principale(self, avviso: str = "", tipo_avviso: str = "info") -> None:
        conf = self._conf
        if conf is None:
            self._mostra("benvenuto")
            return
        self._mostra("principale", {
            "strutture": [self._vista_struttura(s) for s in conf.strutture],
            "aggiornata_il": f"{conf.aggiornata_il:%d/%m/%Y %H:%M}" if conf.aggiornata_il else "",
            "avviso": avviso,
            "tipo_avviso": tipo_avviso,
        })

    def torna_alla_principale(self) -> None:
        if self._lavoro is not None and self._lavoro.is_alive():
            return
        self._pulisci_archivio()
        self._vai_principale()

    def imposta_prova(self, prova: bool, confermato: bool = False) -> dict[str, Any]:
        if self._lavoro is not None and self._lavoro.is_alive():
            return {"errore": "Sto lavorando: cambia modalità a giro finito."}
        if not prova and not confermato:
            return {"errore": "Per la modalità vera serve la conferma."}
        with self._lock:
            self._prova = bool(prova)
            self._rev += 1
        log.info("modalità: %s", "prova" if prova else "VERA")
        if self._schermata == "piano":
            self._mostra_piano()
        return {"ok": True}

    # ─── lo zip ─────────────────────────────────────────────────────────────

    def scegli_zip(self) -> dict[str, Any]:
        if self._scegli_file is None:
            return {"errore": "La scelta del file non è disponibile."}
        percorso = self._scegli_file()
        if not percorso:
            return {"ok": False}
        return self.usa_zip(percorso)

    def usa_zip(self, percorso: str) -> dict[str, Any]:
        if self._schermata != "principale" or self._conf is None:
            return {"errore": "Prima torna alla schermata principale."}
        self._pulisci_archivio()
        try:
            archivio = apri_archivio(Path(percorso))
        except SorgenteNonValida as exc:
            self._vai_principale(messaggi.zip_non_valido(str(exc)), "errore")
            return {"ok": False}
        marcatore = any(f.name.lower() == MARCATORE_PROVA.lower() for f in archivio.file)
        gruppi = raggruppa(archivio.file, marcatore_prova=marcatore)
        if not gruppi:
            archivio.pulisci()
            self._vai_principale(messaggi.nessun_file_istat(Path(percorso).name), "errore")
            return {"ok": False}
        if any(g.di_prova for g in gruppi) and not self._prova:
            archivio.pulisci()
            self._vai_principale(MESSAGGIO_ZIP_DI_PROVA, "errore")
            return {"ok": False}
        self._archivio = archivio
        strutture = [StrutturaNota(s.id_turismatica, s.nome, s.cin) for s in self._conf.strutture]
        self._abbinamenti = abbina(gruppi, strutture, self._conf.alias)
        log.info("zip %s: %d gruppi di file", Path(percorso).name, len(gruppi))
        if any(a.id_turismatica is None for a in self._abbinamenti):
            self._mostra_abbina()
        else:
            self._prepara_piano({a.gruppo.chiave: a.id_turismatica or "" for a in self._abbinamenti})
        return {"ok": True}

    def _mostra_abbina(self) -> None:
        assert self._conf is not None
        nomi = {s.id_turismatica: s.nome for s in self._conf.strutture}
        una_sola = len(self._conf.strutture) == 1
        self._mostra("abbina", {
            "gruppi": [
                {
                    "chiave": a.gruppo.chiave,
                    "nome_nel_file": a.gruppo.nome_nel_file or "(nessun nome nel file)",
                    "codice": a.gruppo.id_nel_nome or "",
                    "giorni": len(a.gruppo.per_giorno),
                    "mesi": self._mesi_del_gruppo(a.gruppo),
                    "di_prova": a.gruppo.di_prova,
                    "domanda": a.domanda,
                    "scelta": a.id_turismatica or (
                        a.proposte[0] if (a.proposte and (una_sola or a.gruppo.di_prova)) else ""
                    ),
                    "deciso": a.id_turismatica is not None,
                    "proposte": [{"id": i, "nome": nomi.get(i, i)} for i in a.proposte]
                    or [{"id": i, "nome": n} for i, n in nomi.items()],
                }
                for a in self._abbinamenti
            ],
        })

    def conferma_abbinamenti(self, scelte: dict[str, str], ricorda: bool) -> dict[str, Any]:
        if self._schermata != "abbina" or self._conf is None:
            return {"errore": "Non c'è niente da abbinare."}
        ids = self._conf.ids()
        finali: dict[str, str] = {}
        for a in self._abbinamenti:
            scelta = (scelte.get(a.gruppo.chiave) or "").strip()
            if scelta and scelta not in ids:
                return {"errore": "Scegli una delle tue strutture."}
            if scelta and a.gruppo.di_prova and not self._prova:
                return {"errore": MESSAGGIO_ZIP_DI_PROVA}
            finali[a.gruppo.chiave] = scelta
        usati = [i for i in finali.values() if i]
        if not usati:
            return {"errore": "Abbina almeno un gruppo di file a una struttura."}
        if len(usati) != len(set(usati)):
            return {"errore": "Due gruppi di file non possono andare sulla stessa "
                              "struttura: uno dei due è di un'altra."}
        if ricorda:
            for a in self._abbinamenti:
                if a.gruppo.di_prova or not finali.get(a.gruppo.chiave):
                    continue          # lo zip di prova non si ricorda mai
                for k in a.gruppo.chiavi_alias():
                    self._conf.alias[k] = finali[a.gruppo.chiave]
            try:
                configurazione.salva(self._conf, self._percorso_conf)
            except OSError:
                log.exception("abbinamenti non salvati")
        self._prepara_piano(finali)
        return {"ok": True}

    def _prepara_piano(self, scelte: dict[str, str]) -> None:
        assert self._conf is not None
        self._piano = []
        stati = {s.id_turismatica: s.mesi for s in self._conf.strutture}
        for a in self._abbinamenti:
            ident = scelte.get(a.gruppo.chiave) or ""
            s = self._conf.struttura(ident)
            if s is None:
                continue
            for voce in costruisci([(ident, s.nome, a.gruppo.giorni)], stati, self._oggi()):
                self._piano.append((voce, a.gruppo))
        self._mostra_piano()

    def _mostra_piano(self) -> None:
        voci = [v for v, _ in self._piano]
        prova_nel_piano = any(g.di_prova for _, g in self._piano)
        self._mostra("piano", {
            "voci": [
                {
                    "testo": v.testo,
                    "struttura": v.nome,
                    "mese": v.etichetta_mese,
                    "presenti": len(v.presenti) if v.presenti is not None else None,
                    "da_caricare": len(v.da_caricare),
                    "giorni_da_caricare": v.da_caricare,
                    "letto_il": f"{v.letto_il:%d/%m %H:%M}" if v.letto_il else "",
                    "futuri": v.futuri,
                    "chiuso": v.chiuso,
                    "chiave": self._chiave_voce(v),
                    "comunicabile": v.comunicabile,
                    "scadenza": f"{scadenza_comunicazione(v.anno, v.mese):%d/%m}",
                }
                for v in voci
            ],
            "niente_da_fare": not any(v.da_caricare or v.comunicabile for v in voci),
            "di_prova": prova_nel_piano,
            "conferma_vera": self._frase_conferma(voci),
        })

    @staticmethod
    def _chiave_voce(v: VocePiano) -> str:
        return f"{v.id_turismatica}|{v.anno:04d}-{v.mese:02d}"

    @staticmethod
    def _frase_conferma(voci: list[VocePiano]) -> str:
        parti = [f"{v.nome}: {v.etichetta_mese}, {len(v.da_caricare)} giorni"
                 for v in voci if v.da_caricare]
        if not parti:
            return "Non carico nessun giorno: sono già tutti sul portale."
        return "Carico DAVVERO sul portale — " + "; ".join(parti) + "."

    # ─── il giro ─────────────────────────────────────────────────────────────

    def avvia(self, confermato: bool = False, comunica: list[str] | None = None) -> dict[str, Any]:
        """Il giro. ``comunica``: le voci del piano (``id|AAAA-MM``) per cui il
        gestore ha chiesto anche la **comunicazione mensile** — un'operazione
        che chiude il mese sul portale. In prova si arriva fino al bottone e
        non lo si preme; in vera serve la stessa conferma del caricamento."""
        if self._schermata != "piano" or not self._piano:
            return {"errore": "Non c'è un piano da eseguire."}
        if not self._prova and not confermato:
            return {"errore": "Per caricare davvero serve la conferma."}
        if not self._prova and any(g.di_prova for _, g in self._piano):
            return {"errore": MESSAGGIO_ZIP_DI_PROVA}
        chieste = set(comunica or [])
        possibili = {self._chiave_voce(v) for v, _ in self._piano if v.comunicabile}
        if chieste - possibili:
            return {"errore": "La comunicazione mensile si può chiedere solo per un mese "
                              "concluso, entro il 5 del mese dopo, con tutti i giorni."}
        if not any(v.da_caricare for v, _ in self._piano) and not chieste:
            return {"errore": "Non c'è niente da caricare."}
        prova = self._prova
        return self._avvia_lavoro(lambda: self._giro_carica(prova, chieste))

    def _giro_carica(self, prova: bool, comunica: set[str] | None = None) -> None:
        assert self._conf is not None
        comunica = comunica or set()
        portale = self._portale()
        esiti: list[EsitoStruttura] = []
        voci = [(v, g) for v, g in self._piano
                if v.periodo is not None or self._chiave_voce(v) in comunica]
        totale_giorni = sum(len(v.da_caricare) for v, _ in voci)
        fatti = 0
        log.info("giro: inizio | versione=%s | modalità=%s | %s", __version__,
                 "prova" if prova else "VERA",
                 " ; ".join(f"{v.id_turismatica} {v.etichetta_mese}" for v, _ in voci))
        try:
            self._entra(portale, "carica")
            for v, gruppo in voci:
                if self._annullato.is_set():
                    break
                periodo = v.periodo
                sorgente = sorgente_da(list(gruppo.per_giorno.values()), di_prova=gruppo.di_prova)

                def avanzamento(msg: str, v: VocePiano = v) -> None:
                    nonlocal fatti
                    # «Fermati»: fra un giorno e l'altro, mai a metà di uno.
                    if self._annullato.is_set():
                        raise _Annullato
                    if len(msg) == 10 and msg[2] == "/" and msg[5] == "/":
                        fatti += 1
                    self._mostra("lavoro", {
                        "titolo": ("Provo" if prova else "Carico") + f" {v.nome}",
                        "dettaglio": f"{v.etichetta_mese} — {msg}",
                        "passo": min(fatti, totale_giorni), "totale": totale_giorni,
                        "prova": prova,
                    })

                esito = portale.carica(
                    id_turismatica=v.id_turismatica, etichetta=v.nome, sorgente=sorgente,
                    periodo=periodo, prova=prova, strutture_note=self._conf.ids(),
                    comunica=date(v.anno, v.mese, 1) if self._chiave_voce(v) in comunica else None,
                    avanzamento=avanzamento,
                )
                esiti.append(esito)
                if not prova:
                    self._segna_caricati(v.id_turismatica, esito)
                    if esito.comunicazione_riuscita:
                        self._segna_comunicato(v.id_turismatica, v.anno, v.mese)
            portale.chiudi()
            mesi = sorted({v.etichetta_mese for v, _ in voci})
            testo = riepilogo(esiti, " e ".join(mesi), prova=prova)
            self._ultimo_riepilogo = testo
            log.info("giro: fine | modalità=%s | %s", "prova" if prova else "VERA", " ; ".join(
                f"{e.id_turismatica}: " + (f"saltata ({e.saltata})" if e.saltata else ", ".join(
                    f"{k.value}={e.quanti(k)}" for k in Esito if e.quanti(k)))
                for e in esiti))
            if not prova:
                try:
                    configurazione.salva(self._conf, self._percorso_conf)
                except OSError:
                    log.exception("stato dei giorni non salvato")
            self._mostra("esito", {
                "prova": prova,
                "testo": testo,
                "strutture": [
                    {
                        "nome": e.etichetta,
                        "saltata": e.saltata or "",
                        "caricati": e.quanti(Esito.CARICATO),
                        "da_caricare": e.quanti(Esito.DA_CARICARE),
                        "gia": e.quanti(Esito.GIA_CARICATO),
                        "non_riusciti": [f"{g:%d/%m}" for g in e.elenco(Esito.NON_RIUSCITO)],
                        "mancanti": [f"{g:%d/%m}" for g in e.elenco(Esito.FILE_MANCANTE)],
                        "comunicazione": e.comunicazione,
                        "comunicazione_riuscita": e.comunicazione_riuscita,
                    }
                    for e in esiti
                ],
            })
        except _Annullato:
            self._torna_indietro()
        except ChromeNonDisponibile as exc:
            self._errore(str(exc))
        finally:
            portale.chiudi()
            self._pulisci_archivio()

    def _segna_caricati(self, ident: str, esito: EsitoStruttura) -> None:
        assert self._conf is not None
        s = self._conf.struttura(ident)
        if s is None:
            return
        for g in esito.elenco(Esito.CARICATO):
            chiave = f"{g.year:04d}-{g.month:02d}"
            mese = s.mesi.setdefault(chiave, StatoMese(g.year, g.month))
            mese.giorni[g.day] = StatoGiorno.CARICATO

    def _segna_comunicato(self, ident: str, anno: int, mese: int) -> None:
        assert self._conf is not None
        s = self._conf.struttura(ident)
        if s is not None:
            s.mesi.setdefault(f"{anno:04d}-{mese:02d}", StatoMese(anno, mese)).chiuso = True

    # ─── dettagli, registro, computer ───────────────────────────────────────

    def dettagli(self) -> dict[str, Any]:
        righe: list[str] = []
        if self._registro is not None:
            try:
                righe = self._registro.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
            except OSError:
                righe = []
        return {
            "registro": str(self._registro) if self._registro else "",
            "righe": righe,
            "riepilogo": self._ultimo_riepilogo,
            "configurazione": str(self._percorso_conf),
        }

    def apri_cartella_registro(self) -> None:
        if self._registro is not None and self._apri_cartella is not None:
            self._apri_cartella(self._registro.parent)

    def verifica_computer(self) -> dict[str, Any]:
        if self._rapporto_computer is None or self._verifica["in_corso"]:
            return {"ok": False}
        rapporto = self._rapporto_computer

        def lavora() -> None:
            testo = rapporto()
            with self._lock:
                self._verifica = {"in_corso": False, "testo": testo}

        # Senza toccare ``_rev``: la verifica si mostra nel pannello Dettagli e
        # non deve ridisegnare la schermata (perderebbe ciò che il gestore sta
        # scrivendo).
        with self._lock:
            self._verifica = {"in_corso": True, "testo": ""}
        threading.Thread(target=lavora, daemon=True).start()
        return {"ok": True}

    # ─── interni ─────────────────────────────────────────────────────────────

    def _avvia_lavoro(self, giro: Callable[[], None]) -> dict[str, Any]:
        with self._lock:
            if self._lavoro is not None and self._lavoro.is_alive():
                return {"errore": "Sto già lavorando."}
            self._annullato.clear()

            def corri() -> None:
                try:
                    giro()
                except Exception:          # noqa: BLE001 — l'app non deve restare appesa
                    log.exception("giro interrotto")
                    self._errore(
                        "Qualcosa è andato storto e mi sono fermato. Apri «Dettagli» "
                        "e manda il registro a chi ti assiste."
                    )

            self._lavoro = threading.Thread(target=corri, daemon=True)
            self._lavoro.start()
        return {"ok": True}

    def aspetta_fine(self, secondi: float = 10.0) -> None:
        """Per i test: aspetta che il thread di lavoro finisca."""
        if self._lavoro is not None:
            self._lavoro.join(secondi)

    def _torna_indietro(self) -> None:
        self._candidata = None
        self._vai_principale(
            "Fermato. I giorni già caricati restano sul portale; per vedere lo "
            "stato aggiornato usa «Aggiorna le mie strutture»." if self._conf else ""
        )

    def _errore(self, messaggio: str) -> None:
        self._mostra("errore", {"messaggio": messaggio, "ha_configurazione": self._conf is not None})

    def _pulisci_archivio(self) -> None:
        if self._archivio is not None:
            self._archivio.pulisci()
            self._archivio = None

    def _mesi_da_leggere(self) -> list[date]:
        oggi = self._oggi()
        return [mese_scorso(oggi).dal, oggi.replace(day=1)]

    @staticmethod
    def _trovata(s: StrutturaTrovata) -> dict[str, str]:
        return {"id": s.id_turismatica, "nome": s.nome, "comune": s.comune,
                "tipologia": s.tipologia}

    @staticmethod
    def _mesi_del_gruppo(g: Gruppo) -> str:
        mesi = sorted({(d.year, d.month) for d in g.per_giorno})
        return ", ".join(f"{MESI[m - 1]} {a}" for a, m in mesi)

    def _vista_struttura(self, s: StrutturaConf) -> dict[str, Any]:
        oggi = self._oggi()
        return {
            "id": s.id_turismatica,
            "nome": s.nome,
            "comune": s.comune,
            "tipologia": s.tipologia,
            "cin": s.cin,
            "manuale": s.manuale,
            "avviso": s.avviso,
            "mesi": [self._vista_mese(s.mesi.get(f"{m.year:04d}-{m.month:02d}"), m, oggi)
                     for m in self._mesi_da_leggere()],
        }

    @staticmethod
    def _vista_mese(stato: StatoMese | None, primo: date, oggi: date) -> dict[str, Any]:
        fine = fine_mese(primo.year, primo.month).day
        giorni = []
        for g in range(1, fine + 1):
            giorno = date(primo.year, primo.month, g)
            if giorno >= oggi:
                giorni.append({"g": g, "s": "futuro"})
            elif stato is None or g not in stato.giorni:
                giorni.append({"g": g, "s": "sconosciuto"})
            else:
                giorni.append({"g": g, "s": stato.giorni[g].value})
        letto = stato is not None and (bool(stato.giorni) or stato.chiuso)
        return {
            "etichetta": f"{MESI[primo.month - 1]} {primo.year}",
            "comunicazione": (stato or StatoMese(primo.year, primo.month)).comunicazione(oggi)
            if letto else "",
            "scadenza": f"{scadenza_comunicazione(primo.year, primo.month):%d/%m}",
            "letto": letto,
            "letto_il": f"{stato.letto_il:%d/%m %H:%M}" if stato and stato.letto_il else "",
            "caricati": len(stato.caricati()) if stato else 0,
            "mancanti": stato.mancanti(oggi) if stato else [],
            "giorni": giorni,
        }
