# -*- coding: utf-8 -*-
"""Il modello "archivista": aggiorna la memoria JSON in background.

Dopo ogni scambio di chat, riceve lo stato attuale (compatto) e gli ultimi
messaggi, e risponde SOLO con un oggetto JSON di OPERAZIONI chirurgiche
(es. aggiorna il campo 'stato_animo' di Sofia, aggiunge un evento...).

Robustezza:
- Ollama viene chiamato con format="json" (output JSON garantito).
- Il JSON viene validato con Pydantic; operazioni con campi inventati
  vengono scartate dal gestore, senza mai corrompere la memoria.
- Se il JSON non è interpretabile, si riprova una volta, poi si scarta.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from backend import config, ollama_client
from backend.memoria import gestore
from backend.memoria.modelli import PacchettoOperazioni

log = logging.getLogger("archivista")

ISTRUZIONI = """Sei l'ARCHIVISTA di una storia interattiva in italiano. Il tuo unico compito è
aggiornare la memoria della storia in base a ciò che è appena successo nella chat.

Ti fornisco:
1. La memoria attuale (JSON con storia, personaggi, luoghi, eventi, scena).
2. Gli ultimi scambi di chat (l'utente è il protagonista).

Devi restituire SOLO un oggetto JSON, senza testo fuori dal JSON, con questa struttura:
{
  "operazioni": [
    {"tipo": "aggiorna_personaggio", "id": "id_personaggio", "campi": {"stato_animo": "...", "fatti_chiave": ["..."]}},
    {"tipo": "aggiungi_personaggio", "campi": {"nome": "...", "descrizione": "...", "personalita": "..."}},
    {"tipo": "aggiorna_luogo", "id": "id_luogo", "campi": {"descrizione": "..."}},
    {"tipo": "aggiungi_luogo", "campi": {"nome": "...", "descrizione": "..."}},
    {"tipo": "aggiorna_evento", "id": "id_evento", "campi": {"stato": "passato|in_corso|pianificato", "conseguenze": ["..."]}},
    {"tipo": "aggiungi_evento", "campi": {"titolo": "...", "descrizione": "...", "stato": "in_corso"}},
    {"tipo": "aggiorna_scena", "campi": {"luogo": "nome_luogo", "presente": ["id_personaggio"], "situazione": "..."}}
  ],
  "nota": "breve frase in italiano che spiega le modifiche, es. 'Sofia ora è diffidente: ha scoperto che...'"
}

CAMPI DISPONIBILI:
- personaggio: nome, descrizione, personalita, aspetto, stato_animo, relazioni (dizionario nome→rapporto), fatti_chiave (lista)
- luogo: nome, descrizione, atmosfera
- evento: titolo, descrizione, stato (passato|in_corso|pianificato), conseguenze (lista)
- scena: luogo (nome del luogo), presente (lista id/nomi), situazione

REGOLE:
- Registra SOLO informazioni nuove o cambiate rispetto alla memoria attuale: fatti importanti
  rivelati, cambi di umore, nuovi personaggi citati, spostamenti di luogo, eventi rilevanti.
- Per aggiornare usa SOLO i campi necessari: il resto resta invariato.
- Non cancellare mai informazioni; correggile solo se la chat le contraddice esplicitamente.
- Se gli scambi sono banali (saluti, chiacchiere senza conseguenze), rispondi
  {"operazioni": [], "nota": ""}.
- Non inventare fatti che non emergono dalla chat.
"""


def stato_compatto(stato) -> str:
    """Versione compatta del world state per il prompt dell'archivista."""
    p = []
    for per in stato.personaggi:
        p.append({
            "id": per.id, "nome": per.nome,
            "descrizione": per.descrizione[:200],
            "personalita": per.personalita[:150],
            "stato_animo": per.stato_animo,
            "relazioni": per.relazioni,
            "fatti_chiave": per.fatti_chiave[-5:],
        })
    l = [{"id": x.id, "nome": x.nome, "descrizione": x.descrizione[:120]} for x in stato.luoghi]
    e = [{"id": x.id, "titolo": x.titolo, "stato": x.stato, "descrizione": x.descrizione[:120]} for x in stato.eventi]
    sc = {"luogo": stato.scena.luogo, "presente": stato.scena.presente,
          "situazione": stato.scena.situazione}
    return json.dumps({
        "storia": {"nome": stato.storia.nome, "premessa": stato.storia.premessa[:200],
                   "tono": stato.storia.tono},
        "personaggi": p, "luoghi": l, "eventi": e, "scena": sc,
    }, ensure_ascii=False)


def _estrai_json(testo: str) -> Optional[dict]:
    """Prova a interpretare la risposta come JSON, con ripiego sul primo blocco {...}."""
    try:
        return json.loads(testo)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", testo, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _chiama_archivista(sid: str, scambio_utente: str, scambio_modello: str,
                       interlocutore: str) -> Optional[PacchettoOperazioni]:
    stato = gestore.carica_stato(sid)
    recenti = gestore.carica_messaggi(sid)[-6:-1]  # scambi immediatamente precedenti
    cron = "\n".join(f"{m.get('nome') or m.get('ruolo')}: {m.get('testo','')}" for m in recenti)

    prompt = (
        f"MEMORIA ATTUALE:\n{stato_compatto(stato)}\n\n"
        f"SCAMBI PRECEDENTI:\n{cron or '(inizio della conversazione)'}\n\n"
        f"ULTIMO SCAMBIO:\n"
        f"Utente: {scambio_utente}\n"
        f"{interlocutore}: {scambio_modello}\n\n"
        f"Restituisci SOLO il JSON per aggiornare la memoria."
    )
    messaggi = [
        {"role": "system", "content": ISTRUZIONI},
        {"role": "user", "content": prompt},
    ]

    for tentativo in (1, 2):
        testo = ollama_client.chat(
            messaggi=messaggi,
            modello=config.MODELLO_ARCHIVISTA,
            temperatura=config.TEMP_ARCHIVISTA,
            formato="json",
            num_predict=config.NUM_PREDICT_ARCHIVISTA,
        )
        dati = _estrai_json(testo)
        if dati is not None:
            try:
                return PacchettoOperazioni.model_validate(dati)
            except Exception:
                log.warning("JSON archivista non valido al tentativo %s", tentativo)
        log.warning("Risposta archivista non interpretabile (tentativo %s)", tentativo)
    return None


def aggiorna_memoria(sid: str, scambio_utente: str, scambio_modello: str,
                     interlocutore: str) -> dict:
    """Esegue il ciclo completo: analizza → valida → applica → registra.
    Chiamata in un thread separato dal server web."""
    try:
        pacchetto = _chiama_archivista(sid, scambio_utente, scambio_modello, interlocutore)
        if pacchetto is None:
            return {"ok": False, "msg": "L'archivista non ha prodotto aggiornamenti validi."}
        if not pacchetto.operazioni:
            gestore._registra_log(sid, ["(nessuna modifica necessaria)"], [])
            return {"ok": True, "msg": "", "nota": ""}
        risultato = gestore.applica_operazioni(sid, pacchetto.operazioni, nota=pacchetto.nota)
        nota = pacchetto.nota or "Memoria aggiornata."
        return {"ok": True, "riepilogo": risultato["riepilogo"],
                "scartate": risultato["scartate"], "nota": nota}
    except ollama_client.ErroreOllama as e:
        log.error("Archivista: %s", e)
        return {"ok": False, "msg": str(e)}
    except FileNotFoundError as e:
        log.error("Archivista: %s", e)
        return {"ok": False, "msg": str(e)}
    except Exception as e:  # mai far morire il thread in silenzio
        log.exception("Errore inatteso dell'archivista")
        return {"ok": False, "msg": f"Errore inatteso: {e}"}
