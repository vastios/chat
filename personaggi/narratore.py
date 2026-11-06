"""Il narratore: dà voce al personaggio.

Fa ciò che nel vecchio LocalStoryEngine faceva game/narrator.py: costruisce
il prompt di sistema unendo il prompt base, la scheda canonica e la memoria,
poi chiama il modello e restituisce la risposta in streaming.

Rispetto al vecchio progetto le regole di continuità sono generalizzate:
niente più frasi hardcodate su un PNG specifico, tutto passa dalla scheda
e dalla memoria del personaggio corrente.
"""

from personaggi import memoria as modulo_memoria
from personaggi import ollama, personaggio
from config import (
    LIMITE_FIDUCIA_SEGRETO,
    MAX_PAROLE_RISPOSTA,
    MESSAGGI_CONTESTO,
    MODELLO_ATTORE,
    PROMPT_ATTORE,
    TEMPERATURA_ATTORE,
)


def costruisci_prompt_sistema(scheda, memoria, nome_utente=""):
    """Unisce prompt base, scheda canonica, memoria e regole di continuità."""
    nome = scheda.get("nome", "Personaggio")
    righe = {
        "nome": nome,
        "scheda": personaggio.formatta_scheda(scheda, nome),
        "memoria": modulo_memoria.formatta_per_contesto(memoria, nome_utente),
        "max_parole": str(MAX_PAROLE_RISPOSTA),
        "limite_segreto": str(LIMITE_FIDUCIA_SEGRETO),
    }
    prompt = PROMPT_ATTORE.format(**righe)
    return prompt


def messaggi_per_modello(scheda, memoria, conversazione, nome_utente=""):
    """Cronologia recente nel formato che Ollama si aspetta."""
    messaggi = [{
        "role": "system",
        "content": costruisci_prompt_sistema(scheda, memoria, nome_utente),
    }]
    for voce in conversazione.get("messaggi", [])[-MESSAGGI_CONTESTO:]:
        ruolo = "user" if voce.get("ruolo") == "utente" else "assistant"
        testo = (voce.get("testo") or "").strip()
        if testo:
            messaggi.append({"role": ruolo, "content": testo})
    return messaggi


def genera_risposta(scheda, memoria, conversazione, nome_utente=""):
    """Generatore: restituisce la risposta del personaggio a pezzi."""
    messaggi = messaggi_per_modello(scheda, memoria, conversazione, nome_utente)
    yield from ollama.stream_pezzi(
        messaggi,
        modello=MODELLO_ATTORE,
        temperatura=TEMPERATURA_ATTORE,
    )
