# LocalStoryEngine - versione modulare

Questa cartella contiene i file Python aggiornati per organizzare LocalStoryEngine in moduli.

## File inclusi
- `app.py`: interfaccia Streamlit e coordinamento
- `config.py`: percorsi, indirizzo di LM Studio e prompt narrativo
- `game/database.py`: database e salvataggi
- `game/character.py`: operazioni del personaggio
- `game/inventory.py`: inventario, equipaggiamento e pozioni
- `game/narrator.py`: comunicazione con LM Studio
- `game/world.py`: luoghi iniziali
- `game/combat.py`: regole di combattimento di base
- `game/__init__.py`: rende esplicito il pacchetto Python

## Installazione prudente
1. Chiudi Streamlit nel terminale con `Ctrl+C`.
2. Conserva la copia di backup già creata.
3. Estrai questi file nella cartella `C:\LocalStoryEngine`, mantenendo le sottocartelle e consentendo la sostituzione dei file Python quando Windows lo chiede.
4. **Non copiare, cancellare o sostituire la cartella `data`**: questa distribuzione non contiene `data/story.db`.
5. Apri il terminale nella cartella del progetto, attiva l'ambiente virtuale e avvia:
   `python -m streamlit run app.py`

LM Studio deve essere avviato e il modello deve essere caricato, come prima.

Questa versione non crea una nuova partita: `initialize_db()` usa `CREATE TABLE IF NOT EXISTS`, `INSERT OR IGNORE` e aggiunge solo le colonne di equipaggiamento mancanti.
