# -*- coding: utf-8 -*-
"""Il modello "attore": recita i personaggi (o il narratore) nella chat.

Il prompt di sistema contiene SOLO lo stato rilevante:
premessa, tono, scena corrente, personaggio interpretato, pochi fatti chiave.
Il world state completo resta all'archivista — così il contesto resta leggero.
"""
from __future__ import annotations

from typing import Generator

from backend import config, ollama_client
from backend.memoria import gestore
from backend.memoria.modelli import Personaggio, StatoDelMondo

NARRATORE = "Narratore"


def _scheda_personaggio(p: Personaggio, interlocutore: str) -> str:
    righe = [
        f"- Nome: {p.nome}",
        f"- Chi è: {p.descrizione or 'non specificato'}",
        f"- Carattere: {p.personalita or 'non specificato'}",
    ]
    if p.aspetto:
        righe.append(f"- Aspetto: {p.aspetto}")
    if p.stato_animo:
        righe.append(f"- Umore attuale: {p.stato_animo}")
    if p.relazioni:
        righe.append("- Relazioni:")
        for nome, rapporto in list(p.relazioni.items())[:6]:
            righe.append(f"    • {nome}: {rapporto}")
    if p.fatti_chiave:
        righe.append("- Fatti importanti che sa/successi:")
        for fatto in p.fatti_chiave[-5:]:
            righe.append(f"    • {fatto}")
    return "\n".join(righe)


def costruisci_prompt_sistema(stato: StatoDelMondo, interlocutore: str) -> str:
    s = stato.storia
    luoghi = {l.id: l for l in stato.luoghi}
    scena = stato.scena

    nome_luogo = luoghi[scena.luogo].nome if scena.luogo in luoghi else (scena.luogo or "non definito")
    desc_luogo = luoghi[scena.luogo].descrizione if scena.luogo in luoghi else ""
    presenti = [p.nome for p in stato.personaggi if p.id in scena.presente] or \
               [p.nome for p in stato.personaggi[:3]]

    intestazione = (
        f"AMBIENTAZIONE\n"
        f"- Storia: {s.nome}\n"
        f"- Premessa: {s.premessa or 'libera'}\n"
        f"- Tono da rispettare: {s.tono or 'realistico e vivace'}\n"
        f"- Luogo attuale: {nome_luogo}" + (f" — {desc_luogo}" if desc_luogo else "") + "\n"
        f"- Personaggi presenti: {', '.join(presenti)}\n"
        f"- Situazione: {scena.situazione or 'all\u2019inizio della storia'}\n"
    )

    if interlocutore == NARRATORE:
        ruolo = (
            "RUOLO\n"
            "Sei il NARRATORE di una storia interattiva. Guidi il racconto, descrivi le scene,\n"
            "fai agire e parlare i personaggi presenti. L'utente interpreta il protagonista.\n"
            "\nREGOLE (importanti)\n"
            "1. Rispondi sempre in ITALIANO, coerente con il tono della storia.\n"
            "2. Non agire e non parlare mai AL POSTO dell'utente: lascia sempre spazio alle sue azioni.\n"
            "3. Fai avanzare la scena: descrizioni brevi e suggestive, dialoghi vivaci dei personaggi.\n"
            "4. Restai coerente con i fatti della memoria qui sotto; non contraddirli mai.\n"
            "5. Risposta breve: massimo ~150 parole, niente elenchi puntati.\n"
            "6. Usa il corsivo tra *asterischi* per descrizioni e azioni.\n"
        )
        schede = "\nPERSONAGGI IN SCENA\n" + "\n\n".join(
            _scheda_personaggio(p, "utente") for p in stato.personaggi if p.id in scena.presente
        ) if scena.presente else ""
    else:
        p = next((x for x in stato.personaggi if x.id == interlocutore or x.nome == interlocutore), None)
        if p is None:
            nomi = ", ".join(x.nome for x in stato.personaggi) or "(nessuno)"
            raise ValueError(
                f"Personaggio '{interlocutore}' non trovato in questa storia. "
                f"Personaggi disponibili: {nomi}."
            )
        ruolo = (
            f"RUOLO\n"
            f"Sei {p.nome}. Interpreta {p.nome} e solo {p.nome}. L'utente è una persona che ti parla:\n"
            f"non interpretarla mai, non scrivere le sue battute né le sue azioni.\n"
            "\nREGOLE (importanti)\n"
            "1. Rispondi sempre in ITALIANO, con la voce e il carattere del personaggio.\n"
            "2. Restai sempre in scena: non uscire mai dal personaggio, non dire di essere un'IA.\n"
            "3. Risposta breve e naturale: da 2 a 6 frasi (max ~120 parole). Niente elenchi puntati.\n"
            "4. Usa il corsivo tra *asterischi* per gesti ed espressioni (es. *sorride soffuso*).\n"
            "5. Restai coerente con i fatti della memoria qui sotto; se l'utente introduce cose nuove,\n"
            "   reagisci in modo plausibile e lasciale alla memoria (l'archivista le registrerà).\n"
        )
        schede = "\nCHI SEI\n" + _scheda_personaggio(p, "utente")

    return intestazione + "\n" + ruolo + schede


def _cronologia_per_attore(messaggi: list[dict]) -> list[dict]:
    """Trasforma i messaggi salvati in formato chat user/assistant."""
    out = []
    for m in messaggi:
        testo = str(m.get("testo", "")).strip()
        if not testo:
            continue
        if m.get("ruolo") == "utente":
            out.append({"role": "user", "content": testo})
        else:
            nome = m.get("nome") or "personaggio"
            out.append({"role": "assistant", "content": f"{nome}: {testo}"})
    return out


def genera_risposta(sid: str, interlocutore: str, testo_utente: str) -> Generator[str, None, None]:
    """Genera in streaming la risposta dell'attore (pezzi di testo)."""
    stato = gestore.carica_stato(sid)
    recenti = gestore.carica_messaggi(sid)[-config.MESSAGGI_CONTESTO:]

    messaggi = [{"role": "system", "content": costruisci_prompt_sistema(stato, interlocutore)}]
    messaggi.extend(_cronologia_per_attore(recenti[:-1]))  # esclude l'ultimo (già quello nuovo)
    messaggi.append({"role": "user", "content": testo_utente})

    risposta = ollama_client.chat(
        messaggi=messaggi,
        modello=config.MODELLO_ATTORE,
        temperatura=config.TEMP_ATTORE,
        stream=True,
        num_predict=config.NUM_PREDICT_ATTORE,
    )
    yield from ollama_client.stream_pezzi(risposta)
