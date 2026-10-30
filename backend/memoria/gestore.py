# -*- coding: utf-8 -*-
"""Gestore della memoria a lungo termine (world state su disco).

Garanzie:
- Scrittura ATOMICA: prima un file temporaneo, poi os.replace (mai file mezzi).
- VERSIONING: prima di ogni modifica lo stato attuale viene copiato in
  history/<data>_<ora>.json — così puoi sempre tornare indietro.
- VALIDAZIONE: niente tocca il disco se Pydantic non accetta i dati.

Struttura di una storia sul disco:
  dati/storie/<id_storia>/
    stato.json            ← la memoria (world state)
    messaggi.jsonl        ← la cronologia della chat (una riga per messaggio)
    archivista_log.jsonl  ← le modifiche fatte dall'archivista (per la UI)
    history/              ← versioni precedenti di stato.json
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from backend.config import CARTELLA_DATI, MAX_VERSIONI_HISTORY
from backend.memoria.modelli import (
    CAMPI_CONSENTITI,
    Evento,
    Luogo,
    Operazione,
    Personaggio,
    Scena,
    StatoDelMondo,
    Storia,
)

_lock = threading.Lock()  # un solo scrittore alla volta

# ---------------------------------------------------------------- utilities

def slug(testo: str) -> str:
    """Trasforma un testo in un id corto: 'Il Caffè' → 'il_caffe'."""
    testo = unicodedata.normalize("NFKD", testo)
    testo = testo.encode("ascii", "ignore").decode("ascii").lower()
    testo = re.sub(r"[^a-z0-9]+", "_", testo).strip("_")
    return testo or "entita"


def _ora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _scrittura_atomica(percorso: Path, contenuto: str) -> None:
    tmp = percorso.with_name(percorso.name + ".tmp")
    tmp.write_text(contenuto, encoding="utf-8")
    os.replace(tmp, percorso)


def _carica_json(percorso: Path, predefinito):
    if not percorso.exists():
        return predefinito
    try:
        return json.loads(percorso.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return predefinito


# ---------------------------------------------------------------- percorsi

def cartella_storia(sid: str) -> Path:
    return CARTELLA_DATI / sid


def percorso_stato(sid: str) -> Path:
    return cartella_storia(sid) / "stato.json"


def percorso_messaggi(sid: str) -> Path:
    return cartella_storia(sid) / "messaggi.jsonl"


def percorso_log(sid: str) -> Path:
    return cartella_storia(sid) / "archivista_log.jsonl"


def percorso_history(sid: str) -> Path:
    return cartella_storia(sid) / "history"


# ---------------------------------------------------------------- storie

def elenco_storie() -> list[dict]:
    """Elenco sintetico delle storie esistenti."""
    storie = []
    if not CARTELLA_DATI.exists():
        return storie
    for cartella in sorted(CARTELLA_DATI.iterdir()):
        if not cartella.is_dir() or cartella.name.startswith("_"):
            continue
        stato_raw = _carica_json(cartella / "stato.json", None)
        if stato_raw is None:
            continue
        try:
            stato = StatoDelMondo.model_validate(stato_raw)
        except ValidationError:
            continue
        n_messaggi = 0
        pm = cartella / "messaggi.jsonl"
        if pm.exists():
            n_messaggi = sum(1 for riga in pm.read_text(encoding="utf-8").splitlines() if riga.strip())
        storie.append({
            "id": cartella.name,
            "nome": stato.storia.nome,
            "premessa": stato.storia.premessa,
            "tono": stato.storia.tono,
            "n_personaggi": len(stato.personaggi),
            "n_messaggi": n_messaggi,
        })
    return storie


def crea_storia(nome: str, premessa: str = "", tono: str = "",
                personaggi: Optional[list[dict]] = None,
                luoghi: Optional[list[dict]] = None,
                eventi: Optional[list[dict]] = None,
                situazione: str = "") -> str:
    """Crea una nuova storia con il suo world state iniziale."""
    base = slug(nome)
    sid = base
    i = 2
    with _lock:
        while cartella_storia(sid).exists():
            sid = f"{base}_{i}"
            i += 1
        cartella = cartella_storia(sid)
        cartella.mkdir(parents=True, exist_ok=True)
        (cartella / "history").mkdir(exist_ok=True)

        personaggi_validi = []
        for p in (personaggi or []):
            if not p.get("nome"):
                continue
            p = dict(p)
            p.setdefault("id", slug(p["nome"]))
            personaggi_validi.append(Personaggio.model_validate(p).model_dump())

        luoghi_validi = []
        for l in (luoghi or []):
            if not l.get("nome"):
                continue
            l = dict(l)
            l.setdefault("id", slug(l["nome"]))
            luoghi_validi.append(Luogo.model_validate(l).model_dump())

        eventi_validi = []
        for e in (eventi or []):
            if not e.get("titolo"):
                continue
            e = dict(e)
            e.setdefault("id", slug(e["titolo"]))
            eventi_validi.append(Evento.model_validate(e).model_dump())

        scena = Scena(situazione=situazione)
        if luoghi_validi:
            scena.luogo = luoghi_validi[0]["id"]
        if personaggi_validi:
            scena.presente = [personaggi_validi[0]["id"]]

        stato = StatoDelMondo(
            storia=Storia(nome=nome, premessa=premessa, tono=tono),
            personaggi=[Personaggio.model_validate(p) for p in personaggi_validi],
            luoghi=[Luogo.model_validate(l) for l in luoghi_validi],
            eventi=[Evento.model_validate(e) for e in eventi_validi],
            scena=scena,
            aggiornato_il=_ora(),
        )
        _scrittura_atomica(percorso_stato(sid), json.dumps(stato.model_dump(), ensure_ascii=False, indent=2))
        percorso_messaggi(sid).touch()
    return sid


def elimina_storia(sid: str) -> bool:
    """Elimina una storia spostandola in _eliminate_ (nessun dato perso subito)."""
    origine = cartella_storia(sid)
    if not origine.exists():
        return False
    destinazione = CARTELLA_DATI / f"_eliminata_{sid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    with _lock:
        origine.rename(destinazione)
    return True


# ---------------------------------------------------------------- stato

def carica_stato(sid: str) -> StatoDelMondo:
    raw = _carica_json(percorso_stato(sid), None)
    if raw is None:
        raise FileNotFoundError(f"Storia '{sid}' non trovata o stato.json corrotto.")
    return StatoDelMondo.model_validate(raw)


def salva_stato(sid: str, stato: StatoDelMondo) -> None:
    """Salva con backup di versione + scrittura atomica."""
    cartella = cartella_storia(sid)
    (cartella / "history").mkdir(parents=True, exist_ok=True)
    perc = percorso_stato(sid)
    if perc.exists():
        nome_bk = datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".json"
        shutil.copy2(perc, percorso_history(sid) / nome_bk)
        _pulisci_history(sid)
    stato.versione += 1
    stato.aggiornato_il = _ora()
    _scrittura_atomica(perc, json.dumps(stato.model_dump(), ensure_ascii=False, indent=2))


def _pulisci_history(sid: str) -> None:
    versioni = sorted(percorso_history(sid).glob("*.json"))
    eccesso = len(versioni) - MAX_VERSIONI_HISTORY
    for vecchio in versioni[:max(0, eccesso)]:
        vecchio.unlink(missing_ok=True)


def annulla_ultima_modifica(sid: str) -> dict:
    """Ripristina lo stato com'era PRIMA dell'ultima modifica salvata."""
    with _lock:
        versioni = sorted(percorso_history(sid).glob("*.json"))
        if not versioni:
            return {"ok": False, "msg": "Nessuna modifica da annullare."}
        ultima = versioni[-1]
        raw = _carica_json(ultima, None)
        if raw is None:
            return {"ok": False, "msg": "La versione di backup è corrotta."}
        try:
            stato = StatoDelMondo.model_validate(raw)
        except ValidationError as e:
            return {"ok": False, "msg": f"Backup non valido: {e.errors()[:1]}"}
        stato.versione = max(1, stato.versione - 1)
        stato.aggiornato_il = _ora()
        _scrittura_atomica(percorso_stato(sid),
                           json.dumps(stato.model_dump(), ensure_ascii=False, indent=2))
        ultima.unlink()  # consuma il backup (un annullamento per modifica)
        return {"ok": True, "msg": f"Ripristinata la versione precedente (v{stato.versione})."}


# ---------------------------------------------------------------- operazioni

def _trova_personaggio(stato: StatoDelMondo, pid: str) -> Optional[Personaggio]:
    for p in stato.personaggi:
        if p.id == pid:
            return p
    return None


def applica_operazioni(sid: str, operazioni: list[Operazione], nota: str = "") -> dict:
    """Applica in modo sicuro le operazioni dell'archivista al world state.

    Se qualcosa cambia, salva lo stato (con backup di versione) e registra
    la voce nel log dell'archivista, includendo la 'nota' esplicativa.
    Restituisce un riepilogo leggibile in italiano di ciò che è cambiato.
    Le operazioni non valide vengono scartate (e segnalate), mai applicate.
    """
    riepilogo: list[str] = []
    scartate: list[str] = []

    with _lock:
        stato = carica_stato(sid)

        for op in operazioni:
            try:
                _applica_una(stato, op, riepilogo)
            except (ValidationError, ValueError, KeyError, AttributeError) as e:
                scartate.append(f"{op.tipo}({op.id or '-'}): {e}")

        if riepilogo:
            salva_stato(sid, stato)
            voci = riepilogo + ([f"Nota: {nota}"] if nota else [])
            _registra_log(sid, voci, operazioni)

    return {"riepilogo": riepilogo, "scartate": scartate}


def _applica_una(stato: StatoDelMondo, op: Operazione, riepilogo: list[str]) -> None:
    tipo = op.tipo

    if tipo == "aggiorna_scena":
        for campo, valore in op.campi.items():
            if campo not in CAMPI_CONSENTITI["scena"]:
                continue
            if campo == "luogo":
                valore = slug(str(valore))
            setattr(stato.scena, campo, valore)
        riepilogo.append(f"Scena aggiornata: {stato.scena.situazione or stato.scena.luogo}")
        return

    if tipo in ("aggiorna_personaggio", "aggiungi_personaggio"):
        pid = op.id or slug(str(op.campi.get("nome", "")))
        p = _trova_personaggio(stato, pid)
        if p is None:
            nome = op.campi.get("nome") or pid
            nuovo = Personaggio(id=pid, nome=str(nome))
            for campo, valore in op.campi.items():
                if campo in CAMPI_CONSENTITI["personaggio"]:
                    setattr(nuovo, campo, valore)
            stato.personaggi.append(nuovo)
            riepilogo.append(f"Nuovo personaggio: {nuovo.nome}")
        else:
            cambiati = []
            for campo, valore in op.campi.items():
                if campo in CAMPI_CONSENTITI["personaggio"]:
                    setattr(p, campo, valore)
                    cambiati.append(campo)
            if cambiati:
                riepilogo.append(f"{p.nome} aggiornato ({', '.join(cambiati)})")
        return

    if tipo in ("aggiorna_luogo", "aggiungi_luogo"):
        lid = op.id or slug(str(op.campi.get("nome", "")))
        l = next((x for x in stato.luoghi if x.id == lid), None)
        if l is None:
            nome = op.campi.get("nome") or lid
            nuovo = Luogo(id=lid, nome=str(nome))
            for campo, valore in op.campi.items():
                if campo in CAMPI_CONSENTITI["luogo"]:
                    setattr(nuovo, campo, valore)
            stato.luoghi.append(nuovo)
            riepilogo.append(f"Nuovo luogo: {nuovo.nome}")
        else:
            cambiati = []
            for campo, valore in op.campi.items():
                if campo in CAMPI_CONSENTITI["luogo"]:
                    setattr(l, campo, valore)
                    cambiati.append(campo)
            if cambiati:
                riepilogo.append(f"Luogo {l.nome} aggiornato ({', '.join(cambiati)})")
        return

    if tipo in ("aggiorna_evento", "aggiungi_evento"):
        eid = op.id or slug(str(op.campi.get("titolo", "")))
        e = next((x for x in stato.eventi if x.id == eid), None)
        if e is None:
            titolo = op.campi.get("titolo") or eid
            nuovo = Evento(id=eid, titolo=str(titolo))
            for campo, valore in op.campi.items():
                if campo in CAMPI_CONSENTITI["evento"]:
                    setattr(nuovo, campo, valore)
            stato.eventi.append(nuovo)
            riepilogo.append(f"Nuovo evento: {nuovo.titolo}")
        else:
            cambiati = []
            for campo, valore in op.campi.items():
                if campo in CAMPI_CONSENTITI["evento"]:
                    setattr(e, campo, valore)
                    cambiati.append(campo)
            if cambiati:
                riepilogo.append(f"Evento {e.titolo} aggiornato ({', '.join(cambiati)})")
        return

    raise ValueError(f"Tipo operazione sconosciuto: {tipo}")


# ---------------------------------------------------------------- log archivista

def _registra_log(sid: str, riepilogo: list[str], operazioni: list[Operazione]) -> None:
    stato = carica_stato(sid)
    voce = {
        "id": prossimo_id_log(sid),
        "ora": _ora(),
        "riepilogo": riepilogo,
        "n_operazioni": len(operazioni),
        "versione_stato": stato.versione,
    }
    with percorso_log(sid).open("a", encoding="utf-8") as f:
        f.write(json.dumps(voce, ensure_ascii=False) + "\n")


def prossimo_id_log(sid: str) -> int:
    perc = percorso_log(sid)
    ultimo = 0
    if perc.exists():
        for riga in perc.read_text(encoding="utf-8").splitlines():
            if not riga.strip():
                continue
            try:
                ultimo = max(ultimo, int(json.loads(riga).get("id", 0)))
            except (json.JSONDecodeError, ValueError):
                continue
    return ultimo + 1


def leggi_log(sid: str, dopo_id: int = 0) -> dict:
    voci = []
    perc = percorso_log(sid)
    if perc.exists():
        for riga in perc.read_text(encoding="utf-8").splitlines():
            if not riga.strip():
                continue
            try:
                v = json.loads(riga)
                if int(v.get("id", 0)) > dopo_id:
                    voci.append(v)
            except (json.JSONDecodeError, ValueError):
                continue
    return {"voci": voci, "ultimo_id": max([int(v.get("id", 0)) for v in voci], default=dopo_id)}


# ---------------------------------------------------------------- messaggi

def carica_messaggi(sid: str) -> list[dict]:
    perc = percorso_messaggi(sid)
    messaggi = []
    if not perc.exists():
        return messaggi
    for riga in perc.read_text(encoding="utf-8").splitlines():
        if not riga.strip():
            continue
        try:
            messaggi.append(json.loads(riga))
        except json.JSONDecodeError:
            continue
    return messaggi


def aggiungi_messaggio(sid: str, ruolo: str, nome: str, testo: str) -> dict:
    msg = {"ora": _ora(), "ruolo": ruolo, "nome": nome, "testo": testo}
    with percorso_messaggi(sid).open("a", encoding="utf-8") as f:
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return msg


def numero_messaggi(sid: str) -> int:
    return len(carica_messaggi(sid))
