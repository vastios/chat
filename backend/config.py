# -*- coding: utf-8 -*-
"""Configurazione centrale dell'applicazione.

Tutti i valori possono essere sovrascritti con variabili d'ambiente,
esempio:  set MODELLO_ATTORE=qwen2.5:3b-instruct-q4_K_M  (cmd)
          $env:MODELLO_ATTORE="qwen2.5:3b-instruct-q4_K_M"  (PowerShell)
"""
from __future__ import annotations

import os
from pathlib import Path

# Cartella base del progetto (una sopra "backend")
BASE_DIR = Path(__file__).resolve().parent.parent

# Cartella dove vivono le storie (world state + messaggi)
CARTELLA_DATI = BASE_DIR / "dati" / "storie"

# --- Ollama -----------------------------------------------------------------
URL_OLLAMA = os.environ.get("URL_OLLAMA", "http://localhost:11434")

# Modello "attore": recita i personaggi in chat.
# 7B quantizzato Q4_K_M ~ 4,7 GB di RAM: ideale per 16 GB senza GPU.
MODELLO_ATTORE = os.environ.get("MODELLO_ATTORE", "qwen2.5:7b-instruct-q4_K_M")

# Modello "archivista": aggiorna la memoria JSON in background.
# Un 3B basta e rende l'aggiornamento più rapido (~2 GB di RAM).
MODELLO_ARCHIVISTA = os.environ.get("MODELLO_ARCHIVISTA", "qwen2.5:3b-instruct-q4_K_M")

# --- Generazione ------------------------------------------------------------
NUM_CTX = int(os.environ.get("NUM_CTX", "4096"))      # finestra di contesto
TEMP_ATTORE = float(os.environ.get("TEMP_ATTORE", "0.85"))
TEMP_ARCHIVISTA = float(os.environ.get("TEMP_ARCHIVISTA", "0.2"))
NUM_PREDICT_ATTORE = int(os.environ.get("NUM_PREDICT_ATTORE", "450"))
NUM_PREDICT_ARCHIVISTA = int(os.environ.get("NUM_PREDICT_ARCHIVISTA", "900"))

# --- Comportamento ----------------------------------------------------------
PORTA = int(os.environ.get("PORTA", "7860"))

# L'archivista parte dopo ogni N messaggi dell'assistente (1 = ogni scambio).
# Su macchine molto lente alza questo valore (es. 2 o 3).
ARCHIVISTA_OGNI_N = int(os.environ.get("ARCHIVISTA_OGNI_N", "1"))
ARCHIVISTA_ATTIVO = os.environ.get("ARCHIVISTA_ATTIVO", "1") == "1"

# Quanti messaggi recenti entrano nel prompt dell'attore
MESSAGGI_CONTESTO = int(os.environ.get("MESSAGGI_CONTESTO", "12"))

# Versioni massime conservate in dati/storie/<storia>/history/
MAX_VERSIONI_HISTORY = int(os.environ.get("MAX_VERSIONI_HISTORY", "50"))
