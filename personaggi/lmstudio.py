"""Comunicazione con LM Studio.

Esattamente come nel vecchio LocalStoryEngine (game/narrator.py): si parla con
il server locale di LM Studio tramite l'API OpenAI-compatibile, e il modello
usato è quello caricato in LM Studio in quel momento — nessun modello fisso
nel codice. Rispetto al vecchio progetto, in più, la risposta del personaggio
arriva in streaming, pezzo per pezzo.

Prerequisiti: LM Studio aperto, un modello caricato e il server locale avviato
(scheda Developer → Start Server, porta predefinita 1234).
"""

import json

import requests

from config import (
    BASE_URL,
    MAX_TOKENS_ARCHIVISTA,
    MAX_TOKENS_ATTORE,
    TEMPERATURA_ARCHIVISTA,
    TEMPERATURA_ATTORE,
)


class ErroreLMStudio(RuntimeError):
    """Errore di comunicazione con LM Studio, con messaggio in italiano."""


MessaggioAvvio = (
    "Non riesco a contattare LM Studio su " + BASE_URL + ". "
    "Apri LM Studio, carica un modello e avvia il server locale "
    "(scheda Developer → Start Server)."
)


def attivo(timeout=3):
    """True se il server locale di LM Studio risponde."""
    try:
        requests.get(f"{BASE_URL}/models", timeout=timeout)
        return True
    except requests.RequestException:
        return False


def modello_attivo():
    """Recupera il modello attualmente caricato in LM Studio.

    Come faceva get_model() nel vecchio LocalStoryEngine: prende il primo
    modello tra quelli caricati. Solleva ErroreLMStudio se il server non
    risponde o se non c'è nessun modello caricato.
    """
    try:
        risposta = requests.get(f"{BASE_URL}/models", timeout=10)
        risposta.raise_for_status()
        modelli = risposta.json().get("data", [])
    except requests.RequestException as errore:
        raise ErroreLMStudio(MessaggioAvvio) from errore
    except ValueError as errore:
        raise ErroreLMStudio("LM Studio ha risposto in un formato inatteso.") from errore
    if not modelli:
        raise ErroreLMStudio(
            "Nessun modello caricato in LM Studio: scaricane uno, caricalo "
            "e assicurati che il server locale sia avviato."
        )
    return modelli[0]["id"]


def _scegli_modello(modello):
    """Usa il modello richiesto, oppure quello caricato in LM Studio."""
    if modello and modello.strip():
        return modello.strip()
    return modello_attivo()


def _errore_richiesta(errore):
    """Traduce le eccezioni di requests in messaggi comprensibili."""
    if isinstance(errore, requests.HTTPError) and errore.response is not None:
        dettaglio = ""
        try:
            corpo = errore.response.json()
            if isinstance(corpo.get("error"), dict):
                dettaglio = corpo["error"].get("message", "")
            elif isinstance(corpo.get("error"), str):
                dettaglio = corpo["error"]
        except ValueError:
            pass
        if dettaglio:
            return ErroreLMStudio("LM Studio ha rifiutato la richiesta: " + dettaglio)
        return ErroreLMStudio(
            "LM Studio ha rifiutato la richiesta "
            f"(errore {errore.response.status_code})."
        )
    return ErroreLMStudio(f"Errore di comunicazione con LM Studio: {errore}")


def _corpo(messaggi, modello, temperatura, max_tokens, stream=False):
    return {
        "model": modello,
        "messages": messaggi,
        "temperature": temperatura,
        "max_tokens": max_tokens,
        "stream": stream,
    }


def chat(
    messaggi,
    modello="",
    temperatura=TEMPERATURA_ARCHIVISTA,
    max_tokens=MAX_TOKENS_ARCHIVISTA,
):
    """Invia la conversazione e restituisce la risposta completa."""
    try:
        risposta = requests.post(
            f"{BASE_URL}/chat/completions",
            json=_corpo(messaggi, _scegli_modello(modello), temperatura, max_tokens),
            timeout=600,
        )
        risposta.raise_for_status()
    except requests.RequestException as errore:
        raise _errore_richiesta(errore) from errore

    try:
        return risposta.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as errore:
        raise ErroreLMStudio("LM Studio ha risposto in un formato inatteso.") from errore


def stream_pezzi(
    messaggi,
    modello="",
    temperatura=TEMPERATURA_ATTORE,
    max_tokens=MAX_TOKENS_ATTORE,
):
    """Generatore che restituisce la risposta a pezzi, mentre l'IA scrive."""
    try:
        risposta = requests.post(
            f"{BASE_URL}/chat/completions",
            json=_corpo(
                messaggi, _scegli_modello(modello), temperatura, max_tokens, stream=True
            ),
            stream=True,
            timeout=600,
        )
        risposta.raise_for_status()
    except requests.RequestException as errore:
        raise _errore_richiesta(errore) from errore

    try:
        for riga in risposta.iter_lines():
            if not riga:
                continue
            testo = riga.decode("utf-8").strip()
            # Le righe che iniziano con ":" sono commenti di tenuta connessione.
            if not testo.startswith("data:"):
                continue
            dati = testo[len("data:"):].strip()
            if dati == "[DONE]":
                break
            blocco = json.loads(dati)
            scelte = blocco.get("choices") or [{}]
            pezzo = (scelte[0].get("delta") or {}).get("content", "")
            if pezzo:
                yield pezzo
    except (json.JSONDecodeError, UnicodeDecodeError) as errore:
        raise ErroreLMStudio("Lo streaming di LM Studio si è interrotto.") from errore
