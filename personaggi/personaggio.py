"""La scheda canonica del personaggio.

Riprende l'idea del vecchio LocalStoryEngine (game/npcs.py): ogni personaggio
ha un'identità fissa — aspetto, personalità, storia, obiettivo, segreto,
conoscenze — più il modo di parlare e un saluto d'apertura.

La scheda è la fonte della verità: il narratore non può contraddirla e solo
l'utente (o la creazione assistita) la modifica. La parte che invece cambia
durante la chat vive in memoria.py.
"""

import json
import re

from personaggi import lmstudio
from config import MODELLO_ATTORE, PROMPT_CREAZIONE


# I campi che compongono l'identità, nell'ordine con cui vengono mostrati.
CAMPI_SCHEDA = [
    ("aspetto", "Aspetto"),
    ("personalita", "Personalità"),
    ("storia", "Storia"),
    ("modo_di_parlare", "Modo di parlare"),
    ("obiettivo", "Obiettivo"),
    ("segreto", "Segreto"),
    ("conoscenze", "Conoscenze"),
]

CAMPI_AMMESSI = {campo for campo, _ in CAMPI_SCHEDA}


def scheda_predefinita():
    return {campo: "" for campo in CAMPI_AMMESSI}


def _pulisci(testo):
    return " ".join(str(testo or "").split())


def normalizza_scheda(dati):
    """Tiene solo i campi ammessi, come stringhe pulite."""
    if not isinstance(dati, dict):
        return scheda_predefinita()
    scheda = scheda_predefinita()
    for campo in CAMPI_AMMESSI:
        scheda[campo] = _pulisci(dati.get(campo, ""))
    return scheda


def valida_scheda(scheda):
    """Errori bloccanti per creare un personaggio sensato."""
    errori = []
    if not scheda.get("personalita"):
        errori.append("La personalità è obbligatoria: senza è solo un nome.")
    if not scheda.get("storia"):
        errori.append("La storia è obbligatoria: dà al personaggio un passato.")
    return errori


def formatta_scheda(scheda, nome=None):
    """Blocco di testo canonico da inserire nel prompt dell'attore."""
    nome = nome or scheda.get("nome", "Personaggio")
    righe = []
    for campo, etichetta in CAMPI_SCHEDA:
        valore = scheda.get(campo, "")
        if valore:
            righe.append(f"{etichetta}: {valore}")
    if not righe:
        righe.append("La scheda è vuota: definisci la personalità con i fatti emersi in chat.")
    return "\n".join(righe)


# ---------------------------------------------------------------------------
# Creazione assistita dall'IA
# ---------------------------------------------------------------------------

class ErroreCreazione(RuntimeError):
    """La generazione della scheda con l'IA non è andata a buon fine."""


def estrai_json(testo):
    """Estrae il primo oggetto JSON da una risposta, anche se ha testo attorno."""
    testo = (testo or "").strip()
    try:
        dati = json.loads(testo)
        if isinstance(dati, dict):
            return dati
    except json.JSONDecodeError:
        pass
    incontro = re.search(r"\{.*\}", testo, re.DOTALL)
    if incontro:
        try:
            dati = json.loads(incontro.group(0))
            if isinstance(dati, dict):
                return dati
        except json.JSONDecodeError:
            return None
    return None


def genera_scheda_con_ia(idea):
    """Da una breve idea dell'utente produce scheda completa, saluto e nome.

    Restituisce (nome, scheda_normalizzata, saluto).
    Solleva ErroreCreazione se l'IA non risponde con un JSON sensato.
    """
    richiesta = [
        {
            "role": "system",
            "content": (
                "Sei un creatore di personaggi per una chat di ruolo. "
                "Rispondi SOLO con un oggetto JSON, senza altro testo."
            ),
        },
        {
            "role": "user",
            "content": PROMPT_CREAZIONE.format(idea=idea.strip()),
        },
    ]

    ultimo_errore = ""
    for tentativo in range(3):
        risposta = lmstudio.chat(
            richiesta,
            modello=MODELLO_ATTORE,
            temperatura=0.7,
            max_tokens=800,
        )
        dati = estrai_json(risposta)
        if dati is None:
            ultimo_errore = "l'IA non ha restituito un JSON valido"
            continue

        nome = _pulisci(dati.get("nome", ""))
        saluto = _pulisci(dati.get("saluto", ""))
        scheda = normalizza_scheda(dati)
        errori = valida_scheda(scheda)
        if not nome:
            errori.append("Manca il nome del personaggio.")
        if errori:
            ultimo_errore = "; ".join(errori)
            # Un secondo tentativo spesso basta: l'IA corregge da sola.
            continue
        return nome, scheda, saluto

    raise ErroreCreazione(
        f"Non sono riuscito a creare la scheda ({ultimo_errore}). "
        "Prova a descrivere l'idea con qualche parola in più, o creala manualmente."
    )
