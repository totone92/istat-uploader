"""Le strutture del gestore, lette dalla pagina del portale — e la copia
ripulita della pagina quando la lettura non riesce.

⚠️ **La pagina con l'elenco delle strutture non l'abbiamo mai vista.** Quello
che il codice sa per certo del portale è una cosa sola: ogni struttura ha un
numero, ``idStruttura``, che compare negli indirizzi
(``…/movimentoospiti.xhtml?idStruttura=12345``) e nei parametri JSF. Per questo
la lettura **parte da lì**, non da un selettore CSS indovinato:

1. ogni attributo che contiene ``idStruttura`` seguito da un numero (``href``,
   ``onclick``, ``data-*``, parametri ``{'idStruttura':'12345'}``) è una
   struttura;
2. il nome, il comune e la tipologia si cercano **intorno**: nella riga di
   tabella che lo contiene, usando le intestazioni delle colonne se ci sono; se
   non c'è una tabella, nel blocco (``li``, ``div`` a scheda) che lo racchiude;
3. una ``<select>`` di strutture (``id``/``name`` con «strutt») dà numero e nome
   dalle sue ``<option>``.

Se tutto questo non trova niente, l'app salva una copia della pagina **senza
dati personali** (:func:`ripulisci`) e lascia inserire i numeri a mano. Con
quella copia la lettura si sistema in un giro.

Sola lettura: qui dentro si guarda HTML, non si clicca niente. I link da
seguire (:func:`link_da_seguire`) sono solo ``href`` veri — mai ``javascript:``,
mai un modulo.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

# ─── un albero HTML minimo, con la libreria standard ────────────────────────

_VUOTI = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
    "param", "source", "track", "wbr",
})
#: Tag che si chiudono da soli quando ne arriva un altro dello stesso gruppo.
_CHIUSURA_IMPLICITA = {
    "td": {"td", "th"}, "th": {"td", "th"}, "tr": {"tr"}, "li": {"li"},
    "option": {"option"}, "p": {"p"},
}


@dataclass
class Nodo:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    figli: list[Nodo | str] = field(default_factory=list)
    padre: Nodo | None = field(default=None, repr=False)

    def testo(self) -> str:
        parti: list[str] = []

        def visita(n: Nodo) -> None:
            if n.tag in ("script", "style"):
                return
            for f in n.figli:
                if isinstance(f, str):
                    parti.append(f)
                else:
                    visita(f)

        visita(self)
        return " ".join(" ".join(parti).split())

    def discendenti(self) -> list[Nodo]:
        out: list[Nodo] = []
        for f in self.figli:
            if isinstance(f, Nodo):
                out.append(f)
                out.extend(f.discendenti())
        return out

    def antenato(self, *tag: str) -> Nodo | None:
        n = self.padre
        while n is not None:
            if n.tag in tag:
                return n
            n = n.padre
        return None

    def classi(self) -> str:
        return f"{self.attrs.get('class', '')} {self.attrs.get('id', '')}".lower()


class _Costruttore(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.radice = Nodo("#documento")
        self.pila: list[Nodo] = [self.radice]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        chiude = _CHIUSURA_IMPLICITA.get(tag)
        if chiude:
            for i in range(len(self.pila) - 1, 0, -1):
                if self.pila[i].tag in chiude:
                    del self.pila[i:]
                    break
                if self.pila[i].tag in ("table", "tbody", "thead", "ul", "ol", "select"):
                    break
        n = Nodo(tag, {k: (v or "") for k, v in attrs}, padre=self.pila[-1])
        self.pila[-1].figli.append(n)
        if tag not in _VUOTI:
            self.pila.append(n)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        n = Nodo(tag, {k: (v or "") for k, v in attrs}, padre=self.pila[-1])
        self.pila[-1].figli.append(n)

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.pila) - 1, 0, -1):
            if self.pila[i].tag == tag:
                del self.pila[i:]
                return

    def handle_data(self, data: str) -> None:
        self.pila[-1].figli.append(data)


def albero(pagina: str) -> Nodo:
    c = _Costruttore()
    c.feed(pagina)
    c.close()
    return c.radice


def serializza(n: Nodo | str) -> str:
    if isinstance(n, str):
        return html.escape(n, quote=False)
    if n.tag == "#documento":
        return "".join(serializza(f) for f in n.figli)
    attrs = "".join(f' {k}="{html.escape(v)}"' for k, v in n.attrs.items())
    if n.tag in _VUOTI:
        return f"<{n.tag}{attrs}>"
    dentro = "".join(serializza(f) for f in n.figli)
    return f"<{n.tag}{attrs}>{dentro}</{n.tag}>"


# ─── le strutture ────────────────────────────────────────────────────────────

#: ``idStruttura=12345`` · ``{'idStruttura':'12345'}`` · e la forma dei
#: parametri PrimeFaces ``{name:'idStruttura',value:'12345'}``.
_ID_STRUTTURA = re.compile(
    r"idStruttura['\"]?\s*(?:,\s*value\s*)?[=:,]\s*['\"]?(\d{2,9})", re.IGNORECASE,
)
#: Testi di link che sono azioni, non nomi («Movimenti», «Apri», …).
_AZIONI = re.compile(
    r"^(apri|vai|seleziona|scegli|movimenti?|dettagli?o?|gestisci|entra|visualizza|"
    r"modifica|ospiti|comunicazioni|>+|»)$",
    re.IGNORECASE,
)
_COL_NOME = re.compile(r"denominaz|insegna|^nome|nome struttura|^struttura", re.I)
_COL_COMUNE = re.compile(r"comune|localit|citt", re.I)
_COL_TIPO = re.compile(r"tipolog|categoria|^tipo", re.I)
_COL_STATO = re.compile(r"^stato", re.I)
_COL_ID = re.compile(r"^(id|codice|n\.?°?|numero)\b", re.I)


@dataclass
class StrutturaTrovata:
    id_turismatica: str
    nome: str = ""
    comune: str = ""
    tipologia: str = ""
    stato: str = ""

    def completezza(self) -> int:
        return sum(bool(x) for x in (self.nome, self.comune, self.tipologia, self.stato))


def _intestazioni(tabella: Nodo) -> list[str]:
    """Le intestazioni di colonna: i ``th`` (in ``thead`` o nella prima riga)."""
    for riga in (n for n in tabella.discendenti() if n.tag == "tr"):
        celle = [c for c in riga.figli if isinstance(c, Nodo) and c.tag in ("th", "td")]
        if celle and all(c.tag == "th" for c in celle):
            return [c.testo() for c in celle]
    return []


def _celle(riga: Nodo) -> list[Nodo]:
    return [c for c in riga.figli if isinstance(c, Nodo) and c.tag in ("td", "th")]


def _da_riga(id_t: str, riga: Nodo, ancora: Nodo) -> StrutturaTrovata:
    s = StrutturaTrovata(id_t)
    tabella = riga.antenato("table")
    titoli = _intestazioni(tabella) if tabella is not None else []
    celle = _celle(riga)
    for i, cella in enumerate(celle):
        titolo = titoli[i] if i < len(titoli) else ""
        valore = cella.testo()
        if not valore or not titolo:
            continue
        if _COL_ID.search(titolo) and not _COL_NOME.search(titolo):
            continue
        if _COL_NOME.search(titolo) and not s.nome:
            s.nome = valore
        elif _COL_COMUNE.search(titolo) and not s.comune:
            s.comune = valore
        elif _COL_TIPO.search(titolo) and not s.tipologia:
            s.tipologia = valore
        elif _COL_STATO.search(titolo) and not s.stato:
            s.stato = valore
    if not s.nome:
        s.nome = _nome_senza_intestazioni(id_t, ancora, [c.testo() for c in celle])
    return s


def _nome_senza_intestazioni(id_t: str, ancora: Nodo, testi: list[str]) -> str:
    proprio = ancora.testo()
    if proprio and not _AZIONI.match(proprio) and not proprio.isdigit():
        return _togli_id(proprio, id_t)
    for t in testi:
        if t and re.search(r"[A-Za-zÀ-ÿ]{3}", t) and not _AZIONI.match(t):
            return _togli_id(t, id_t)
    return ""


def _togli_id(testo: str, id_t: str) -> str:
    """«12345 - CASA LAVANDA» → «CASA LAVANDA»."""
    return re.sub(rf"^\s*\(?{id_t}\)?\s*[-–:|]?\s*|\s*[-–(]?\s*{id_t}\)?\s*$", "", testo).strip()


def _da_blocco(id_t: str, ancora: Nodo) -> StrutturaTrovata:
    """Senza tabella: il blocco più vicino che sembra una scheda."""
    n = ancora.padre
    while n is not None and n.tag != "#documento":
        if n.tag == "li" or (n.tag in ("div", "section", "article") and re.search(
            r"card|item|strutt|box|panel|row", n.classi(),
        )):
            break
        n = n.padre
    blocco = n if n is not None and n.tag != "#documento" else ancora
    s = StrutturaTrovata(id_t)
    titolo = next(
        (d.testo() for d in blocco.discendenti()
         if d.tag in ("h1", "h2", "h3", "h4", "h5", "strong", "b") and d.testo()),
        "",
    )
    s.nome = _togli_id(titolo, id_t) if titolo else _nome_senza_intestazioni(
        id_t, ancora, [blocco.testo()],
    )
    s.comune = _etichettato(blocco, "comune")
    s.tipologia = _etichettato(blocco, "tipologia")
    return s


def _etichettato(blocco: Nodo, etichetta: str) -> str:
    """Il valore di «Comune: Spello» dentro il blocco: dall'elemento **più
    piccolo** che comincia con l'etichetta, così il testo dei vicini (il link
    «Apri») non ci finisce dentro."""
    candidati = [
        d.testo() for d in blocco.discendenti()
        if re.match(rf"{etichetta}\s*:", d.testo(), re.I)
    ]
    if not candidati:
        return ""
    breve = min(candidati, key=len)
    return breve.split(":", 1)[1].strip(" ·|,;")


def strutture(pagina: str) -> list[StrutturaTrovata]:
    """Le strutture che la pagina mostra, una per numero, in ordine di nome."""
    radice = albero(pagina)
    trovate: dict[str, StrutturaTrovata] = {}

    def tieni(s: StrutturaTrovata) -> None:
        vecchia = trovate.get(s.id_turismatica)
        if vecchia is None or s.completezza() > vecchia.completezza():
            trovate[s.id_turismatica] = s

    for n in radice.discendenti():
        if n.tag == "select" and "strutt" in (
            n.attrs.get("id", "") + n.attrs.get("name", "")
        ).lower():
            for o in (d for d in n.discendenti() if d.tag == "option"):
                valore = o.attrs.get("value", "").strip()
                if valore.isdigit() and int(valore) > 0:
                    tieni(StrutturaTrovata(valore, _togli_id(o.testo(), valore)))
            continue
        for valore in n.attrs.values():
            for m in _ID_STRUTTURA.finditer(valore):
                id_t = m.group(1)
                riga = n.antenato("tr")
                tieni(_da_riga(id_t, riga, n) if riga is not None else _da_blocco(id_t, n))
    return sorted(trovate.values(), key=lambda s: (s.nome.lower(), s.id_turismatica))


def link_da_seguire(pagina: str, indirizzo: str, massimo: int = 3) -> list[str]:
    """Le pagine dove l'elenco delle strutture potrebbe stare, se non è in
    questa: link **veri** (``href`` http) il cui testo o indirizzo parla di
    strutture. Mai ``javascript:``, mai ``#``, mai un'uscita."""
    out: list[str] = []
    for n in albero(pagina).discendenti():
        if n.tag != "a":
            continue
        href = n.attrs.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        testo = f"{n.testo()} {href}".lower()
        if "strutt" not in testo or re.search(r"logout|esci|nuova|aggiungi|elimina", testo):
            continue
        assoluto = urljoin(indirizzo, href)
        if assoluto.startswith("http") and assoluto not in out:
            out.append(assoluto)
        if len(out) >= massimo:
            break
    return out


# ─── la copia della pagina, senza dati personali ────────────────────────────

_CF = re.compile(
    r"\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-EHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_TELEFONO = re.compile(r"(?<![\w/=])\+?\d[\d .-]{7,}\d(?![\w])")
#: Un token: 32+ caratteri **con lettere e cifre** (i nomi di classe lunghi,
#: come ``ui-datatable-scrollable-header-box``, non hanno cifre e restano).
_TOKEN = re.compile(
    r"(?=[A-Za-z0-9+/_=-]*\d)(?=[A-Za-z0-9+/_=-]*[A-Za-z])[A-Za-z0-9+/_=-]{32,}"
)
#: Attributi che descrivono la forma della pagina: servono interi.
_ATTRIBUTI_DI_FORMA = frozenset({"class", "id", "name", "for", "style", "role", "type"})
_SESSIONE = re.compile(r";jsessionid=[^?#\"'\s]*", re.IGNORECASE)
_PARAMETRI_RISERVATI = re.compile(
    r"([?&](?:token|code|state|samlresponse|relaystate|sessionid|jsessionid|ticket)=)[^&#\"'\s]*",
    re.IGNORECASE,
)
_CLASSI_PERSONA = re.compile(
    r"utente|user|nominativ|profil|account|benvenut|anagrafic|titolare|"
    r"gestore|referente|legale|operatore|login-name|username",
)
_COLONNE_PERSONA = re.compile(
    r"titolare|gestore|referente|responsabil|legale|proprietar|cognome|"
    r"nominativ|codice fiscale|e-?mail|pec|telefon|cellulare|nato|nascita",
    re.IGNORECASE,
)
_BENVENUTO = re.compile(r"(benvenut[oa]|ciao|salve)\s*,?\s*[^<\n]{0,60}", re.IGNORECASE)
RIMOSSO = "[RIMOSSO]"


def _telefono(m: re.Match[str]) -> str:
    """Solo con almeno 9 cifre: una data «01.09.2026» ne ha 8 e resta."""
    return "[TELEFONO RIMOSSO]" if sum(c.isdigit() for c in m.group(0)) >= 9 else m.group(0)


def _ripulisci_testo(t: str) -> str:
    t = _CF.sub("[CODICE FISCALE RIMOSSO]", t)
    t = _EMAIL.sub("[EMAIL RIMOSSA]", t)
    t = _TELEFONO.sub(_telefono, t)
    t = _TOKEN.sub("[TOKEN RIMOSSO]", t)
    return _BENVENUTO.sub(lambda m: f"{m.group(1)} {RIMOSSO}", t)


def _ripulisci_attributo(nome: str, valore: str) -> str:
    valore = _SESSIONE.sub("", valore)
    valore = _PARAMETRI_RISERVATI.sub(r"\1" + RIMOSSO, valore)
    if nome in ("value", "title", "alt", "placeholder", "aria-label", "content") or nome.startswith("data-"):
        valore = _ripulisci_testo(valore)
    valore = _CF.sub("[CODICE FISCALE RIMOSSO]", valore)
    if nome in _ATTRIBUTI_DI_FORMA:
        return valore
    return _TOKEN.sub("[TOKEN RIMOSSO]", valore)


def _svuota(n: Nodo) -> None:
    n.figli = [RIMOSSO]


def ripulisci(pagina: str) -> str:
    """La pagina senza dati personali, per mandarla a chi sistema la lettura.

    Toglie: codici fiscali, email, telefoni, token e identificativi di sessione
    (anche nei link), il valore di **ogni** campo di modulo, il contenuto degli
    script, i blocchi che parlano dell'utente (``utente``, ``profilo``,
    ``benvenuto``…) e le colonne di tabella con nomi di persone (titolare,
    referente, codice fiscale…). Lascia la **forma** della pagina — tag, classi,
    id, intestazioni, numeri e nomi delle strutture — che è ciò che serve per
    sistemare la lettura. ⚠️ È fatto con cura, non è una garanzia: la copia si
    può aprire e guardare prima di mandarla, e l'app lo dice."""
    radice = albero(pagina)
    for n in radice.discendenti():
        n.attrs = {k: _ripulisci_attributo(k, v) for k, v in n.attrs.items()}
        if n.tag == "input" or n.tag == "textarea":
            if "value" in n.attrs:
                n.attrs["value"] = RIMOSSO
            if n.tag == "textarea":
                _svuota(n)
        elif n.tag in ("script", "noscript"):
            n.figli = ["/* contenuto rimosso */"] if n.figli else []
        elif _CLASSI_PERSONA.search(n.classi()) and n.tag not in ("html", "body", "form"):
            _svuota(n)
    for tabella in (n for n in radice.discendenti() if n.tag == "table"):
        titoli = _intestazioni(tabella)
        personali = {i for i, t in enumerate(titoli) if _COLONNE_PERSONA.search(t)}
        if not personali:
            continue
        for riga in (n for n in tabella.discendenti() if n.tag == "tr"):
            for i, c in enumerate(_celle(riga)):
                if i in personali and c.tag == "td":
                    _svuota(c)

    def testi(n: Nodo) -> None:
        n.figli = [_ripulisci_testo(f) if isinstance(f, str) else f for f in n.figli]
        for f in n.figli:
            if isinstance(f, Nodo):
                testi(f)

    testi(radice)
    return "<!-- copia ripulita da Istat Uploader: senza dati personali -->\n" + serializza(radice)
