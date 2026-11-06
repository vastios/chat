# 💬 Chat Personaggi

Chat locale con personaggi AI, in italiano. È l'evoluzione di **LocalStoryEngine**:
stessa struttura a moduli, ma il prodotto non è più un gioco di ruolo fantasy —
è una chat di personaggi (stile Rosytalk) con una **memoria viva su file JSON**
che l'IA aggiorna da sola dopo ogni scambio.

Tutto gira sul tuo computer: **Python + Streamlit + LM Studio**. Nessun dato esce di casa.

---

## Struttura del progetto (ereditata da LocalStoryEngine)

| Vecchio progetto (RPG) | Nuovo progetto (chat personaggi) |
|---|---|
| `app.py` — interfaccia Streamlit | `app.py` — interfaccia Streamlit (sidebar + chat) |
| `config.py` — percorsi e prompt | `config.py` — percorsi, modelli e prompt |
| `game/database.py` — SQLite | `personaggi/database.py` — **archivio JSON** |
| `game/character.py` + `npcs.py` — scheda RPG e PNG | `personaggi/personaggio.py` — scheda identità del personaggio |
| *ricordi e fiducia aggiornati a mano* | `personaggi/memoria.py` — ricordi, fiducia, umore con log e annulla |
| `game/narrator.py` — LM Studio | `personaggi/lmstudio.py` — **stesso collegamento, identico**; `personaggi/narratore.py` — prompt e streaming |
| *assente (mai collegato)* | `personaggi/archivista.py` — **aggiorna la memoria da solo** |
| `game/world.py`, `combat.py`, `inventory.py` | *rimossi: niente RPG (per ora)* |

## I file JSON della memoria

Ogni personaggio ha la sua cartella in `dati/personaggi/<id>/`, leggibile a occhio nudo:

```
dati/
  personaggi.json              elenco di tutti i personaggi
  impostazioni.json            il tuo nome
  personaggi/
    sofia/
      scheda.json              identità canonica: aspetto, personalità, storia,
                               modo di parlare, obiettivo, SEGRETO, conoscenze
      memoria.json             umore, situazione, relazione (fiducia 0-100 + nota),
                               ricordi (testo + importanza 1-5 + data)
      conversazione.json       cronologia dei messaggi
      log_memoria.jsonl        stato precedente a ogni modifica → "Annulla" sempre possibile
```

**La memoria si aggiorna da sola**: dopo ogni tua risposta, il modello caricato
in LM Studio (o uno più leggero, a tua scelta) rilegge lo scambio e aggiorna
umore, situazione, fiducia e ricordi.
Ogni modifica è visibile nel pannello 🧠 e puoi annullarla con un clic.
Puoi anche disattivare l'aggiornamento automatico e scrivere i ricordi a mano.

## Installazione (Windows)

1. Installa [Python](https://www.python.org/downloads/) (spunta *Add Python to PATH*)
   e [LM Studio](https://lmstudio.ai).
2. Fai doppio clic su **`1_installazione.bat`**: crea l'ambiente virtuale e installa
   Streamlit.
3. In LM Studio: cerca e scarica un modello (consigliato **Qwen2.5 7B Instruct**,
   quantizzazione q4_K_M, ~4,7 GB), caricalo e avvia il server locale dalla scheda
   **Developer → Start Server** (porta 1234).
4. Fai doppio clic su **`2_avvia.bat`**: si apre la pagina nel browser.

Da terminale (Linux/Mac o se preferisci i comandi):

```bash
python -m venv venv
venv\Scripts\activate        # Windows   (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
streamlit run app.py
# serve LM Studio avviato: modello caricato e server locale attivo (porta 1234)
```

## Come si usa

1. **Scegli il personaggio** nella barra laterale (al primo avvio trovi Sofia, di esempio).
2. **Crea i tuoi personaggi**: con una descrizione (li compone l'IA) oppure
   campo per campo, includendo il segreto che non riveleranno facilmente.
3. **Chiacchiera**: il personaggio risponde in streaming, coerente con scheda e memoria.
4. **Guarda la memoria crescere** nel pannello 🧠: umore, situazione, fiducia e ricordi
   si aggiornano dopo ogni scambio. Se un aggiornamento non ti piace: *Annulla*.
5. Il tuo nome lo imposti nella barra laterale: il personaggio ti chiamerà per nome.

## La fiducia e il segreto

La **fiducia** (0-100) evolve con il comportamento dell'utente: gentilezza,
provocazioni, bugie. Finché la fiducia è sotto 70, il personaggio **non rivela
il suo segreto** nemmeno se pregato. È la regola di continuità del vecchio
progetto, finalmente collegata al modello.

## Personalizzazioni

Tutte in `config.py` (o con variabili d'ambiente): indirizzo del server LM Studio
(`LMSTUDIO_URL`), modelli per attore e archivista (vuoti = modello caricato, come
nel vecchio progetto), temperatura, quanti messaggi/ricordi entrano nel contesto,
lunghezza delle risposte.

## Problemi comuni

| Problema | Soluzione |
|---|---|
| "LM Studio non risponde" | Apri LM Studio e premi **Start Server** nella scheda Developer, poi ricarica la pagina |
| "Nessun modello caricato" | In LM Studio scarica e carica un modello (es. **Qwen2.5 7B Instruct**) |
| Risposte lentissime | Normale su CPU (5-10 parole/sec): carica in LM Studio un modello più leggero (es. **Qwen2.5 3B Instruct**) |
| Ho sbagliato a creare un personaggio | Pannello 🪪 → Modifica la scheda; o eliminalo con 🗑️ |
| La memoria ha fatto un pasticcio | Bottone ↩️ *Annulla ultima modifica della memoria* |

---

*Consiglio: i file in `dati/` sono la tua storia. Copiali di tanto in tanto, come un salvataggio.*
