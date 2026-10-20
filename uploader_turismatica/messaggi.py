"""Cosa dire al gestore quando qualcosa non va: **cosa è successo e cosa fare**.

Un posto solo per le frasi, così la stessa situazione si dice sempre allo
stesso modo. Niente nomi tecnici («tabella», «selettore», «timeout»): il
gestore vede il portale, non il codice. Il dettaglio tecnico va nel registro.
"""
from __future__ import annotations

from collections.abc import Collection


def struttura_non_tua(id_turismatica: str) -> str:
    return (
        f"La struttura {id_turismatica} non è fra quelle del tuo account "
        "Turismatica. Controlla il numero, oppure rifai «Aggiorna le mie "
        "strutture» entrando con lo SPID di chi gestisce quella struttura."
    )


def uscito_dal_portale() -> str:
    return (
        "Il portale ti ha fatto uscire (la sessione è scaduta). Riprova: ti "
        "chiederò di entrare di nuovo con SPID o CIE."
    )


def struttura_non_attiva(id_turismatica: str, stato: str) -> str:
    return (
        f"Sul portale la struttura {id_turismatica} risulta «{stato.lower()}»: "
        "i movimenti non si possono caricare. Se è un errore, va sistemato con "
        "la Regione."
    )


def movimenti_non_aperti(id_turismatica: str) -> str:
    return (
        f"Il portale non ha aperto la pagina dei movimenti della struttura "
        f"{id_turismatica}. Riprova fra qualche minuto; se succede ancora, apri "
        "«Dettagli» e manda il registro."
    )


def mese_non_raggiunto(mostrato: str, voluto: str) -> str:
    return (
        f"Il portale mostra {mostrato} e non sono riuscito a passare a {voluto}. "
        f"Apri tu {voluto} sul portale, nella pagina dei movimenti, poi riprova: "
        "il portale ricorda l'ultimo mese aperto."
    )


def strutture_non_lette(percorso_copia: str | None) -> str:
    base = (
        "Sono entrato nel portale ma non sono riuscito a leggere l'elenco delle "
        "tue strutture. Scrivi qui sotto il numero di ognuna: lo trovi "
        "nell'indirizzo della pagina dei movimenti, dopo «idStruttura=»."
    )
    if percorso_copia:
        base += (
            f" Ho salvato una copia della pagina, senza dati personali, in "
            f"{percorso_copia}: mandala a chi ti assiste, così la lettura "
            "automatica si sistema."
        )
    return base


def chrome_non_si_apre(dettaglio: str) -> str:
    return dettaglio  # chrome.py lo scrive già per il gestore


def zip_non_valido(dettaglio: str) -> str:
    return f"{dettaglio} Scegli lo zip dei file ISTAT del mese."


def nessun_file_istat(nome: str) -> str:
    return (
        f"In «{nome}» non ho trovato file ISTAT giornalieri "
        "(schedine_istat_…_AAAAMMGG.txt oppure GGMMAAAA.txt). È lo zip giusto?"
    )


#: Cosa scrive il portale quando la sessione non c'è più o la pagina non è per
#: te. In minuscolo: si confronta col testo visibile della pagina.
_SEGNI_USCITA = ("accedi con spid", "entra con spid", "sessione scaduta",
                 "sessione è scaduta")
_SEGNI_NEGATO = (
    "non autorizzat", "accesso negato", "non abilitat", "non hai i permessi",
    "struttura non trovata", "errore 403", "forbidden",
)
_URL_USCITA = ("login", "spid", "/idp", "logout")


def perche_movimenti_non_aperti(
    id_turismatica: str,
    *,
    url: str,
    testo_pagina: str,
    strutture_note: Collection[str],
) -> str:
    """Il messaggio quando la pagina dei movimenti non si apre — il caso
    «la tabella dei movimenti non si è aperta» della prima prova, che non
    diceva né perché né cosa fare.

    In ordine: il numero non è fra quelli letti dal tuo account · il portale
    dice che non è tua · la sessione è finita · non si sa (e allora lo si dice
    così, con la cosa da fare)."""
    testo = testo_pagina.lower()
    if strutture_note and id_turismatica not in strutture_note:
        return struttura_non_tua(id_turismatica)
    if any(s in testo for s in _SEGNI_NEGATO):
        return struttura_non_tua(id_turismatica)
    if any(s in url.lower() for s in _URL_USCITA) or any(s in testo for s in _SEGNI_USCITA):
        return uscito_dal_portale()
    return movimenti_non_aperti(id_turismatica)
