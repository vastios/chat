# ♥ Chat Locale AI

Applicazione di **chat con personaggi AI** che gira **completamente sul tuo PC**: modello linguistico scaricato in locale (con **Ollama**), interfaccia web nel browser e una **memoria a lungo termine in JSON** che l'IA aggiorna da sola mentre chatti. Nessun cloud, nessun abbonamento, nessun dato che esce dalla macchina.

> Pensata per Windows su macchine **senza GPU moderna** (testata per Intel i7-4700HQ, 16 GB RAM): funziona **solo su CPU**, in modo lento ma reale.

---

## Cosa sa fare

- 💬 **Chat in italiano** con i personaggi della tua storia (o con un narratore che guida il racconto)
- 🧠 **Memoria a lungo termine**: personaggi, luoghi, eventi e scena corrente vivono in un file `stato.json`
- ✍️ **Archivista automatico**: dopo ogni scambio un secondo modello (più piccolo) aggiorna la memoria con **modifiche chirurgiche** (aggiorna solo i campi toccati), validata prima di scrivere
- 🔄 **Storico versioni**: ogni modifica salva una copia in `history/` — puoi annullare l'ultimo aggiornamento con un clic
- 👥 **Più personaggi**: passa da un interlocutore all'altro; la memoria registra le relazioni tra tutti
- 🎭 **Storia demo inclusa**: "Il Caffè di Pontevecchio", per provare subito l'app

## Come funziona (in breve)

```
[Tu scrivi] ──► [MODELLO ATTORE (7B)] ──► risposta in chat (in streaming)
                     │ (a fine scambio, in background)
                     ▼
             [MODELLO ARCHIVISTA (3B)]
                     │  produce SOLO operazioni JSON
                     ▼
        [validazione Pydantic] ──► scrittura atomica su stato.json
                     └─► copia della versione precedente in history/
```

Nella chat entra solo lo **stato rilevante** (scena, personaggio interpretato, pochi fatti chiave): il world state completo resta all'archivista. Così il contesto resta leggero e le risposte restano coerenti anche dopo settimane.

---

## Requisiti hardware (e la verità sulla tua GPU)

| Componente | Minimo consigliato | Note |
|---|---|---|
| CPU | 4 core recenti o vecchi con AVX2 | Haswell (2013+) va bene |
| RAM | 16 GB | i modelli occupano ~7 GB totali |
| Disco | SSD per i modelli | il caricamento passa da minuti a secondi |
| GPU | **non necessaria** | vedi sotto |

**⚠️ Nota importante sulla GPU:** le schede NVIDIA antecedenti alle serie 700/900 "veri" (es. la GeForce GT 750M, architettura Kepler del 2013) **non sono supportate dalle librerie CUDA moderne**, quindi Ollama lavorerà **solo su CPU**. Con un i7-4700HQ significa circa **5–10 parole al secondo**: la prima risposta arriva dopo 5–15 s (caricamento del modello), poi lo vedi scrivere parola per parola. Lento ma usabile — e l'archivista lavora in background senza bloccarti.

---

## Installazione su Windows (passo-passo)

La guida dettagliata con i rimedi ai problemi più comuni è in **[docs/INSTALLAZIONE.md](docs/INSTALLAZIONE.md)**. In sintesi:

1. **Installa Python** da [python.org](https://www.python.org/downloads/) — spunta *"Add python.exe to PATH"*.
2. **Installa Ollama** da [ollama.com/download/windows](https://ollama.com/download/windows) — sarà già attivo come icona vicino all'orologio.
3. **Scarica la cartella del progetto** (Code → Download ZIP, o `git clone`) e scompattala.
4. **Doppio clic su `1_installazione.bat`** — crea l'ambiente, installa le librerie e scarica i due modelli (~6,6 GB, una volta sola):
   - attore: `qwen2.5:7b-instruct-q4_K_M` (~4,7 GB)
   - archivista: `qwen2.5:3b-instruct-q4_K_M` (~1,9 GB)
5. **Doppio clic su `2_avvia.bat`** — si apre il browser su `http://localhost:7860`. Fatto.

### Consiglio: modelli sull'SSD

Ollama salva i modelli in `C:\Users\<tuo-utente>\.ollama\models`. Se quel disco è l'HDD, spostali sull'SSD così il caricamento è molto più veloce: crea la variabile d'ambiente utente `OLLAMA_MODELS` con un percorso tipo `D:\ollama\models` (Cerca Windows → "Modifica le variabili d'ambiente relative al sistema") e ri-scarica i modelli.

---

## Uso

- **Storia demo**: apri "Il Caffè di Pontevecchio" e parli subito con Sofia.
- **Nuova storia**: nome, premessa, tono, situazione iniziale e il primo personaggio.
- **Scegli con chi parlare** nella barra laterale (personaggi o Narratore).
- **Pannello 🧠 Memoria**: vedi in diretta il world state (con il JSON completo di ogni entità).
- **Toast viola**: quando l'archivista aggiorna la memoria ti mostra cosa ha cambiato — puoi **annullare** con un clic.
- I dati di ogni storia sono in `dati/storie/<id>/`: `stato.json` (memoria), `messaggi.jsonl` (cronologia), `history/` (versioni precedenti).

## Cambiare modelli

Tutto è configurabile con variabili d'ambiente (o modificando `backend/config.py`):

| Ruolo | Default (consigliato, 16 GB) | Alternativa più veloce | Alternativa più creativa |
|---|---|---|---|
| Attore | `qwen2.5:7b-instruct-q4_K_M` | `qwen2.5:3b-instruct-q4_K_M` | `llama3.1:8b-instruct-q4_K_M` |
| Archivista | `qwen2.5:3b-instruct-q4_K_M` | `qwen2.5:1.5b-instruct-q4_K_M` | `qwen2.5:7b-instruct-q4_K_M` |

```bat
rem esempio: attore più veloce
set MODELLO_ATTORE=qwen2.5:3b-instruct-q4_K_M
2_avvia.bat
```

Per l'archivista meglio restare su Qwen 2.5 o Llama 3.1+: sono i modelli più affidabili nel produrre JSON puliti.

## Risoluzione problemi

| Problema | Rimedio |
|---|---|
| "Non riesco a contattare Ollama" | Apri Ollama dal menu Start (icona vicino all'orologio), oppure avvia `ollama serve` |
| "Il modello X non è installato" | `ollama pull qwen2.5:7b-instruct-q4_K_M` (e `ollama pull qwen2.5:3b-instruct-q4_K_M`) |
| Risposte troppo lente | Usa `MODELLO_ATTORE=qwen2.5:3b-instruct-q4_K_M`; tieni il progetto sui dischi SSD; chiudi browser e app pesanti |
| La memoria non si aggiorna mai | Controlla che l'archivista sia attivo (`ARCHIVISTA_ATTIVO=1`) e il modello installato; guarda `archivista_log.jsonl` |
| L'archivista cambia troppo | Alza `ARCHIVISTA_OGNI_N` (es. 2 = aggiorna ogni 2 scambi) |
| Ho rotto la memoria | `annulla` dal toast, oppure riprendi una copia da `dati/storie/<id>/history/` |

## Struttura del progetto

```
chat/
├── 1_installazione.bat      ← prima volta: ambiente + modelli
├── 2_avvia.bat              ← ogni volta: Ollama + server + browser
├── requirements.txt
├── backend/
│   ├── app.py               ← server web e API (Flask)
│   ├── config.py            ← modelli, porta, parametri
│   ├── attore.py            ← prompt e streaming del modello attore
│   ├── archivista.py        ← aggiornamento della memoria (JSON forzato)
│   ├── ollama_client.py     ← client API di Ollama
│   └── memoria/
│       ├── modelli.py       ← entità Pydantic (Personaggio, Luogo, Evento…)
│       └── gestore.py       ← scrittura atomica, versioning, operazioni
├── frontend/                ← interfaccia web (HTML/CSS/JS, vanilla)
├── dati/storie/…            ← world state, messaggi, history di ogni storia
└── docs/INSTALLAZIONE.md    ← guida dettagliata
```

## Roadmap (per il futuro)

- Recupero per similarità (vettoriale) dei ricordi lontani
- TTS locale (Piper) e voci dei personaggi
- Immagini locali (Stable Diffusion) per avatar e scene

## Licenza

MIT — fai quello che vuoi, citaci se ti piace.
