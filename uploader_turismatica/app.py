"""La finestra dell'app (tkinter, niente dipendenze grafiche esterne).

Tre zone, nell'ordine in cui si usano: **il periodo**, **le strutture**,
**avvia**. Sotto, quello che sta succedendo.

⚠️ **Il momento SPID è una schermata, non un messaggio.** È l'unico punto in
cui il programma si ferma e tocca alla persona: se lo si dicesse con una riga
di stato passerebbe inosservato, e l'utente resterebbe a guardare un'app che
«non fa niente». Quindi: un pannello grande, e **nessuna scadenza** — l'attesa
dura quanto ci mette lui, che con SPID vuol dire aprire l'app sul telefono,
inquadrare un QR, confermare. Un timeout di trenta secondi lì è la differenza
fra un'app che funziona e una che non funziona.

⚠️ Selenium **non gira sul thread di Tk**: bloccherebbe la finestra, che
smetterebbe di ridisegnarsi e Windows la segnalerebbe come «non risponde». Il
lavoro sta su un thread, e parla con la finestra attraverso una coda letta da
``after()`` — il modo standard, e l'unico che non fa toccare i widget da fuori.
"""
from __future__ import annotations

import contextlib
import logging
import queue
import threading
import tkinter
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import (
    BOTH,
    END,
    LEFT,
    RIGHT,
    StringVar,
    Tk,
    W,
    X,
    filedialog,
    messagebox,
    ttk,
)
from tkinter.scrolledtext import ScrolledText

from uploader_turismatica import __version__
from uploader_turismatica.chrome import ChromeNonDisponibile, apri_chrome
from uploader_turismatica.esito import EsitoStruttura, riepilogo
from uploader_turismatica.periodo import MESI, Periodo, da_campi, mese_scorso
from uploader_turismatica.portale import (
    apri_portale,
    carica_struttura,
    sembra_dentro,
)
from uploader_turismatica.sorgente import Sorgente, SorgenteNonValida, apri
from uploader_turismatica.strutture import Struttura, carica, percorso_file, salva

log = logging.getLogger(__name__)

_SPUNTA, _VUOTO = "☑", "☐"


# ─── messaggi dal thread di lavoro alla finestra ─────────────────────────────


@dataclass
class Stato:
    testo: str


@dataclass
class ChiediSpid:
    pass


@dataclass
class Finito:
    esiti: list[EsitoStruttura]
    etichetta_periodo: str


@dataclass
class Rotto:
    messaggio: str


class App:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title(f"Carica movimenti su Turismatica — v{__version__}")
        self.root.geometry("880x720")
        self.root.minsize(760, 620)

        self.strutture: list[Struttura] = carica()
        self.selezionate: set[str] = {s.id_turismatica for s in self.strutture}
        self.coda: queue.Queue[object] = queue.Queue()
        self.vai = threading.Event()
        self.annullato = threading.Event()
        self.lavoro: threading.Thread | None = None

        self._costruisci()
        self._ridisegna_strutture()
        self.root.after(100, self._svuota_coda)
        self.root.protocol("WM_DELETE_WINDOW", self._chiudi)

    # ── costruzione ──────────────────────────────────────────────────────────

    def _costruisci(self) -> None:
        pad = {"padx": 10, "pady": 6}

        # 1. periodo
        f1 = ttk.LabelFrame(self.root, text=" 1.  Che periodo carico ")
        f1.pack(fill=X, **pad)
        self.modo = StringVar(value="mese")
        riga = ttk.Frame(f1)
        riga.pack(fill=X, padx=10, pady=8)
        ttk.Radiobutton(
            riga, text="Il mese di", variable=self.modo, value="mese",
            command=self._aggiorna_modo,
        ).pack(side=LEFT)
        scorso = mese_scorso()
        self.mese_v = StringVar(value=MESI[scorso.dal.month - 1])
        self.anno_v = StringVar(value=str(scorso.dal.year))
        self.cb_mese = ttk.Combobox(
            riga, textvariable=self.mese_v, values=list(MESI), width=12,
            state="readonly",
        )
        self.cb_mese.pack(side=LEFT, padx=(6, 4))
        anni = [str(a) for a in range(scorso.dal.year - 3, scorso.dal.year + 2)]
        self.cb_anno = ttk.Combobox(
            riga, textvariable=self.anno_v, values=anni, width=7, state="readonly",
        )
        self.cb_anno.pack(side=LEFT)

        riga2 = ttk.Frame(f1)
        riga2.pack(fill=X, padx=10, pady=(0, 8))
        ttk.Radiobutton(
            riga2, text="Oppure dal", variable=self.modo, value="intervallo",
            command=self._aggiorna_modo,
        ).pack(side=LEFT)
        self.dal_v = StringVar(value=f"{scorso.dal:%d/%m/%Y}")
        self.al_v = StringVar(value=f"{scorso.al:%d/%m/%Y}")
        self.e_dal = ttk.Entry(riga2, textvariable=self.dal_v, width=12)
        self.e_dal.pack(side=LEFT, padx=6)
        ttk.Label(riga2, text="al").pack(side=LEFT)
        self.e_al = ttk.Entry(riga2, textvariable=self.al_v, width=12)
        self.e_al.pack(side=LEFT, padx=6)
        ttk.Label(riga2, text="(giorno/mese/anno)", foreground="#666").pack(side=LEFT)

        # 2. strutture
        f2 = ttk.LabelFrame(self.root, text=" 2.  Quali strutture, e dove sono i file ")
        f2.pack(fill=BOTH, expand=True, **pad)
        self.tabella = ttk.Treeview(
            f2, columns=("sel", "nome", "id", "file"), show="headings", height=7,
        )
        for col, testo, larghezza in (
            ("sel", "", 34), ("nome", "Struttura", 190),
            ("id", "n° Turismatica", 110), ("file", "File da caricare", 380),
        ):
            self.tabella.heading(col, text=testo)
            self.tabella.column(col, width=larghezza, anchor=W, stretch=(col == "file"))
        self.tabella.pack(fill=BOTH, expand=True, padx=10, pady=(8, 4))
        self.tabella.bind("<Button-1>", self._click_tabella)
        self.tabella.bind("<Double-1>", lambda _e: self._modifica())

        bar = ttk.Frame(f2)
        bar.pack(fill=X, padx=10, pady=(0, 8))
        ttk.Button(bar, text="Aggiungi struttura…", command=self._aggiungi).pack(side=LEFT)
        ttk.Button(bar, text="Modifica…", command=self._modifica).pack(side=LEFT, padx=6)
        ttk.Button(bar, text="Togli", command=self._togli).pack(side=LEFT)
        ttk.Button(
            bar, text="Scegli i file…", command=self._scegli_file,
        ).pack(side=LEFT, padx=(18, 0))

        # 3. avvio
        f3 = ttk.Frame(self.root)
        f3.pack(fill=X, **pad)
        self.bottone = ttk.Button(f3, text="  Avvia  ", command=self._avvia)
        self.bottone.pack(side=LEFT)
        ttk.Button(
            f3, text="Verifica il computer", command=self._verifica,
        ).pack(side=LEFT, padx=8)
        self.stato = StringVar(value="Pronto.")
        ttk.Label(f3, textvariable=self.stato).pack(side=LEFT, padx=12)

        self.log = ScrolledText(self.root, height=10, wrap="word", state="disabled")
        self.log.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        self._aggiorna_modo()

    def _aggiorna_modo(self) -> None:
        per_mese = self.modo.get() == "mese"
        for w in (self.cb_mese, self.cb_anno):
            w.configure(state="readonly" if per_mese else "disabled")
        for w in (self.e_dal, self.e_al):
            w.configure(state="normal" if not per_mese else "disabled")

    # ── strutture ────────────────────────────────────────────────────────────

    def _ridisegna_strutture(self) -> None:
        self.tabella.delete(*self.tabella.get_children())
        for s in self.strutture:
            self.tabella.insert(
                "", END, iid=s.id_turismatica,
                values=(
                    _SPUNTA if s.id_turismatica in self.selezionate else _VUOTO,
                    s.etichetta,
                    s.id_turismatica,
                    s.sorgente or "— nessun file scelto —",
                ),
            )

    def _click_tabella(self, evento: object) -> None:
        """Il clic sulla prima colonna accende/spegne la spunta."""
        if self.tabella.identify_column(evento.x) != "#1":   # type: ignore[attr-defined]
            return
        iid = self.tabella.identify_row(evento.y)            # type: ignore[attr-defined]
        if not iid:
            return
        self.selezionate.symmetric_difference_update({iid})
        self._ridisegna_strutture()

    def _scelta(self) -> Struttura | None:
        sel = self.tabella.selection()
        if not sel:
            messagebox.showinfo("Quale?", "Prima clicca sulla riga della struttura.")
            return None
        return next((s for s in self.strutture if s.id_turismatica == sel[0]), None)

    def _aggiungi(self) -> None:
        nuova = _Dialogo(self.root, Struttura(id_turismatica="", etichetta="")).risultato
        if nuova is None:
            return
        if any(s.id_turismatica == nuova.id_turismatica for s in self.strutture):
            messagebox.showerror(
                "Già c'è",
                f"Il numero {nuova.id_turismatica} è già in elenco.",
            )
            return
        self.strutture.append(nuova)
        self.selezionate.add(nuova.id_turismatica)
        self._salva_strutture()

    def _modifica(self) -> None:
        s = self._scelta()
        if s is None:
            return
        modificata = _Dialogo(self.root, s).risultato
        if modificata is None:
            return
        self.strutture[self.strutture.index(s)] = modificata
        self.selezionate.discard(s.id_turismatica)
        self.selezionate.add(modificata.id_turismatica)
        self._salva_strutture()

    def _togli(self) -> None:
        s = self._scelta()
        if s is None:
            return
        if not messagebox.askyesno("Togliere?", f"Tolgo «{s.etichetta}» dall'elenco?"):
            return
        self.strutture.remove(s)
        self.selezionate.discard(s.id_turismatica)
        self._salva_strutture()

    def _scegli_file(self) -> None:
        s = self._scelta()
        if s is None:
            return
        scelto = filedialog.askopenfilename(
            title=f"Lo .zip scaricato da HostLab per «{s.etichetta}»",
            filetypes=[("File scaricato da HostLab", "*.zip"), ("Tutti i file", "*.*")],
        )
        if not scelto:
            # Niente zip: forse i file sono già estratti in una cartella.
            if not messagebox.askyesno(
                "Cartella?",
                "Non hai scelto uno .zip.\n\n"
                "Hai già estratto i file in una cartella? "
                "Se sì te la faccio scegliere.",
            ):
                return
            scelto = filedialog.askdirectory(
                title=f"La cartella con i file .txt di «{s.etichetta}»"
            )
            if not scelto:
                return
        s.sorgente = scelto
        self._salva_strutture()

    def _salva_strutture(self) -> None:
        try:
            salva(self.strutture)
        except OSError as exc:
            messagebox.showwarning(
                "Non ho potuto salvare",
                "Le strutture valgono per questo giro ma non me le ricorderò "
                f"la prossima volta.\n\n{exc}",
            )
        self._ridisegna_strutture()

    # ── avvio ────────────────────────────────────────────────────────────────

    def _periodo(self) -> Periodo | None:
        """Il periodo scelto, o ``None`` dopo aver detto all'utente cosa non va.

        La regola sta in ``periodo.da_campi`` e il messaggio arriva già scritto
        da lì: tradurlo qui sarebbe un secondo posto in cui dire la stessa cosa,
        e i due finirebbero per dirla diversa."""
        try:
            return da_campi(
                self.modo.get() == "mese",
                nome_mese=self.mese_v.get(), anno=self.anno_v.get(),
                dal=self.dal_v.get(), al=self.al_v.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Controlla il periodo", str(exc))
            return None

    def _avvia(self) -> None:
        if self.lavoro is not None and self.lavoro.is_alive():
            return
        periodo = self._periodo()
        if periodo is None:
            return
        scelte = [s for s in self.strutture if s.id_turismatica in self.selezionate]
        if not scelte:
            messagebox.showinfo(
                "Nessuna struttura",
                "Metti la spunta ☑ accanto ad almeno una struttura."
                if self.strutture else
                "Prima aggiungi una struttura con «Aggiungi struttura…».",
            )
            return
        senza_file = [s.etichetta for s in scelte if not s.sorgente]
        if senza_file:
            messagebox.showerror(
                "Mancano i file",
                "Non ho i file da caricare per: " + ", ".join(senza_file) +
                ".\n\nSeleziona la riga e usa «Scegli i file…».",
            )
            return

        self._pulisci_log()
        self._scrivi(f"Periodo: {periodo.etichetta}")
        self.bottone.configure(state="disabled")
        self.vai.clear()
        self.annullato.clear()
        self.lavoro = threading.Thread(
            target=self._lavora, args=(periodo, scelte), daemon=True,
        )
        self.lavoro.start()

    def _lavora(self, periodo: Periodo, scelte: list[Struttura]) -> None:
        """Gira sul thread di lavoro: **non tocca un solo widget**."""
        driver = None
        sorgenti: list[Sorgente] = []
        try:
            self.coda.put(Stato("apro Chrome…"))
            driver = apri_chrome()
            apri_portale(driver)
            self.coda.put(ChiediSpid())
            # ⚠️ Nessuna scadenza: si aspetta l'utente, quanto ci mette.
            while not self.vai.is_set() and not self.annullato.is_set():
                if sembra_dentro(driver):
                    self.coda.put(Stato("sei dentro — vado"))
                    break
                self.vai.wait(timeout=1.0)
            if self.annullato.is_set():
                self.coda.put(Rotto("Annullato."))
                return

            esiti: list[EsitoStruttura] = []
            for s in scelte:
                if self.annullato.is_set():
                    break
                try:
                    sorgente = apri(Path(s.sorgente))
                except SorgenteNonValida as exc:
                    e = EsitoStruttura(
                        etichetta=s.etichetta, id_turismatica=s.id_turismatica,
                        saltata=str(exc),
                    )
                    esiti.append(e)
                    self.coda.put(Stato(f"{s.etichetta}: {exc}"))
                    continue
                sorgenti.append(sorgente)
                try:
                    esiti.append(carica_struttura(
                        driver,
                        id_turismatica=s.id_turismatica,
                        etichetta=s.etichetta,
                        sorgente=sorgente,
                        periodo=periodo,
                        avanzamento=lambda m, et=s.etichetta: self.coda.put(
                            Stato(f"{et} — {m}")
                        ),
                    ))
                except Exception as exc:      # noqa: BLE001
                    # Una struttura rotta non toglie il giro alle altre.
                    log.exception("struttura %s interrotta", s.etichetta)
                    esiti.append(EsitoStruttura(
                        etichetta=s.etichetta, id_turismatica=s.id_turismatica,
                        saltata=f"si è interrotta ({type(exc).__name__})",
                    ))
            self.coda.put(Finito(esiti, periodo.etichetta))
        except ChromeNonDisponibile as exc:
            self.coda.put(Rotto(str(exc)))
        except Exception:                     # noqa: BLE001
            log.exception("giro interrotto")
            self.coda.put(Rotto(
                "Qualcosa è andato storto e mi sono fermato.\n\n"
                + traceback.format_exc(limit=3)
            ))
        finally:
            for s in sorgenti:
                s.pulisci()
            if driver is not None:
                with contextlib.suppress(Exception):
                    driver.quit()

    # ── coda → finestra ──────────────────────────────────────────────────────

    def _svuota_coda(self) -> None:
        try:
            while True:
                msg = self.coda.get_nowait()
                if isinstance(msg, Stato):
                    self.stato.set(msg.testo)
                    self._scrivi(msg.testo)
                elif isinstance(msg, ChiediSpid):
                    self._pannello_spid()
                elif isinstance(msg, Finito):
                    self._mostra_riepilogo(msg)
                elif isinstance(msg, Rotto):
                    self.stato.set("fermo")
                    self.bottone.configure(state="normal")
                    messagebox.showerror("Mi sono fermato", msg.messaggio)
        except queue.Empty:
            pass
        self.root.after(150, self._svuota_coda)

    def _pannello_spid(self) -> None:
        """La schermata che dice **tocca a te**. Grande, e senza scadenza."""
        self.stato.set("aspetto che tu entri con SPID")
        top = tkinter.Toplevel(self.root)
        top.title("Tocca a te")
        top.transient(self.root)
        top.geometry("620x330")
        top.protocol("WM_DELETE_WINDOW", lambda: None)

        c = ttk.Frame(top, padding=24)
        c.pack(fill=BOTH, expand=True)
        ttk.Label(
            c, text="Ora tocca a te: entra con SPID o CIE",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor=W)
        ttk.Label(
            c, wraplength=560, justify=LEFT, font=("Segoe UI", 11),
            text=(
                "\nHo aperto Chrome sulla pagina di Turismatica.\n\n"
                "1.  Vai sulla finestra di Chrome che si è aperta\n"
                "2.  Premi «Accedi» ed entra con SPID o CIE, come fai sempre\n"
                "3.  Quando sei dentro, torna qui e premi il pulsante verde\n\n"
                "Non ho fretta: prenditi il tempo che ti serve. "
                "L'accesso lo fai tu — io non conosco né le tue credenziali "
                "né i tuoi codici, e non li salvo da nessuna parte."
            ),
        ).pack(anchor=W)

        bar = ttk.Frame(c)
        bar.pack(fill=X, pady=(14, 0))

        def procedi() -> None:
            self.vai.set()
            top.destroy()

        def annulla() -> None:
            self.annullato.set()
            self.vai.set()
            top.destroy()

        ttk.Button(bar, text="  Sono dentro: vai  ", command=procedi).pack(side=LEFT)
        ttk.Button(bar, text="Annulla", command=annulla).pack(side=LEFT, padx=8)

        def chiudi_se_partito() -> None:
            if self.vai.is_set() or self.annullato.is_set():
                top.destroy()
                return
            top.after(500, chiudi_se_partito)

        top.after(500, chiudi_se_partito)

    def _mostra_riepilogo(self, msg: Finito) -> None:
        testo = riepilogo(msg.esiti, msg.etichetta_periodo)
        self.stato.set("finito")
        self.bottone.configure(state="normal")
        self._scrivi("\n" + "─" * 60 + "\n" + testo)
        _Riepilogo(self.root, testo)

    def _verifica(self) -> None:
        """Il controllo del computer, dalla finestra. Gira su un thread perché
        apre Chrome davvero, e un'app ferma sembra bloccata."""
        self.stato.set("controllo in corso…")

        def lavora() -> None:
            from uploader_turismatica.diagnostica import rapporto

            testo = rapporto()
            self.coda.put(Stato("controllo finito"))
            self.root.after(0, lambda: _Riepilogo(self.root, testo))

        threading.Thread(target=lavora, daemon=True).start()

    def _scrivi(self, testo: str) -> None:
        self.log.configure(state="normal")
        # noqa DTZ005: orario locale, serve solo a leggere il progresso a schermo.
        self.log.insert(END, f"{datetime.now():%H:%M:%S}  {testo}\n")  # noqa: DTZ005
        self.log.see(END)
        self.log.configure(state="disabled")

    def _pulisci_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", END)
        self.log.configure(state="disabled")

    def _chiudi(self) -> None:
        if self.lavoro is not None and self.lavoro.is_alive():
            if not messagebox.askyesno(
                "Sto caricando",
                "Sto ancora caricando. Se chiudo adesso i giorni non ancora "
                "caricati restano da fare.\n\nChiudo lo stesso?",
            ):
                return
            self.annullato.set()
            self.vai.set()
        self.root.destroy()


class _Dialogo:
    """Aggiungi/modifica una struttura. Due campi, e si spiegano da soli."""

    def __init__(self, padre: Tk, iniziale: Struttura) -> None:
        self.risultato: Struttura | None = None
        top = tkinter.Toplevel(padre)
        top.title("Struttura")
        top.transient(padre)
        top.grab_set()
        top.resizable(False, False)
        c = ttk.Frame(top, padding=18)
        c.pack(fill=BOTH, expand=True)

        ttk.Label(c, text="Nome della struttura").grid(row=0, column=0, sticky=W)
        nome = StringVar(value=iniziale.etichetta)
        ttk.Entry(c, textvariable=nome, width=42).grid(row=1, column=0, pady=(2, 2))
        ttk.Label(
            c, text="Serve solo a te per riconoscerla in elenco.",
            foreground="#666",
        ).grid(row=2, column=0, sticky=W, pady=(0, 12))

        ttk.Label(c, text="Numero della struttura su Turismatica").grid(
            row=3, column=0, sticky=W,
        )
        idt = StringVar(value=iniziale.id_turismatica)
        ttk.Entry(c, textvariable=idt, width=42).grid(row=4, column=0, pady=(2, 2))
        ttk.Label(
            c, justify=LEFT, foreground="#666",
            text=(
                "Lo trovi nell'indirizzo della pagina dei movimenti, in fondo:\n"
                "…movimentoospiti.xhtml?idStruttura=12345  →  scrivi  12345\n"
                "⚠️  Non è il numero di beb.it: sono due cose diverse."
            ),
        ).grid(row=5, column=0, sticky=W, pady=(0, 14))

        bar = ttk.Frame(c)
        bar.grid(row=6, column=0, sticky="e")

        def ok() -> None:
            s = Struttura(
                id_turismatica=idt.get().strip(),
                etichetta=nome.get().strip(),
                sorgente=iniziale.sorgente,
            )
            errore = s.valida()
            if errore:
                messagebox.showerror("Controlla", errore, parent=top)
                return
            self.risultato = s
            top.destroy()

        ttk.Button(bar, text="Salva", command=ok).pack(side=RIGHT)
        ttk.Button(bar, text="Annulla", command=top.destroy).pack(side=RIGHT, padx=6)
        top.wait_window()


class _Riepilogo:
    """Il riepilogo finale, in una finestra da cui si può **copiare**: quasi
    sempre finisce in un messaggio a qualcuno."""

    def __init__(self, padre: Tk, testo: str) -> None:
        top = tkinter.Toplevel(padre)
        top.title("Com'è andata")
        top.geometry("680x520")
        c = ttk.Frame(top, padding=14)
        c.pack(fill=BOTH, expand=True)
        area = ScrolledText(c, wrap="word", font=("Consolas", 10))
        area.pack(fill=BOTH, expand=True)
        area.insert(END, testo)
        area.configure(state="disabled")
        bar = ttk.Frame(c)
        bar.pack(fill=X, pady=(10, 0))

        def copia() -> None:
            top.clipboard_clear()
            top.clipboard_append(testo)

        ttk.Button(bar, text="Copia tutto", command=copia).pack(side=LEFT)
        ttk.Button(bar, text="Chiudi", command=top.destroy).pack(side=RIGHT)


def avvia() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
    )
    log.info("impostazioni in %s", percorso_file())
    root = Tk()
    # Il tema nativo di Windows. Su Linux/macOS non esiste e non importa.
    with contextlib.suppress(Exception):
        ttk.Style().theme_use("vista")
    App(root)
    root.mainloop()
