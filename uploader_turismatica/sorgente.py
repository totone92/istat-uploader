"""Da dove arrivano i .txt: uno **zip** di HostLab o una **cartella** già estratta.

Logica pura più un po' di file I/O locale: niente Selenium, niente rete. È la
parte che si può provare davvero, e conviene che sia grossa.

## I due nomi che esistono davvero

Non se ne inventa un terzo, e non si chiede all'utente di rinominare niente:

* ``schedine_istat_<idBooking>_<AAAAMMGG>.txt`` — come li scrive HostLab
  (``sync/istat_export.py``) e come stanno dentro lo zip che l'app scarica;
* ``GGMMAAAA.txt`` — come li nominava lo script originale.

⚠️ **L'``<idBooking>`` nel nome di HostLab NON è l'id Turismatica della
struttura**: è l'id della struttura su *beb.it*. Sono due numeri diversi e non
si deducono l'uno dall'altro — è la ragione per cui la struttura la dichiara
l'utente una volta e resta salvata, invece di essere indovinata dal nome del
file.

## Perché la data si legge dal nome e non dal contenuto

Il file è il movimento **di un giorno**, e il portale ha una riga per giorno: se
il nome dice una data e il contenuto un'altra, caricarlo sulla riga sbagliata è
una dichiarazione falsa fatta a nome del gestore. Il nome è ciò che entrambi i
produttori scrivono apposta; il contenuto non ha un campo data che valga come
chiave. Quindi si legge il nome, e un file il cui nome non dice una data non si
carica — si **elenca fra quelli non riconosciuti**, che è diverso da tacere.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from uploader_turismatica.periodo import Periodo

#: ``schedine_istat_<qualcosa>_<AAAAMMGG>.txt`` — il nome di HostLab.
_HOSTLAB = re.compile(r"^schedine_istat_.*_(\d{8})\.txt$", re.IGNORECASE)
#: ``GGMMAAAA.txt`` — il nome dello script originale.
_OTTO_CIFRE = re.compile(r"^(\d{8})\.txt$", re.IGNORECASE)

#: Il marcatore dello zip di prova (``scripts/zip_di_prova.py``).
MARCATORE_PROVA = "PROVA.txt"
#: Il nome della struttura nei file inventati dello zip di prova.
STRUTTURA_DI_PROVA = b"STRUTTURA DI PROVA"
MESSAGGIO_ZIP_DI_PROVA = "Questo è lo zip di prova: serve solo in modalità prova."


def data_dal_nome(nome: str) -> date | None:
    """La data che il nome del file dichiara, o ``None`` se non ne dichiara una.

    ⚠️ **L'ordine dei tentativi è la sostanza, perché le due convenzioni sono
    ambigue fra loro**: ``01022026`` è il 1° febbraio 2026 letto GGMMAAAA, e
    sarebbe l'anno 102 letto AAAAMMGG. Si decide dal **prefisso del nome**, che
    è un fatto, non dalla plausibilità della data, che è un indovinello:

    1. nome di HostLab ⇒ AAAAMMGG, sempre;
    2. otto cifre nude ⇒ GGMMAAAA, sempre (è la convenzione dello script
       originale, e non ne esistono altre con quella forma);
    3. tutto il resto ⇒ ``None``. Non si va a caccia di otto cifre in mezzo a un
       nome qualunque: un file scaricato due volte si chiama
       ``...(1).txt`` e va riconosciuto lo stesso (ci pensa il punto 1), ma un
       nome che non appartiene a nessuna delle due convenzioni non è un file
       nostro e indovinarne la data sarebbe caricarlo su una riga a caso.
    """
    m = _HOSTLAB.match(nome.strip())
    if m is not None:
        return _parse(m.group(1), "%Y%m%d")
    m = _OTTO_CIFRE.match(nome.strip())
    if m is not None:
        return _parse(m.group(1), "%d%m%Y")
    return None


def _parse(cifre: str, formato: str) -> date | None:
    try:
        # noqa DTZ007: il nome del file dichiara un GIORNO di calendario, non
        # un istante. Attaccargli un fuso inventerebbe un'informazione.
        return datetime.strptime(cifre, formato).date()  # noqa: DTZ007
    except ValueError:
        return None


@dataclass
class Sorgente:
    """I file di una struttura, indicizzati per giorno.

    ``non_riconosciuti`` non è un dettaglio da log: se l'utente sceglie la
    cartella sbagliata, questa lista è l'unico posto in cui la cosa si vede
    prima di aprire Chrome."""

    per_giorno: dict[date, Path] = field(default_factory=dict)
    non_riconosciuti: list[str] = field(default_factory=list)
    #: ``True`` per lo zip di prova: file inventati, che **non** devono mai
    #: arrivare al portale. Vedi :func:`blocco_modalita_vera`.
    di_prova: bool = False
    #: Directory temporanea da cancellare a fine giro (solo se veniva da uno zip).
    _temp: Path | None = None

    def file_del(self, giorno: date) -> Path | None:
        return self.per_giorno.get(giorno)

    def mancanti(self, periodo: Periodo) -> list[date]:
        return [g for g in periodo.giorni if g not in self.per_giorno]

    def presenti(self, periodo: Periodo) -> list[date]:
        return [g for g in periodo.giorni if g in self.per_giorno]

    @property
    def primo(self) -> date | None:
        return min(self.per_giorno) if self.per_giorno else None

    @property
    def ultimo(self) -> date | None:
        return max(self.per_giorno) if self.per_giorno else None

    def pulisci(self) -> None:
        """Cancella l'estrazione temporanea. Idempotente e non solleva mai: a
        fine giro un errore qui non deve trasformare un caricamento riuscito in
        un messaggio di errore."""
        if self._temp is None:
            return
        shutil.rmtree(self._temp, ignore_errors=True)
        self._temp = None


class SorgenteNonValida(Exception):
    """Il percorso scelto non è uno zip né una cartella leggibile."""


def apri(percorso: Path) -> Sorgente:
    """Apre uno **zip** (estraendolo in una temporanea) o una **cartella**.

    Entrambi si accettano, e non per gentilezza: lo zip è quello che HostLab fa
    scaricare, la cartella è quella che resta a chi lo ha già aperto a mano — e
    fra i due c'è il doppio clic di Windows, che estrae senza che l'utente
    pensi di aver fatto niente.

    ⚠️ Dentro lo zip si guarda a **qualunque profondità**: un .zip aperto e
    ricompresso da Windows si ritrova i file dentro una cartella con lo stesso
    nome dell'archivio, e pretendere che siano in cima farebbe fallire il caso
    più comune.
    """
    percorso = Path(percorso).expanduser()
    if not percorso.exists():
        raise SorgenteNonValida(f"Non trovo «{percorso.name}».")
    if percorso.is_dir():
        return _indicizza(sorted(percorso.rglob("*.txt")), temp=None)
    if percorso.suffix.lower() != ".zip":
        raise SorgenteNonValida(
            f"«{percorso.name}» non è né uno .zip né una cartella."
        )
    try:
        temp = Path(tempfile.mkdtemp(prefix="istat-"))
        with zipfile.ZipFile(percorso) as zf:
            _estrai_sicuro(zf, temp)
    except zipfile.BadZipFile as exc:
        raise SorgenteNonValida(
            f"«{percorso.name}» non si apre: il file è danneggiato o non è uno zip."
        ) from exc
    return _indicizza(sorted(temp.rglob("*.txt")), temp=temp)


def _estrai_sicuro(zf: zipfile.ZipFile, dove: Path) -> None:
    """Estrae **solo** i .txt, e solo dentro ``dove``.

    ⚠️ Non è zelo: uno zip può contenere percorsi che risalgono
    (``../../qualcosa``) e scrivere fuori dalla cartella di destinazione — è il
    ``zip slip``. Qui lo zip lo produce HostLab, ma il campo lo riempie
    l'utente, e un file scelto per sbaglio non deve poter toccare il resto del
    PC. ``extract`` da solo non basta come garanzia: si controlla il percorso
    risolto."""
    radice = dove.resolve()
    for info in zf.infolist():
        if info.is_dir() or not info.filename.lower().endswith(".txt"):
            continue
        destinazione = (dove / Path(info.filename).name).resolve()
        if not destinazione.is_relative_to(radice):
            continue
        with zf.open(info) as sorgente, destinazione.open("wb") as out:
            shutil.copyfileobj(sorgente, out)


def blocco_modalita_vera(sorgente: Sorgente, *, prova: bool) -> str | None:
    """Il messaggio per cui questa sorgente non si può caricare davvero, o
    ``None``. Oggi un caso solo: lo zip di prova in modalità vera."""
    if sorgente.di_prova and not prova:
        return MESSAGGIO_ZIP_DI_PROVA
    return None


def _e_di_prova(path: Path) -> bool:
    """Lo zip di prova si riconosce in due modi, e ne basta uno: il marcatore
    ``PROVA.txt``, oppure un file il cui nome di struttura è quello inventato.
    Il secondo c'è perché il marcatore si può perdere (estratto a mano, file
    cancellato) e i giorni inventati restano lì, con i loro nomi validi."""
    if path.name.lower() == MARCATORE_PROVA.lower():
        return True
    try:
        with path.open("rb") as f:
            return f.read(len(STRUTTURA_DI_PROVA)) == STRUTTURA_DI_PROVA
    except OSError:
        return False


def _indicizza(files: list[Path], *, temp: Path | None) -> Sorgente:
    s = Sorgente(_temp=temp)
    for path in files:
        if _e_di_prova(path):
            s.di_prova = True
            if path.name.lower() == MARCATORE_PROVA.lower():
                continue          # il marcatore non è un giorno, né un «non riconosciuto»
        giorno = data_dal_nome(path.name)
        if giorno is None:
            s.non_riconosciuti.append(path.name)
            continue
        # Stesso giorno due volte (zip + cartella, o un doppione scaricato):
        # vince il primo in ordine alfabetico, che è deterministico. Sono lo
        # stesso movimento dello stesso giorno — beb li genera on-demand
        # identici — quindi non c'è una scelta da fare, c'è da non oscillare.
        s.per_giorno.setdefault(giorno, path)
    return s
