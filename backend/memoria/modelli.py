# -*- coding: utf-8 -*-
"""Modelli Pydantic del "world state": la memoria a lungo termine della storia.

Ogni storia è un unico file stato.json validato con questi modelli.
L'archivista (modello LLM in background) propone OPERAZIONI di modifica
chirurgica; qui vengono validate prima di toccare il disco.
"""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class Personaggio(BaseModel):
    id: str
    nome: str
    descrizione: str = ""          # chi è: età, ruolo, storia breve
    personalita: str = ""          # carattere, modo di parlare
    aspetto: str = ""              # come appare
    stato_animo: str = ""          # umore attuale (si evolve con la chat)
    relazioni: dict[str, str] = Field(default_factory=dict)  # nome → rapporto
    fatti_chiave: list[str] = Field(default_factory=list)    # cose successe/che sa


class Luogo(BaseModel):
    id: str
    nome: str
    descrizione: str = ""
    atmosfera: str = ""


class Evento(BaseModel):
    id: str
    titolo: str
    descrizione: str = ""
    stato: Literal["passato", "in_corso", "pianificato"] = "passato"
    conseguenze: list[str] = Field(default_factory=list)


class Scena(BaseModel):
    """Dove ci troviamo ORA e chi c'è: è ciò che entra nel prompt dell'attore."""
    luogo: str = ""                 # id del luogo corrente
    presente: list[str] = Field(default_factory=list)  # id dei personaggi presenti
    situazione: str = ""            # cosa sta succedendo in questo momento


class Storia(BaseModel):
    nome: str
    premessa: str = ""
    tono: str = ""                  # es. "realistico e intimista"


class StatoDelMondo(BaseModel):
    """Il file stato.json completo di una storia."""
    storia: Storia
    personaggi: list[Personaggio] = Field(default_factory=list)
    luoghi: list[Luogo] = Field(default_factory=list)
    eventi: list[Evento] = Field(default_factory=list)
    scena: Scena = Field(default_factory=Scena)
    versione: int = 1               # aumenta a ogni modifica salvata
    aggiornato_il: str = ""


# --- Operazioni proposte dall'archivista ------------------------------------

TipoOperazione = Literal[
    "aggiungi_personaggio", "aggiorna_personaggio",
    "aggiungi_luogo", "aggiorna_luogo",
    "aggiungi_evento", "aggiorna_evento",
    "aggiorna_scena",
]


class Operazione(BaseModel):
    """Una singola modifica chirurgica alla memoria.

    - aggiorna_*: id obbligatorio, campi = {nome_campo: nuovo_valore}
      (solo i campi forniti vengono modificati, il resto resta).
    - aggiungi_*: campi contiene l'intera entità (almeno "nome"/"titolo").
    - aggiorna_scena: campi = {luogo?, presente?, situazione?}.
    """
    tipo: TipoOperazione
    id: Optional[str] = None
    campi: dict = Field(default_factory=dict)


class PacchettoOperazioni(BaseModel):
    """La risposta JSON dell'archivista."""
    operazioni: list[Operazione] = Field(default_factory=list)
    nota: str = ""   # breve spiegazione in italiano, mostrata nella UI


# Campi modificabili per ogni tipo di entità (protezione da campi inventati)
CAMPI_CONSENTITI = {
    "personaggio": {"nome", "descrizione", "personalita", "aspetto",
                    "stato_animo", "relazioni", "fatti_chiave"},
    "luogo": {"nome", "descrizione", "atmosfera"},
    "evento": {"titolo", "descrizione", "stato", "conseguenze"},
    "scena": {"luogo", "presente", "situazione"},
}
