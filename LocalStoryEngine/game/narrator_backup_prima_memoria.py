"""Comunicazione con il server locale di LM Studio."""

import requests

from config import BASE_URL, SYSTEM_PROMPT


def get_model():
    """Recupera il modello attualmente disponibile in LM Studio."""
    response = requests.get(f"{BASE_URL}/models", timeout=10)
    response.raise_for_status()
    models = response.json().get("data", [])

    if not models:
        raise RuntimeError(
            "Nessun modello disponibile. Carica un modello in LM Studio."
        )

    return models[0]["id"]


def generate_response(messages, state_context="", max_tokens=500):
    """Invia la conversazione e il contesto del personaggio a LM Studio."""
    model = get_model()
    system_content = SYSTEM_PROMPT
    if state_context:
        system_content += "\n\n" + state_context

    conversation = [
        {"role": "system", "content": system_content},
        *messages,
    ]

    response = requests.post(
        f"{BASE_URL}/chat/completions",
        json={
            "model": model,
            "messages": conversation,
            "temperature": 0.8,
            "max_tokens": max_tokens,
        },
        timeout=240,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]
