"""Comunicazione con Ollama.

Nel vecchio LocalStoryEngine si parlava con LM Studio tramite l'API
OpenAI-compatibile. Qui si usa l'API nativa di Ollama, che supporta lo
streaming dei pezzi e l'output JSON forzato con "format": "json".
"""

import json
import requests

from config import NUM_CTX, OLLAMA_URL, TEMPERATURA_ARCHIVISTA, TEMPERATURA_ATTORE


class ErroreOllama(RuntimeError):
    """Errore di comunicazione con Ollama, con messaggio in italiano."""


def attivo(timeout=3):
    """True se il server Ollama risponde."""
    try:
        requests.get(f"{OLLAMA_URL}/api/version", timeout=timeout)
        return True
    except requests.RequestException:
        return False


def modelli_installati():
    """Elenca i modelli scaricati in Ollama."""
    try:
        risposta = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        risposta.raise_for_status()
    except requests.RequestException as errore:
        raise ErroreOllama(
            "Non riesco a contattare Ollama. Avvialo con il comando 'ollama serve' "
            "o aprendo l'applicazione Ollama."
        ) from errore
    return [m.get("name", "") for m in risposta.json().get("models", [])]


def _corpo(messaggi, modello, temperatura, formato=None):
    return {
        "model": modello,
        "messages": messaggi,
        "stream": False,
        "format": formato,
        "options": {
            "temperature": temperatura,
            "num_ctx": NUM_CTX,
        },
    }


def _errore_richiesta(errore, modello):
    if isinstance(errore, requests.HTTPError) and errore.response is not None and errore.response.status_code == 404:
        return ErroreOllama(
            f"Ollama non conosce il modello '{modello}'. "
            f"Scaricalo con:  ollama pull {modello}"
        )
    return ErroreOllama(f"Errore di comunicazione con Ollama: {errore}")


def chat(messaggi, modello, temperatura=TEMPERATURA_ARCHIVISTA, formato=None):
    """Invia la conversazione e restituisce la risposta completa."""
    try:
        risposta = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json=_corpo(messaggi, modello, temperatura, formato),
            timeout=600,
        )
        risposta.raise_for_status()
    except requests.RequestException as errore:
        raise _errore_richiesta(errore, modello) from errore

    try:
        return risposta.json()["message"]["content"]
    except (KeyError, ValueError) as errore:
        raise ErroreOllama("Ollama ha risposto in un formato inatteso.") from errore


def stream_pezzi(messaggi, modello, temperatura=TEMPERATURA_ATTORE):
    """Generatore che restituisce la risposta a pezzi, mentre l'IA scrive."""
    corpo = _corpo(messaggi, modello, temperatura)
    corpo["stream"] = True
    try:
        risposta = requests.post(
            f"{OLLAMA_URL}/api/chat", json=corpo, stream=True, timeout=600
        )
        risposta.raise_for_status()
    except requests.RequestException as errore:
        raise _errore_richiesta(errore, modello) from errore

    try:
        for riga in risposta.iter_lines():
            if not riga:
                continue
            blocco = json.loads(riga.decode("utf-8"))
            pezzo = blocco.get("message", {}).get("content", "")
            if pezzo:
                yield pezzo
    except (json.JSONDecodeError, UnicodeDecodeError) as errore:
        raise ErroreOllama("Lo streaming di Ollama si è interrotto.") from errore
