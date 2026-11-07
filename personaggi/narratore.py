"""Il narratore: dà voce ai personaggi.

Fa ciò che nel vecchio LocalStoryEngine faceva game/narrator.py: costruisce
il prompt di sistema unendo il prompt base, la scheda canonica e la memoria,
poi chiama il modello e restituisce la risposta in streaming.

Con più PNG in scena usa un prompt di scena: il modello scrive le battute
di tutti, ognuna preceduta dal nome ("Marco: ..."), e l'app le attribuisce
al personaggio giusto (colore e bolla).

Rispetto al vecchio progetto le regole di continuità sono generalizzate:
niente più frasi hardcodate su un PNG specifico, tutto passa dalla scheda
e dalla memoria del personaggio corrente.
"""

from personaggi import lmstudio, personaggio
from personaggi import memoria as modulo_memoria
from config import (
    LIMITE_FIDUCIA_SEGRETO,
    MAX_PAROLE_RISPOSTA,
    MAX_TOKENS_ATTORE,
    MESSAGGI_CONTESTO,
    MODELLO_ATTORE,
    PROMPT_ATTORE,
    PROMPT_ATTORE_SCENA,
    TEMPERATURA_ATTORE,
)

import re

# Una battuta di scena inizia con il nome del personaggio e i due punti:
# "Marco: Ciao!", "**Sofia:** *sorride*" — il nome può stare in grassetto,
# con i due punti dentro o fuori dal grassetto.
_MOTIVO_BATTUTA = re.compile(r"^\s*(?:\*\*)?\s*([^:*]{1,40}?)\s*(?:\*\*)?\s*:\s*(.*)$")
_MOTIVO_GRASSETTO_RESIDUO = re.compile(r"^\*\*\s*")


def spezza_risposta(testo, scena, chi_proprietario):
    """Divide la risposta del modello in battute (chi, testo) per personaggio.

    Riconosce le righe che iniziano con 'Nome:' (anche in grassetto): ogni
    battuta nuova prende il colore e l'autore di quel PNG. Le righe senza
    nome continuano la battuta aperta; se non compare nessun nome, tutto
    resta al protagonista.
    """
    per_nome = {voce["nome"].strip().lower(): voce["id"] for voce in scena}
    battute = []
    chi = chi_proprietario
    righe = []
    for riga in (testo or "").splitlines():
        incontro = _MOTIVO_BATTUTA.match(riga)
        if incontro:
            nome_trovato = incontro.group(1).strip().lower()
            if nome_trovato in per_nome:
                if righe and "\n".join(righe).strip():
                    battute.append((chi, "\n".join(righe).strip()))
                    righe = []
                chi = per_nome[nome_trovato]
                # Se i due punti stavano dentro il grassetto ("**Sofia:** testo")
                # resta un residuo di asterischi davanti al testo: tolto solo lui,
                # mai gli asterischi singoli delle azioni.
                riga = _MOTIVO_GRASSETTO_RESIDUO.sub("", incontro.group(2), count=1)
        righe.append(riga)
    if righe and "\n".join(righe).strip():
        battute.append((chi, "\n".join(righe).strip()))
    return battute


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
    """Cronologia recente nel formato OpenAI che LM Studio si aspetta."""
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


# ---------------------------------------------------------------------------
# Scena con più personaggi
# ---------------------------------------------------------------------------

def nome_di(id_png, schede_scena, nomi_extra=None):
    """Il nome di un PNG a partire dall'id: prima le schede in scena, poi
    la mappa d'appoggio (serve per i vecchi messaggi)."""
    for scheda_voce in schede_scena:
        if scheda_voce.get("id") == id_png or scheda_voce.get("nome", "").lower() == str(id_png).lower():
            return scheda_voce.get("nome", "")
    return (nomi_extra or {}).get(id_png, "")


def costruisci_prompt_scena(scheda_proprietario, schede_scena, memoria, nome_utente=""):
    """Prompt di scena: tutte le schede in scena più la memoria del protagonista."""
    blocchi = []
    for scheda_voce in schede_scena:
        nome_voce = scheda_voce.get("nome", "Personaggio")
        marca = " (protagonista)" if scheda_voce.get("id") == scheda_proprietario.get("id") else ""
        blocchi.append(f"— {nome_voce}{marca} —\n{personaggio.formatta_scheda(scheda_voce, nome_voce)}")
    righe = {
        "nome": scheda_proprietario.get("nome", "Personaggio"),
        "schede": "\n\n".join(blocchi),
        "memoria": modulo_memoria.formatta_per_contesto(memoria, nome_utente),
        "max_parole": str(MAX_PAROLE_RISPOSTA),
    }
    return PROMPT_ATTORE_SCENA.format(**righe)


def messaggi_per_modello_scena(scheda_proprietario, schede_scena, memoria,
                               conversazione, nome_utente="", nomi_extra=None):
    """Cronologia nel formato OpenAI per la scena multi-PNG.

    Le battute dei personaggi arrivano al modello con il nome davanti
    ("Marco: ..."), così resta chiaro chi ha detto cosa e il modello
    impara il formato di risposta atteso.
    """
    nome_proprietario = scheda_proprietario.get("nome", "Personaggio")
    messaggi = [{
        "role": "system",
        "content": costruisci_prompt_scena(
            scheda_proprietario, schede_scena, memoria, nome_utente
        ),
    }]
    for voce in conversazione.get("messaggi", [])[-MESSAGGI_CONTESTO:]:
        testo = (voce.get("testo") or "").strip()
        if not testo:
            continue
        if voce.get("ruolo") == "utente":
            messaggi.append({"role": "user", "content": testo})
            continue
        chi = voce.get("chi") or ""
        nome = voce.get("nome_png") or nome_di(chi, schede_scena, nomi_extra) or nome_proprietario
        messaggi.append({"role": "assistant", "content": f"{nome}: {testo}"})
    return messaggi


def genera_risposta(scheda, memoria, conversazione, nome_utente="",
                    scena=None, schede_scena=None, nomi_extra=None):
    """Generatore: restituisce la risposta a pezzi.

    Con `scena` di un solo personaggio (o None) vale il prompt classico;
    con più PNG in scena si usa il prompt di scena e il modello scrive
    le battute di tutti, una per riga, con il nome davanti.
    """
    if schede_scena and len(schede_scena) > 1:
        messaggi = messaggi_per_modello_scena(
            scheda, schede_scena, memoria, conversazione, nome_utente, nomi_extra
        )
    else:
        messaggi = messaggi_per_modello(scheda, memoria, conversazione, nome_utente)
    yield from lmstudio.stream_pezzi(
        messaggi,
        modello=MODELLO_ATTORE,
        temperatura=TEMPERATURA_ATTORE,
        max_tokens=MAX_TOKENS_ATTORE,
    )
