"""Chat Personaggi — chat locale con personaggi AI e memoria JSON.

Struttura del pacchetto:
- database.py    : archivio su file JSON (al posto di SQLite)
- personaggio.py : la scheda canonica del personaggio (identità)
- memoria.py     : umore, situazione, relazione e ricordi, con log e annulla
- ollama.py      : comunicazione con Ollama
- narratore.py   : costruisce il prompt e genera le risposte in streaming
- archivista.py  : aggiorna la memoria in background dopo ogni scambio
"""

__versione__ = "1.0.0"
