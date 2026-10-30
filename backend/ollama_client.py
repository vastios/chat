# -*- coding: utf-8 -*-
"""Client per l'API locale di Ollama (http://localhost:11434)."""
from __future__ import annotations

import json
from typing import Generator, Optional

import requests

from backend.config import NUM_CTX, URL_OLLAMA


class ErroreOllama(Exception):
    """Errore chiaro da mostrare all'utente in italiano."""


def ollama_attivo(timeout: float = 3.0) -> bool:
    try:
        requests.get(f"{URL_OLLAMA}/", timeout=timeout)
        return True
    except requests.RequestException:
        return False


def modelli_installati() -> list[str]:
    try:
        r = requests.get(f"{URL_OLLAMA}/api/tags", timeout=5)
        r.raise_for_status()
        return [m["name"] for m in r.json().get("models", [])]
    except requests.RequestException:
        return []


def chat(messaggi: list[dict], modello: str, temperatura: float = 0.7,
         stream: bool = False, num_ctx: int = NUM_CTX,
         formato: Optional[object] = None, num_predict: Optional[int] = None,
         timeout: int = 600):
    """Chiama /api/chat di Ollama. Con stream=True restituisce l'oggetto risposta
    da iterare con stream_pezzi(); altrimenti restituisce il testo completo."""
    payload = {
        "model": modello,
        "messages": messaggi,
        "stream": bool(stream),
        "options": {"temperature": temperatura, "num_ctx": num_ctx},
    }
    if formato is not None:
        payload["format"] = formato
    if num_predict:
        payload["options"]["num_predict"] = num_predict

    try:
        r = requests.post(f"{URL_OLLAMA}/api/chat", json=payload,
                          stream=bool(stream), timeout=timeout)
    except requests.ConnectionError:
        raise ErroreOllama(
            "Non riesco a contattare Ollama su " + URL_OLLAMA + ". "
            "Avvia Ollama (menu Start → Ollama) e riprova."
        )
    except requests.Timeout:
        raise ErroreOllama("Ollama ha impiegato troppo tempo a rispondere (timeout).")

    if r.status_code != 200:
        dettaglio = r.text[:300]
        if r.status_code == 404 and "not found" in dettaglio.lower():
            raise ErroreOllama(
                f"Il modello '{modello}' non è installato. Apri il Prompt dei comandi "
                f"ed esegui:  ollama pull {modello}"
            )
        raise ErroreOllama(f"Ollama ha risposto con errore {r.status_code}: {dettaglio}")
    return r


def stream_pezzi(risposta) -> Generator[str, None, None]:
    """Trasforma la risposta in streaming in pezzi di testo."""
    for riga in risposta.iter_lines():
        if not riga:
            continue
        try:
            dato = json.loads(riga.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        pezzo = dato.get("message", {}).get("content", "")
        if pezzo:
            yield pezzo
        if dato.get("done"):
            break
