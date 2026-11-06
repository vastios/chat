"""La regia: canale di servizio tra te e la macchina.

Qui non si gioca: è la linea diretta per tutto ciò che sta fuori dal
personaggio — far arrivare un nuovo PNG in scena, segnare che qualcuno
esce dal dialogo, farsi proporre aggiornamenti della memoria (che l'utente
conferma sempre prima del salvataggio) e le altre comunicazioni di servizio.

La macchina risponde con un oggetto JSON:
- "crea_png"         → l'app genera il personaggio e lo aggiunge all'archivio
- "aggiorna_memoria" → l'app mostra la proposta e la applica solo dopo conferma
- "nessuna"          → semplice risposta di servizio

Se il modello risponde senza JSON, il testo grezzo diventa la risposta:
la regia non deve mai bloccare l'app.
"""

from personaggi import memoria, personaggio
from personaggi.lmstudio import chat
from config import MAX_TOKENS_REGIA, MODELLO_REGIA, PROMPT_REGIA, TEMPERATURA_REGIA


def costruisci_contesto(scheda, memoria_dati, nomi_png):
    """Riunisce le informazioni di scena che la regia deve conoscere."""
    memoria_dati = memoria.normalizza_memoria(memoria_dati)
    return {
        "nome": scheda.get("nome", "Personaggio"),
        "umore": memoria_dati["umore"] or "non registrato",
        "situazione": memoria_dati["situazione"] or "non registrata",
        "fiducia": str(memoria_dati["relazione"]["fiducia"]),
        "elenco_png": ", ".join(nomi_png) if nomi_png else "nessuno",
    }


def interpreta(testo_utente, scheda, memoria_dati, nomi_png):
    """Invia una richiesta di servizio alla macchina.

    Restituisce la coppia (messaggio, azione): la frase breve da mostrare
    all'utente e il dizionario con le chiavi azione / descrizione_png /
    attiva_png / modifiche. Solleva ErroreLMStudio se il server non risponde.
    """
    richiesta = [
        {
            "role": "system",
            "content": PROMPT_REGIA.format(
                **costruisci_contesto(scheda, memoria_dati, nomi_png)
            ),
        },
        {"role": "user", "content": str(testo_utente).strip()},
    ]
    risposta = chat(
        richiesta,
        modello=MODELLO_REGIA,
        temperatura=TEMPERATURA_REGIA,
        max_tokens=MAX_TOKENS_REGIA,
    )
    return analizza_risposta(risposta)


def analizza_risposta(risposta):
    """Trasforma la risposta della macchina in (messaggio, azione) affidabile."""
    dati = personaggio.estrai_json(risposta)
    if not isinstance(dati, dict):
        testo = " ".join(str(risposta or "").split())
        return (
            testo or "Non ho capito la richiesta: prova a riformularla.",
            {"azione": "nessuna", "descrizione_png": "", "attiva_png": False, "modifiche": {}},
        )

    messaggio = " ".join(str(dati.get("messaggio", "")).split()) or "Fatto."
    tipo = str(dati.get("azione", "nessuna")).strip()
    if tipo not in ("crea_png", "aggiorna_memoria"):
        tipo = "nessuna"
    modifiche = dati.get("modifiche")
    azione = {
        "azione": tipo,
        "descrizione_png": str(dati.get("descrizione_png", "") or "").strip(),
        "attiva_png": bool(dati.get("attiva_png", False)),
        "modifiche": modifiche if isinstance(modifiche, dict) else {},
    }
    return messaggio, azione
