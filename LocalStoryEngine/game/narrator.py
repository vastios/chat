"""Comunicazione con LM Studio e contesto persistente dei PNG."""

import requests

from config import BASE_URL, SYSTEM_PROMPT
from game.npcs import get_npc, list_npcs


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


def _format_npc_context():
    """Prepara un riepilogo canonico dei PNG e dei ricordi già salvati."""
    npcs = list_npcs()
    if not npcs:
        return (
            "ARCHIVIO PNG\n"
            "Non ci sono PNG registrati nell'archivio. "
            "Non inventare PNG già esistenti come se fossero salvati."
        )

    sections = [
        "ARCHIVIO CANONICO DEI PNG",
        "Queste informazioni provengono dal salvataggio. Rispetta identità, "
        "passato, obiettivi e segreti registrati. Un segreto non va rivelato "
        "automaticamente agli altri personaggi. Un PNG conosce solo le "
        "informazioni della sua scheda e i ricordi registrati.",
    ]

    for summary in npcs:
        npc = get_npc(summary["id"])
        if not npc:
            continue
        sections.append(
            f"\nPNG: {npc['name']} (ID {npc['id']})\n"
            f"Luogo registrato: {npc.get('location') or 'Non definito'}\n"
            f"Origine: {npc.get('origin_type', 'non definita')}\n"
            f"Situazione attuale: {npc.get('current_status') or 'Non definita'}"
        )
        for field, value in (npc.get("identity") or {}).items():
            if value is not None and str(value).strip():
                sections.append(f"{field.capitalize()}: {value}")

        relationship = npc.get("relationship")
        if relationship:
            sections.append(
                "Rapporto con il protagonista: fiducia "
                f"{relationship.get('trust', 0)}/100."
            )
            notes = relationship.get("relationship_notes", "")
            if notes:
                sections.append(f"Note sulla relazione: {notes}")

        memories = npc.get("memories") or []
        if memories:
            sections.append("RICORDI REGISTRATI:")
            for memory in memories:
                sections.append(
                    f"- [Importanza {memory.get('importance', 1)}/5] "
                    f"{memory.get('memory_text', '')}"
                )
        else:
            sections.append(
                "RICORDI REGISTRATI: nessun ricordo salvato finora. "
                "Non fingere che esistano ricordi precedenti."
            )
    return "\n".join(sections)


def generate_response(messages, state_context="", max_tokens=500):
    """Invia a LM Studio la conversazione, lo stato e l'archivio PNG."""
    model = get_model()
    system_content = SYSTEM_PROMPT
    if state_context:
        system_content += "\n\n" + state_context

    # Rilegge i PNG a ogni risposta: le modifiche salvate sono subito disponibili.
    system_content += "\n\n" + _format_npc_context()
    system_content += """

REGOLE VINCOLANTI DI CONTINUITÀ NARRATIVA
- L'archivio canonico dei PNG è la fonte di verità per la loro identità.
- I tratti fisici esplicitamente registrati sono immutabili, salvo un evento
  narrativo esplicito che ne giustifichi il cambiamento.
- Mira ha capelli castani raccolti e occhi color nocciola.
- Mira indossa un grembiule di cuoio sopra una semplice veste da locandiera.
- Non descrivere Mira con capelli grigi, occhi di altro colore o altri tratti
  fisici incompatibili con la sua scheda.
- Non inventare dettagli mancanti come se fossero fatti canonici.
- Rispetta personalità, storia, obiettivi, segreti e conoscenze dei PNG.
- Non confondere voci, ipotesi e fatti conosciuti personalmente.
- Non dichiarare avvenuti eventi o cambiamenti non registrati dal gioco.
- Non affermare di aver salvato ricordi o modificato relazioni senza averlo fatto.
- Se non conosci un dettaglio, omettilo invece di inventarlo.
"""

    conversation = [
        {"role": "system", "content": system_content},
        *messages,
    ]
    response = requests.post(
        f"{BASE_URL}/chat/completions",
        json={
            "model": model,
            "messages": conversation,
            "temperature": 0.3,
            "max_tokens": max_tokens,
        },
        timeout=240,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]
