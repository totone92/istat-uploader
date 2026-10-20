"""Caricatore dei movimenti ISTAT su Turismatica (Regione Umbria).

L'app fa **una cosa sola**: prende i file .txt di un periodo, apre Chrome sul
portale, **aspetta che l'utente entri con SPID/CIE**, e poi carica giorno per
giorno.

⚠️ **Il login NON si automatizza e non deve.** È SPID/CIE: l'identità è della
persona, non del programma. È anche il motivo per cui questa app vive sul PC
del gestore e non su un server.

Non genera e non converte niente: i .txt li produce beb.it e li scarica
HostLab. Qui si caricano e basta.
"""

__version__ = "1.1.1"
