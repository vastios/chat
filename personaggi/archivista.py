"""L'archivista: aggiorna la memoria del personaggio dopo ogni scambio.

Nel vecchio LocalStoryEngine i ricordi e la fiducia dei PNG andavano scritti
a mano. Questo modulo chiude quel "passaggio successivo" mai arrivato:
dopo ogni risposta del personaggio, un modello leggero rilegge l'ultimo
scambio e propone le modifiche alla memoria in JSON, che vengono validate
e applicate da memoria.applica_aggiornamenti().

L'archivista non solleva mai eccezioni: se qualcosa va storto la chat
continua e la memoria semplicemente non cambia.
"""

import json
import re

from personaggi import database, memoria, personaggio
from personaggi.ollama import ErroreOllama, chat
from config import (
    MAX_RICORDI_PER_SCAMBIO,
    MODELLO_ARCHIVISTA,
    PROMPT_ARCHIVISTA,
)


def _estrai_json(testo):
    return personaggio.estrai_json(testo)


def _normalizza_aggiornamenti(dati):
    """Pulisce il JSON dell'archivista: solo campi validi e ben formati."""
    if not isinstance(dati, dict):
        return {}
    puliti = {}

    if isinstance(dati.get("umore"), str) and dati["umore"].strip():
        puliti["umore"] = dati["umore"]
    if isinstance(dati.get("situazione"), str) and dati["situazione"].strip():
        puliti["situazione"] = dati["situazione"]

    relazione = dati.get("relazione")
    if isinstance(relazione, dict):
        relazione_pulita = {}
        if relazione.get("delta_fiducia") not in (None, ""):
            relazione_pulita["delta_fiducia"] = relazione["delta_fiducia"]
        if isinstance(relazione.get("nota"), str) and relazione["nota"].strip():
            relazione_pulita["nota"] = relazione["nota"]
        if relazione_pulita:
            puliti["relazione"] = relazione_pulita

    nuovi = dati.get("nuovi_ricordi")
    if isinstance(nuovi, list):
        ricordi_puliti = []
        for elemento in nuovi[:MAX_RICORDI_PER_SCAMBIO]:
            if isinstance(elemento, dict) and str(elemento.get("testo", "")).strip():
                ricordi_puliti.append(elemento)
        if ricordi_puliti:
            puliti["nuovi_ricordi"] = ricordi_puliti

    return puliti


def aggiorna_memoria(id_personaggio, nome_utente=""):
    """Rilegge l'ultimo scambio e aggiorna memoria.json.

    Restituisce l'elenco delle modifiche applicate (lista di frasi), vuoto
    se non c'era nulla da aggiornare o se l'archivista non è riuscito
    nel suo compito. Non solleva mai eccezioni.
    """
    try:
        conversazione = database.carica_conversazione(id_personaggio)
        messaggi = conversazione.get("messaggi", [])
        if not messaggi:
            return []

        # Riprende dal punto in cui l'archivista si era fermato: nel log di ogni
        # suo aggiornamento c'è quanti messaggi erano stati elaborati. Così non
        # si dipende dai timestamp e non si elabora mai due volte lo stesso scambio.
        gia_elaborati = 0
        for voce in reversed(database.leggi_log(id_personaggio, ultime=200)):
            if voce.get("nota") == "Aggiornamento archivista" and isinstance(voce.get("n_messaggi"), int):
                gia_elaborati = voce["n_messaggi"]
                break
        if len(messaggi) < gia_elaborati:
            # La cronologia è stata svuotata tra un aggiornamento e l'altro.
            gia_elaborati = 0
        totale_messaggi = len(messaggi)
        nuovi = messaggi[gia_elaborati:]
        if not any(m.get("ruolo") == "utente" for m in nuovi):
            return []
        messaggi = nuovi

        scheda = database.carica_scheda(id_personaggio)
        memoria_attuale = memoria.normalizza_memoria(
            database.carica_memoria(id_personaggio)
        )

        contesto = {
            "nome": scheda.get("nome", "Personaggio"),
            "max_ricordi": str(MAX_RICORDI_PER_SCAMBIO),
        }
        richiesta = [
            {
                "role": "system",
                "content": PROMPT_ARCHIVISTA.format(**contesto),
            },
            {
                "role": "user",
                "content": (
                    f"MEMORIA ATTUALE DI {scheda.get('nome', 'il personaggio')}:\n"
                    + json.dumps(memoria_attuale, ensure_ascii=False, indent=1)
                    + "\n\nULTIMO SCAMBIO CON "
                    + (nome_utente or "l'utente").upper()
                    + ":\n"
                    + "\n".join(
                        f"{'UTENTE' if m.get('ruolo') == 'utente' else scheda.get('nome', 'PERSONAGGIO')}: "
                        f"{m.get('testo', '')}"
                        for m in messaggi
                        if m.get("testo")
                    )
                ),
            },
        ]

        risposta = chat(
            richiesta,
            modello=MODELLO_ARCHIVISTA,
            formato="json",
        )
        dati = _estrai_json(risposta)
        if dati is None:
            return []
        aggiornamenti = _normalizza_aggiornamenti(dati)
        if not aggiornamenti:
            return []
        return memoria.applica_aggiornamenti(
            id_personaggio,
            aggiornamenti,
            nota="Aggiornamento archivista",
            n_messaggi=totale_messaggi,
        )
    except (ErroreOllama, FileNotFoundError, OSError, ValueError):
        return []
