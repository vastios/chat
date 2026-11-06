"""Archivio su file JSON.

Questo modulo fa ciò che nel vecchio LocalStoryEngine faceva game/database.py
con SQLite: salva e carica personaggi, schede, memoria e conversazioni.
La differenza è che ogni personaggio ha una sua cartella di file JSON leggibili
a occhio nudo, che l'IA aggiorna in tempo reale durante la chat.

Struttura su disco:

    dati/
      personaggi.json                 <- indice di tutti i personaggi
      personaggi/
        <id>/
          scheda.json                 <- identità canonica (stabile)
          memoria.json                <- umore, situazione, relazione, ricordi
          conversazione.json          <- cronologia dei messaggi
          regia.json                  <- chat di servizio con la macchina
          log_memoria.jsonl           <- stato precedente a ogni modifica (per l'annulla)

Tutte le scritture sono atomiche: prima si scrive un file temporaneo e poi
viene rinominato, così un'interruzione non corrompe mai i dati.
"""

import json
import os
import re
import unicodedata
from datetime import datetime

from config import DATI_DIR, ELIMINATI_DIR, MAX_VOCI_LOG, PERSONAGGI_DIR


# ---------------------------------------------------------------------------
# Lettura e scrittura JSON di base
# ---------------------------------------------------------------------------

def _adesso():
    return datetime.now().isoformat(timespec="seconds")


def _leggi_json(percorso, predefinito):
    if not percorso.exists():
        return predefinito
    try:
        with open(percorso, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        # File danneggiato o letture concorrenti: meglio il predefinito che un crash.
        return predefinito


def _scrivi_json(percorso, dati):
    percorso.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = percorso.with_suffix(".json.tmp")
    with open(temporaneo, "w", encoding="utf-8") as file:
        json.dump(dati, file, ensure_ascii=False, indent=2)
    os.replace(temporaneo, percorso)


def _slug(testo):
    """Trasforma un nome in un identificatore corto e leggibile."""
    testo = unicodedata.normalize("NFKD", testo)
    testo = testo.encode("ascii", "ignore").decode("ascii")
    testo = re.sub(r"[^a-zA-Z0-9]+", "-", testo).strip("-").lower()
    return testo or "personaggio"


# ---------------------------------------------------------------------------
# Indice dei personaggi
# ---------------------------------------------------------------------------

def _percorso_indice():
    return DATI_DIR / "personaggi.json"


def inizializza_archivio():
    """Crea le cartelle e l'indice se non esistono, senza cancellare nulla."""
    PERSONAGGI_DIR.mkdir(parents=True, exist_ok=True)
    ELIMINATI_DIR.mkdir(parents=True, exist_ok=True)
    indice = _leggi_json(_percorso_indice(), None)
    if indice is None:
        _scrivi_json(_percorso_indice(), {"personaggi": []})


def leggi_indice():
    inizializza_archivio()
    return _leggi_json(_percorso_indice(), {"personaggi": []})


def _scrivi_indice(indice):
    _scrivi_json(_percorso_indice(), indice)


def lista_personaggi():
    """Restituisce i personaggi, dal più di recente aggiornato."""
    indice = leggi_indice()
    personaggi = sorted(
        indice.get("personaggi", []),
        key=lambda p: p.get("aggiornato_il", ""),
        reverse=True,
    )
    return personaggi


def trova_personaggio(id_personaggio):
    for personaggio in leggi_indice().get("personaggi", []):
        if personaggio.get("id") == id_personaggio:
            return personaggio
    return None


def _tocca_indice(id_personaggio):
    """Aggiorna 'aggiornato_il' del personaggio nell'indice."""
    indice = leggi_indice()
    for personaggio in indice.get("personaggi", []):
        if personaggio.get("id") == id_personaggio:
            personaggio["aggiornato_il"] = _adesso()
    _scrivi_indice(indice)


def id_libero(nome):
    """Costruisce un id univoco tipo 'sofia-a3f2' partendo dal nome."""
    base = _slug(nome)
    candidato = base
    numero = 0
    while True:
        if trova_personaggio(candidato) is None and not (PERSONAGGI_DIR / candidato).exists():
            return candidato
        numero += 1
        candidato = f"{base}-{numero % 100:02d}{numero // 100:02d}x" if numero >= 100 else f"{base}-{numero}"


# ---------------------------------------------------------------------------
# Personaggi: creazione, lettura, eliminazione
# ---------------------------------------------------------------------------

def cartella_personaggio(id_personaggio):
    return PERSONAGGI_DIR / id_personaggio


def crea_personaggio(nome, scheda, origine="giocatore", saluto=""):
    """Crea la cartella e i tre file JSON del personaggio, e restituisce l'id."""
    nome = str(nome).strip()
    if not nome:
        raise ValueError("Il personaggio deve avere un nome.")
    id_personaggio = id_libero(nome)
    cartella = cartella_personaggio(id_personaggio)
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / "backup").mkdir(exist_ok=True)

    ora = _adesso()

    _scrivi_json(cartella / "scheda.json", {
        "nome": nome,
        "origine": origine,                # 'giocatore' oppure 'ia'
        "creato_il": ora,
        **scheda,
    })
    _scrivi_json(cartella / "memoria.json", {
        "umore": "",
        "situazione": "",
        "relazione": {"fiducia": 50, "nota": ""},
        "ricordi": [],
    })
    conversazione = {"messaggi": []}
    if str(saluto).strip():
        conversazione["messaggi"].append({
            "ruolo": "personaggio",
            "testo": str(saluto).strip(),
            "data": ora,
        })
    _scrivi_json(cartella / "conversazione.json", conversazione)

    indice = leggi_indice()
    indice.setdefault("personaggi", []).append({
        "id": id_personaggio,
        "nome": nome,
        "origine": origine,
        "creato_il": ora,
        "aggiornato_il": ora,
    })
    _scrivi_indice(indice)
    return id_personaggio


def elimina_personaggio(id_personaggio):
    """Sposta la cartella del personaggio in dati/_eliminati (nessuna perdita)."""
    cartella = cartella_personaggio(id_personaggio)
    if not cartella.exists():
        return False

    indice = leggi_indice()
    indice["personaggi"] = [
        p for p in indice.get("personaggi", []) if p.get("id") != id_personaggio
    ]
    _scrivi_indice(indice)

    destinazione = ELIMINATI_DIR / f"{id_personaggio}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.replace(cartella, destinazione)
    return True


# ---------------------------------------------------------------------------
# Impostazioni generali (nome dell'utente, ecc.)
# ---------------------------------------------------------------------------

def _percorso_impostazioni():
    return DATI_DIR / "impostazioni.json"


def carica_impostazioni():
    inizializza_archivio()
    return _leggi_json(_percorso_impostazioni(), {"nome_utente": ""})


def salva_impostazioni(impostazioni):
    _scrivi_json(_percorso_impostazioni(), impostazioni)


# ---------------------------------------------------------------------------
# Scheda, memoria e conversazione
# ---------------------------------------------------------------------------

def carica_scheda(id_personaggio):
    cartella = cartella_personaggio(id_personaggio)
    scheda = _leggi_json(cartella / "scheda.json", None)
    if scheda is None:
        raise FileNotFoundError(f"Scheda non trovata per '{id_personaggio}'.")
    return scheda


def salva_scheda(id_personaggio, scheda):
    _scrivi_json(cartella_personaggio(id_personaggio) / "scheda.json", scheda)
    _tocca_indice(id_personaggio)


def carica_memoria(id_personaggio):
    cartella = cartella_personaggio(id_personaggio)
    memoria = _leggi_json(cartella / "memoria.json", None)
    if memoria is None:
        raise FileNotFoundError(f"Memoria non trovata per '{id_personaggio}'.")
    return memoria


def salva_memoria(id_personaggio, memoria, nota="", extra=None):
    """Salva la memoria registrando nel log lo stato precedente (per l'annulla)."""
    cartella = cartella_personaggio(id_personaggio)
    try:
        precedente = carica_memoria(id_personaggio)
    except FileNotFoundError:
        precedente = None
    _scrivi_json(cartella / "memoria.json", memoria)
    _tocca_indice(id_personaggio)
    _registra_log(cartella, precedente, memoria, nota, extra)


def carica_conversazione(id_personaggio):
    cartella = cartella_personaggio(id_personaggio)
    return _leggi_json(cartella / "conversazione.json", {"messaggi": []})


def salva_conversazione(id_personaggio, conversazione):
    _scrivi_json(cartella_personaggio(id_personaggio) / "conversazione.json", conversazione)
    _tocca_indice(id_personaggio)


def aggiungi_messaggio(id_personaggio, ruolo, testo):
    """Aggiunge un messaggio in coda e restituisce la conversazione aggiornata."""
    conversazione = carica_conversazione(id_personaggio)
    conversazione["messaggi"].append({
        "ruolo": ruolo,            # 'utente' oppure 'personaggio'
        "testo": str(testo).strip(),
        "data": _adesso(),
    })
    salva_conversazione(id_personaggio, conversazione)
    return conversazione


def svuota_conversazione(id_personaggio):
    """Cancella la cronologia dei messaggi ma NON la memoria."""
    cartella = cartella_personaggio(id_personaggio)
    _scrivi_json(cartella / "conversazione.json", {"messaggi": []})
    _tocca_indice(id_personaggio)


# ---------------------------------------------------------------------------
# Chat di regia (comunicazioni di servizio con la macchina, fuori dal gioco)
# ---------------------------------------------------------------------------

MAX_MESSAGGI_REGIA = 60


def carica_regia(id_personaggio):
    """Storico della chat di regia (dati/personaggi/<id>/regia.json)."""
    return _leggi_json(cartella_personaggio(id_personaggio) / "regia.json", {"messaggi": []})


def aggiungi_messaggio_regia(id_personaggio, ruolo, testo):
    """Aggiunge un messaggio alla chat di regia.

    A differenza della conversazione di gioco NON tocca 'aggiornato_il':
    le comunicazioni di servizio non cambiano la data dell'ultimo scambio
    mostrata nel menu.
    """
    regia = carica_regia(id_personaggio)
    regia.setdefault("messaggi", []).append({
        "ruolo": ruolo,            # 'utente' oppure 'macchina'
        "testo": str(testo).strip(),
        "data": _adesso(),
    })
    regia["messaggi"] = regia["messaggi"][-MAX_MESSAGGI_REGIA:]
    _scrivi_json(cartella_personaggio(id_personaggio) / "regia.json", regia)
    return regia


# ---------------------------------------------------------------------------
# Log della memoria (per la voce "Annulla ultima modifica")
# ---------------------------------------------------------------------------

def _registra_log(cartella, memoria_prima, memoria_dopo, nota, extra=None):
    log = cartella / "log_memoria.jsonl"
    voce = {
        "id": int(datetime.now().timestamp() * 1000),
        "data": _adesso(),
        "nota": str(nota or "").strip(),
        "memoria_prima": memoria_prima,
        "memoria_dopo": memoria_dopo,
    }
    if isinstance(extra, dict):
        voce.update(extra)
    cartella.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as file:
        file.write(json.dumps(voce, ensure_ascii=False) + "\n")
    _potare_log(log, MAX_VOCI_LOG)


def _potare_log(percorso, massime=200):
    """Tiene il log leggero: al massimo le ultime 'massime' voci."""
    try:
        with open(percorso, "r", encoding="utf-8") as file:
            righe = file.readlines()
        if len(righe) > massime:
            with open(percorso, "w", encoding="utf-8") as file:
                file.writelines(righe[-massime:])
    except OSError:
        pass


def leggi_log(id_personaggio, ultime=20):
    """Legge le ultime voci del log della memoria, dalla più recente."""
    percorso = cartella_personaggio(id_personaggio) / "log_memoria.jsonl"
    if not percorso.exists():
        return []
    voci = []
    try:
        with open(percorso, "r", encoding="utf-8") as file:
            for riga in file:
                riga = riga.strip()
                if riga:
                    try:
                        voci.append(json.loads(riga))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        return []
    return list(reversed(voci[-ultime:]))


def annulla_ultima_modifica(id_personaggio):
    """Ripristina la memoria com'era prima dell'ultima modifica.

    La voce di log usata viene consumata: un secondo annulla torna così
    alla modifica precedente, e così via a cascata.
    """
    percorso = cartella_personaggio(id_personaggio) / "log_memoria.jsonl"
    if not percorso.exists():
        return False
    try:
        with open(percorso, "r", encoding="utf-8") as file:
            righe = [r for r in file.read().splitlines() if r.strip()]
    except OSError:
        return False
    if not righe:
        return False
    try:
        ultima = json.loads(righe[-1])
    except json.JSONDecodeError:
        return False
    precedente = ultima.get("memoria_prima")
    if not isinstance(precedente, dict):
        return False
    _scrivi_json(cartella_personaggio(id_personaggio) / "memoria.json", precedente)
    _tocca_indice(id_personaggio)
    try:
        with open(percorso, "w", encoding="utf-8") as file:
            file.writelines(riga + "\n" for riga in righe[:-1])
    except OSError:
        pass
    return True
