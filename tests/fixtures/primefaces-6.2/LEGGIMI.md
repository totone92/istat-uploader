# PrimeFaces 6.2 — solo per i test

I file JavaScript che la pagina vera dei movimenti carica dal portale
(`javax.faces.resource/…?ln=primefaces&v=6.2`), presi così come sono dal jar
ufficiale `org.primefaces:primefaces:6.2` di Maven Central
(sha256 del jar `007bdea064f20cecad6773442a08062149b197d8a57329d070d945c06274f0cf`).
Licenza: Apache 2.0 (`LICENSE.txt`, dal jar); jQuery dentro `jquery.js` è MIT,
con la sua intestazione.

Servono a `tests/chrome_vero.py`: Chrome apre le copie delle pagine del portale
**con il loro JavaScript**, come sul PC del gestore. È lì che si è visto il
guasto della v1.3.1 — PrimeFaces, all'avvio, mette in ogni cella della tabella
l'etichetta della colonna (`<span class="ui-column-title">Data</span>`), e una
lettura provata solo sull'HTML del server non lo vede.

Non entrano nell'eseguibile.
