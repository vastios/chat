# Installazione dettagliata su Windows

## 0. Controlla le tue finestre

- **Windows 10/11 a 64 bit** ✔
- **16 GB di RAM**: i modelli consigliati usano ~7 GB insieme, il resto lo tiene il sistema
- **~7 GB liberi** per i modelli (meglio se su SSD)

## 1. Python (una volta sola)

1. Vai a <https://www.python.org/downloads/> e scarica l'ultima versione (3.11+).
2. Esegui l'installer: **spunta "Add python.exe to PATH"** (fondamentale!), poi *Install Now*.
3. Verifica: apri "Prompt dei comandi" e scrivi `python --version` → deve rispondere qualcosa tipo `Python 3.12.5`.

## 2. Ollama (una volta sola)

1. Scarica da <https://ollama.com/download/windows> e installa (Avanti, Avanti, Fine).
2. Al termine Ollama parte da solo: vedrai un'icona (un lama) vicino all'orologio.
3. Verifica: nel Prompt dei comandi scrivi `ollama --version` → deve rispondere con una versione.

> **Se vuoi i modelli sull'SSD** (consigliato se `C:\Users\<utente>\.ollama` finisce sull'HDD):
> 1. Cerca Windows → "Modifica le variabili d'ambiente relative al sistema" → *Variabili d'ambiente…*
> 2. Sotto "Variabili utente" → *Nuova*: nome `OLLAMA_MODELS`, valore un percorso sull'SSD, es. `D:\ollama\models`
> 3. Riavvia Ollama (esci dall'icona dell'orologio e riaprilo dal menu Start), poi procedi: i modelli finiranno lì.

## 3. Il progetto

Se hai Git installato:

```bat
git clone https://github.com/vastios/chat.git
cd chat
```

Altrimenti: dalla pagina del repo → bottone verde **Code** → **Download ZIP** → scompatta.

## 4. `1_installazione.bat` (una volta sola)

Doppio clic. Fa tutto: crea `venv`, installa Flask/Pydantic/Requests e scarica i due modelli:

- `qwen2.5:7b-instruct-q4_K_M` — l'**attore** (~4,7 GB)
- `qwen2.5:3b-instruct-q4_K_M` — l'**archivista** (~1,9 GB)

Il download dipende dalla linea: da 10 a 40 minuti. Dura solo una volta.

> Se preferisci avviare i passaggi a mano:
> ```bat
> python -m venv venv
> venv\Scripts\activate.bat
> pip install -r requirements.txt
> ollama pull qwen2.5:7b-instruct-q4_K_M
> ollama pull qwen2.5:3b-instruct-q4_K_M
> ```

## 5. `2_avvia.bat` (ogni volta)

Doppio clic. Lo script:

1. controlla che Ollama sia attivo (se no lo avvia ridotto a icona);
2. avvia il server locale su **http://localhost:7860**;
3. apre il browser.

Si apre la schermata con le storie: la demo **"Il Caffè di Pontevecchio"** è già pronta.
Per chiudere: chiudi la finestra nera del server (e, se vuoi, esci anche dall'icona di Ollama).

## Come si usa in due minuti

1. Apri la storia demo → al centro la chat, a sinistra i personaggi.
2. Scrivi a Sofia qualcosa tipo: *"Mi sono accorto di averti pensata per dieci anni."*
3. La prima risposta arriva dopo 5–15 s (caricamento del modello), poi vedi il testo crescere parola per parola (5–10 parole/s su CPU).
4. A fine scambio, dopo qualche secondo, appare il **toast viola**: l'archivista ha aggiornato la memoria (es. *"Sofia ora è scossa: Marco le ha detto che…"*). Con **Annulla** ripristini lo stato precedente.
5. Bottone **🧠 Memoria della storia**: vedi personaggi, luoghi, eventi e scena — con il JSON completo di ogni scheda.

## Problemi frequenti

| Sintomo | Causa probabile | Rimedio |
|---|---|---|
| `python --version` non funziona | PATH mancante | reinstaller Python spuntando "Add to PATH" |
| `1_installazione.bat` si chiude subito | doppio clic bloccato dal server | clic destro → esegui come amministratore, o usa il Prompt dei comandi |
| La chat dice "Non riesco a contattare Ollama" | Ollama non è avviato | menu Start → Ollama; controlla l'icona vicino all'orologio |
| "Il modello non è installato" | pull non completato | `ollama pull qwen2.5:7b-instruct-q4_K_M` |
| Le risposte tardano troppo la prima volta | modello su HDD | sposta i modelli su SSD (`OLLAMA_MODELS`), o usa il 3B come attore |
| Porta 7860 occupata | altro programma | `set PORTA=7861` prima di `2_avvia.bat` |
| Ho cancellato una storia per errore | — | le storie eliminate vanno in `dati/storie/_eliminata_…`: rinomina la cartella e torna tutto |
