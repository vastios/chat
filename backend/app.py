# -*- coding: utf-8 -*-
"""Server web locale dell'app Chat Locale AI.

- Serve l'interfaccia (frontend/) su http://localhost:7860
- Espone le API JSON per storie, chat (in streaming), memoria e archivista.
- Ascolta SOLO su 127.0.0.1: nessuno dall'esterno può accedere.

Avvio:  python -m backend.app
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

from backend import archivista, attore, config, ollama_client
from backend.memoria import gestore

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("server")

FRONTEND = config.BASE_DIR / "frontend"

app = Flask(__name__, static_folder=str(FRONTEND), static_url_path="/")

# Stato archivista in corso, per storia (per l'indicatore nella UI)
_arch_in_corso: dict[str, bool] = {}
_lock_arch = threading.Lock()


# ------------------------------------------------------------------ pagina

@app.get("/")
def home():
    return send_from_directory(FRONTEND, "index.html")


@app.get("/favicon.ico")
def favicon():
    return ("", 204)


# ------------------------------------------------------------------ salute

@app.get("/api/salute")
def salute():
    attivo = ollama_client.ollama_attivo()
    modelli = ollama_client.modelli_installati() if attivo else []
    return jsonify({
        "ollama_attivo": attivo,
        "modelli": modelli,
        "modello_attore": config.MODELLO_ATTORE,
        "modello_archivista": config.MODELLO_ARCHIVISTA,
        "attore_presente": any(m == config.MODELLO_ATTORE or m.startswith(config.MODELLO_ATTORE) for m in modelli),
        "archivista_presente": any(m == config.MODELLO_ARCHIVISTA or m.startswith(config.MODELLO_ARCHIVISTA) for m in modelli),
    })


# ------------------------------------------------------------------ storie

@app.get("/api/storie")
def lista_storie():
    return jsonify({"storie": gestore.elenco_storie()})


@app.post("/api/storie")
def nuova_storia():
    corpo = request.get_json(force=True, silent=True) or {}
    nome = str(corpo.get("nome") or "").strip()
    if not nome:
        return jsonify({"errore": "Il nome della storia è obbligatorio."}), 400
    sid = gestore.crea_storia(
        nome=nome,
        premessa=str(corpo.get("premessa") or ""),
        tono=str(corpo.get("tono") or ""),
        personaggi=corpo.get("personaggi") or [],
        luoghi=corpo.get("luoghi") or [],
        eventi=corpo.get("eventi") or [],
        situazione=str(corpo.get("situazione") or ""),
    )
    return jsonify({"id": sid})


@app.get("/api/storie/<sid>")
def dettaglio_storia(sid):
    try:
        stato = gestore.carica_stato(sid)
    except FileNotFoundError as e:
        return jsonify({"errore": str(e)}), 404
    messaggi = gestore.carica_messaggi(sid)
    return jsonify({"stato": stato.model_dump(), "messaggi": messaggi[-80:]})


@app.post("/api/storie/<sid>/elimina")
def rimuovi_storia(sid):
    if gestore.elimina_storia(sid):
        return jsonify({"ok": True})
    return jsonify({"errore": "Storia non trovata."}), 404


# ------------------------------------------------------------------ chat

@app.post("/api/storie/<sid>/messaggi")
def invia_messaggio(sid):
    corpo = request.get_json(force=True, silent=True) or {}
    testo = str(corpo.get("testo") or "").strip()
    interlocutore = str(corpo.get("interlocutore") or "").strip() or attore.NARRATORE

    if not testo:
        return jsonify({"errore": "Il messaggio è vuoto."}), 400
    try:
        gestore.carica_stato(sid)
    except FileNotFoundError as e:
        return jsonify({"errore": str(e)}), 404

    gestore.aggiungi_messaggio(sid, "utente", "Tu", testo)

    def genera():
        parti: list[str] = []
        try:
            for pezzo in attore.genera_risposta(sid, interlocutore, testo):
                parti.append(pezzo)
                yield pezzo
        except ollama_client.ErroreOllama as e:
            yield f"\n\n⚠️ {e}"
            return
        except ValueError as e:
            yield f"\n\n⚠️ {e}"
            return
        except Exception as e:  # noqa: BLE001
            log.exception("Errore durante la generazione")
            yield f"\n\n⚠️ Errore inatteso: {e}"
            return

        risposta = "".join(parti).strip()
        if not risposta:
            return

        ruolo = "narratore" if interlocutore == attore.NARRATORE else "personaggio"
        gestore.aggiungi_messaggio(sid, ruolo, interlocutore, risposta)

        # Archivista in background (a scadenza configurabile)
        n = gestore.numero_messaggi(sid)
        if config.ARCHIVISTA_ATTIVO and config.ARCHIVISTA_OGNI_N > 0 and \
                n % (2 * config.ARCHIVISTA_OGNI_N) == 0:  # ogni N scambi completi
            with _lock_arch:
                _arch_in_corso[sid] = True
            threading.Thread(
                target=_esegui_archivista,
                args=(sid, testo, risposta, interlocutore),
                daemon=True,
            ).start()

    resp = Response(stream_with_context(genera()), mimetype="text/plain; charset=utf-8")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


def _esegui_archivista(sid, testo_utente, risposta, interlocutore):
    try:
        esito = archivista.aggiorna_memoria(sid, testo_utente, risposta, interlocutore)
        log.info("Archivista (%s): %s", sid, esito.get("nota") or esito.get("msg") or "nessuna modifica")
    finally:
        with _lock_arch:
            _arch_in_corso[sid] = False


# ------------------------------------------------------------------ archivista / memoria

@app.get("/api/storie/<sid>/archivista")
def stato_archivista(sid):
    dopo = int(request.args.get("dopo", "0") or 0)
    with _lock_arch:
        in_corso = bool(_arch_in_corso.get(sid, False))
    dati = gestore.leggi_log(sid, dopo)
    return jsonify({"in_corso": in_corso, **dati})


@app.post("/api/storie/<sid>/annulla_memoria")
def annulla_memoria(sid):
    return jsonify(gestore.annulla_ultima_modifica(sid))


# ------------------------------------------------------------------ avvio

def _apri_browser():
    import webbrowser
    try:
        webbrowser.open(f"http://localhost:{config.PORTA}")
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    print()
    print("  ╭──────────────────────────────────────────────────╮")
    print("  │   Chat Locale AI — i tuoi personaggi, offline    │")
    print(f"  │   http://localhost:{config.PORTA:<26}│")
    print("  ╰──────────────────────────────────────────────────╯")
    print()

    if not ollama_client.ollama_attivo():
        print("  ⚠️  Ollama non è raggiungibile su", config.URL_OLLAMA)
        print("     Avvia Ollama (menu Start → Ollama) e poi ricarica la pagina.")
        print()

    threading.Timer(1.2, _apri_browser).start()
    app.run(host="127.0.0.1", port=config.PORTA, debug=False, threaded=True)
