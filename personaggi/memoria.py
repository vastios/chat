"""La memoria a lungo termine del personaggio.

Qui c'è il vero salto rispetto al vecchio LocalStoryEngine: nel vecchio
progetto i ricordi e la fiducia dei PNG esistevano, ma andava aggiornati
A MANO dall'utente. Ora la memoria è viva:

- umore        : come si sente il personaggio adesso
- situazione   : cosa sta succedendo nella sua vita/conversazione
- relazione    : fiducia 0-100 verso l'utente, con una nota che la spiega
- ricordi      : fatti concreti, ognuno con importanza da 1 a 5

Ogni modifica arriva dall'archivista (dopo ogni scambio in chat) oppure
dall'utente dal pannello laterale, passa per applic_aggiornamenti() che la
valida, e viene registrata in log_memoria.jsonl con lo stato precedente:
per questo è sempre possibile annullare l'ultima modifica.
"""

from datetime import datetime

from personaggi import database
from config import MAX_RICORDI_CONTESTO


# ---------------------------------------------------------------------------
# Struttura della memoria
# ---------------------------------------------------------------------------

def memoria_predefinita():
    return {
        "umore": "",
        "situazione": "",
        "relazione": {"fiducia": 50, "nota": ""},
        "ricordi": [],
    }


def _adesso():
    return datetime.now().isoformat(timespec="seconds")


def _pulisci(testo):
    return " ".join(str(testo or "").split())


def normalizza_memoria(memoria):
    """Garantisce che tutti i campi esistano, anche nei file creati prima."""
    base = memoria_predefinita()
    if not isinstance(memoria, dict):
        return base
    base["umore"] = _pulisci(memoria.get("umore", ""))
    base["situazione"] = _pulisci(memoria.get("situazione", ""))

    relazione = memoria.get("relazione") or {}
    if isinstance(relazione, dict):
        base["relazione"] = {
            "fiducia": _limita_fiducia(relazione.get("fiducia", 50)),
            "nota": _pulisci(relazione.get("nota", "")),
        }

    ricordi = []
    for ricordo in memoria.get("ricordi") or []:
        testo = _pulisci(ricordo.get("testo", "")) if isinstance(ricordo, dict) else _pulisci(ricordo)
        if not testo:
            continue
        ricordi.append({
            "id": int(ricordo.get("id", len(ricordi) + 1)) if isinstance(ricordo, dict) else len(ricordi) + 1,
            "testo": testo,
            "importanza": _limita_importanza(ricordo.get("importanza", 2) if isinstance(ricordo, dict) else 2),
            "data": _pulisci(ricordo.get("data", "")) if isinstance(ricordo, dict) else "",
        })
    base["ricordi"] = ricordi
    return base


def _limita_fiducia(valore):
    try:
        return max(0, min(100, int(valore)))
    except (TypeError, ValueError):
        return 50


def _limita_importanza(valore):
    try:
        return max(1, min(5, int(valore)))
    except (TypeError, ValueError):
        return 2


# ---------------------------------------------------------------------------
# Aggiornamenti (dall'archivista o manuali)
# ---------------------------------------------------------------------------

def applica_aggiornamenti(id_personaggio, aggiornamenti, nota="", delta_max_fiducia=10, n_messaggi=None):
    """Applica a memoria.json le modifiche proposte, dopo averle validate.

    'aggiornamenti' è un dizionario con campi facoltativi:
        umore, situazione, relazione {delta_fiducia, nota}, nuovi_ricordi [{testo, importanza}]

    L'archivista usa il limite predefinito di ±10 per scambio (l'evoluzione è
    graduale); le modifiche manuali possono passare un limite più ampio.
    'n_messaggi' è il numero di messaggi elaborati: registrato nel log, serve
    all'archivista per capire da dove riprendere.

    Restituisce l'elenco testuale delle modifiche applicate (per la notifica).
    """
    memoria = normalizza_memoria(database.carica_memoria(id_personaggio))
    cambiamenti = []

    if not isinstance(aggiornamenti, dict):
        return cambiamenti

    umore = _pulisci(aggiornamenti.get("umore", ""))
    if umore and umore != memoria["umore"]:
        memoria["umore"] = umore[:200]
        cambiamenti.append(f"Umore: {umore[:200]}")

    situazione = _pulisci(aggiornamenti.get("situazione", ""))
    if situazione and situazione != memoria["situazione"]:
        memoria["situazione"] = situazione[:300]
        cambiamenti.append(f"Situazione: {situazione[:300]}")

    relazione = aggiornamenti.get("relazione")
    if isinstance(relazione, dict):
        if relazione.get("delta_fiducia") not in (None, "", 0, "0"):
            try:
                delta = max(-delta_max_fiducia, min(delta_max_fiducia, int(relazione["delta_fiducia"])))
            except (TypeError, ValueError):
                delta = 0
            if delta:
                prima = memoria["relazione"]["fiducia"]
                memoria["relazione"]["fiducia"] = _limita_fiducia(prima + delta)
                freccia = "+" if delta > 0 else ""
                cambiamenti.append(
                    f"Fiducia: {prima} → {memoria['relazione']['fiducia']} ({freccia}{delta})"
                )
        nota_relazione = _pulisci(relazione.get("nota", ""))
        if nota_relazione and nota_relazione != memoria["relazione"]["nota"]:
            memoria["relazione"]["nota"] = nota_relazione[:300]
            cambiamenti.append(f"Nota relazione: {nota_relazione[:300]}")

    nuovi = aggiornamenti.get("nuovi_ricordi")
    if isinstance(nuovi, list):
        prossima_id = max((r["id"] for r in memoria["ricordi"]), default=0) + 1
        aggiunti = 0
        for elemento in nuovi:
            if aggiunti >= 3:
                break
            testo = _pulisci(elemento.get("testo", "")) if isinstance(elemento, dict) else _pulisci(elemento)
            if not testo:
                continue
            # Niente doppioni: se il ricordo è già registrato, lo salta.
            if any(testo.casefold() == r["testo"].casefold() for r in memoria["ricordi"]):
                continue
            importanza = _limita_importanza(
                elemento.get("importanza", 2) if isinstance(elemento, dict) else 2
            )
            memoria["ricordi"].append({
                "id": prossima_id,
                "testo": testo[:300],
                "importanza": importanza,
                "data": _adesso(),
            })
            prossima_id += 1
            aggiunti += 1
            cambiamenti.append(f"Nuovo ricordo ({importanza}/5): {testo[:300]}")

    if cambiamenti:
        extra = {"n_messaggi": int(n_messaggi)} if n_messaggi is not None else None
        database.salva_memoria(
            id_personaggio, memoria, nota=nota or "; ".join(cambiamenti), extra=extra
        )
    return cambiamenti


def aggiungi_ricordo_manuale(id_personaggio, testo, importanza=3):
    """Ricordo scritto a mano dall'utente (come nel vecchio pannello PNG)."""
    return applica_aggiornamenti(
        id_personaggio,
        {"nuovi_ricordi": [{"testo": testo, "importanza": importanza}]},
        nota="Ricordo aggiunto manualmente",
    )


def modifica_fiducia_manuale(id_personaggio, delta, nota_nuova=None):
    """Variazione manuale della fiducia, come nel vecchio pannello PNG."""
    aggiornamenti = {"relazione": {"delta_fiducia": max(-100, min(100, int(delta)))}}
    if nota_nuova is not None:
        aggiornamenti["relazione"]["nota"] = nota_nuova
    return applica_aggiornamenti(
        id_personaggio,
        aggiornamenti,
        nota="Relazione aggiornata manualmente",
        delta_max_fiducia=100,
    )


# ---------------------------------------------------------------------------
# Contesto per il narratore
# ---------------------------------------------------------------------------

def formatta_per_contesto(memoria, nome_utente=""):
    """Blocco di memoria da iniettare nel prompt dell'attore.

    I ricordi vengono scelti per importanza e poi per data: i più importanti
    e i più recenti entrano nel prompt, gli altri restano nel file JSON.
    """
    memoria = normalizza_memoria(memoria)
    righe = []

    if memoria["umore"]:
        righe.append(f"Umore attuale: {memoria['umore']}")
    if memoria["situazione"]:
        righe.append(f"Situazione: {memoria['situazione']}")

    fiducia = memoria["relazione"]["fiducia"]
    if fiducia >= 70:
        tono = "vi siete avvicinati molto"
    elif fiducia >= 40:
        tono = "c'è una buona familiarità"
    elif fiducia >= 20:
        tono = "vi conoscete poco"
    else:
        tono = "c'è quasi diffidenza"
    relazione = f"Rapporto con {nome_utente or 'l\u2019utente'}: fiducia {fiducia}/100 ({tono})"
    if memoria["relazione"]["nota"]:
        relazione += f". {memoria['relazione']['nota']}"
    righe.append(relazione)

    if memoria["ricordi"]:
        ordinati = sorted(
            memoria["ricordi"],
            key=lambda r: (r["importanza"], r["data"]),
            reverse=True,
        )[:MAX_RICORDI_CONTESTO]
        righe.append("Ricordi (in ordine di importanza):")
        for ricordo in ordinati:
            righe.append(f"- [{ricordo['importanza']}/5] {ricordo['testo']}")
    else:
        righe.append("Non hai ancora ricordi: è l'inizio della vostra storia. Non inventare passati comuni.")

    return "\n".join(righe)


def riepilogo_leggibile(memoria):
    """Versione per il pannello laterale dell'interfaccia."""
    memoria = normalizza_memoria(memoria)
    return memoria
