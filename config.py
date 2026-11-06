"""Configurazione di Chat Personaggi.

Tutti i valori possono essere sovrascritti con variabili d'ambiente,
ad esempio:  set LMSTUDIO_URL=http://localhost:1234/v1
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Percorsi
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DATI_DIR = BASE_DIR / "dati"                       # tutti i file JSON vivono qui
PERSONAGGI_DIR = DATI_DIR / "personaggi"
ELIMINATI_DIR = DATI_DIR / "_eliminati"            # personaggi cestinati, non persi

# ---------------------------------------------------------------------------
# LM Studio (come nel vecchio LocalStoryEngine)
# ---------------------------------------------------------------------------

# Indirizzo del server locale di LM Studio: scheda Developer → Start Server.
BASE_URL = os.environ.get("LMSTUDIO_URL", "http://localhost:1234/v1")

# Nome del modello da usare. Se lasciato vuoto (come di default) si usa
# automaticamente il modello caricato in LM Studio, esattamente come faceva
# LocalStoryEngine. Se carichi due modelli e vuoi ruoli separati, scrivi qui
# i loro nomi esatti (li vedi nella pagina del server di LM Studio), ad esempio:
#   set MODELLO_ATTORE=qwen2.5-7b-instruct
MODELLO_ATTORE = os.environ.get("MODELLO_ATTORE", "")
# Modello che aggiorna la memoria in background: se vuoto usa lo stesso
# dell'attore. Con un modello leggero dedicato l'aggiornamento è più rapido.
MODELLO_ARCHIVISTA = os.environ.get("MODELLO_ARCHIVISTA", "")

TEMPERATURA_ATTORE = float(os.environ.get("TEMPERATURA_ATTORE", "0.8"))
TEMPERATURA_ARCHIVISTA = float(os.environ.get("TEMPERATURA_ARCHIVISTA", "0.2"))
MAX_TOKENS_ATTORE = int(os.environ.get("MAX_TOKENS_ATTORE", "700"))
MAX_TOKENS_ARCHIVISTA = int(os.environ.get("MAX_TOKENS_ARCHIVISTA", "500"))

# ---------------------------------------------------------------------------
# Contesto e memoria
# ---------------------------------------------------------------------------

MESSAGGI_CONTESTO = int(os.environ.get("MESSAGGI_CONTESTO", "24"))     # messaggi recenti inviati all'attore
MAX_RICORDI_CONTESTO = int(os.environ.get("MAX_RICORDI_CONTESTO", "20"))  # ricordi massimi nel prompt
MAX_PAROLE_RISPOSTA = int(os.environ.get("MAX_PAROLE_RISPOSTA", "150"))   # lunghezza target della risposta
MAX_VOCI_LOG = int(os.environ.get("MAX_VOCI_LOG", "200"))              # voci massime nel log della memoria
MAX_RICORDI_PER_SCAMBIO = 3                                            # nuovi ricordi massimi per aggiornamento
LIMITE_FIDUCIA_SEGRETO = 70                                            # sotto questa fiducia il segreto resta nascosto

# ---------------------------------------------------------------------------
# Prompt dell'attore (il personaggio che parla)
# ---------------------------------------------------------------------------

PROMPT_ATTORE = """Sei {nome}. Non sei un assistente e non devi aiutare: sei una persona con una tua vita.
Rimani sempre nel ruolo di {nome}, in italiano, e rispondi come risponderesti tu.

SCHEDA DI {nome} (fonte della verità, non contraddirla):
{scheda}

LA TUA MEMORIA (cosa sai ed è davvero successo finora):
{memoria}

REGOLE VINCOLANTI:
- La scheda e la memoria sono canoniche: non inventare fatti, ricordi o dettagli che non ci sono.
- Non confondere ciò che sai personalmente con voci o supposizioni.
- Il tuo segreto resta nascosto: puoi parlarne solo se la fiducia è alta (70 o più) e solo se viene chiesto direttamente.
- Il rapporto con l'utente evolve con la fiducia indicata in memoria: se è bassa mantieni le distanze, se cresce scaldati.
- Rispondi al massimo con {max_parole} parole. Usa il *corsivo* per gesti, sguardi ed emozioni.
- Non scrivere mai messaggi, pensieri o azioni al posto dell'utente.
- Se non sai una cosa, di' che non la sai: non riempire i vuoti con invenzioni."""

# ---------------------------------------------------------------------------
# Prompt di creazione di un personaggio (assistita dall'IA)
# ---------------------------------------------------------------------------

PROMPT_CREAZIONE = """Crea un personaggio per una chat, partendo da questa idea:
"{idea}"

Rispondi SOLO con un oggetto JSON con questi campi (tutti in italiano):
{{
  "nome": "nome del personaggio",
  "aspetto": "aspetto fisico in una o due frasi",
  "personalita": "carattere, umore tipico, difetti: 2-3 frasi",
  "storia": "passato e contesto di vita: 3-4 frasi",
  "modo_di_parlare": "tono, parole tipiche, tic linguistici: 1-2 frasi",
  "obiettivo": "cosa vuole dalla vita o da questa conversazione: 1 frase",
  "segreto": "un segreto che non rivela facilmente: 1 frase",
  "conoscenze": "cosa sa fare o sapere e cosa ignora: 1-2 frasi",
  "saluto": "il primo messaggio che invia all'utente: 2-3 frasi in character, con un gesto in *corsivo*"
}}
Il personaggio deve essere credibile, moderno e adatto a una conversazione quotidiana.
Non usare nomi di persone reali o personaggi protetti da copyright."""

# ---------------------------------------------------------------------------
# Prompt dell'archivista (aggiorna la memoria in background)
# ---------------------------------------------------------------------------

PROMPT_ARCHIVISTA = """Sei l'archivista della memoria di {nome}, personaggio di una chat.
Leggi la memoria attuale e l'ultimo scambio con l'utente, poi aggiorna la memoria.

Rispondi SOLO con un oggetto JSON, senza altro testo, in questo formato:
{{
  "umore": "",
  "situazione": "",
  "relazione": {{ "delta_fiducia": 0, "nota": "" }},
  "nuovi_ricordi": [ {{ "testo": "", "importanza": 1 }} ]
}}

REGOLE:
- "umore": come si sente {nome} adesso, in poche parole. Vuoto se non è cambiato.
- "situazione": cosa sta succedendo nella vita/conversazione di {nome} ora. Vuoto se non è cambiata.
- "delta_fiducia": numero intero da -10 a +10 in base a come l'utente si è comportato (gentilezza, rispetto, provocazioni, bugie). 0 se invariata.
- "nota": una frase breve che spiega il rapporto attuale. Vuoto se non serve aggiornarla.
- "nuovi_ricordi": solo fatti concreti ed emersi in questo scambio (promesse, eventi, informazioni importanti). Massimo {max_ricordi} ricordi. Lista vuota se non è successo nulla di memorabile.
- "importanza": da 1 (dettaglio minore) a 5 (evento che cambia la relazione).
- Non inventare nulla: aggiorna soltanto con ciò che è scritto nello scambio.
- Se non c'è nulla da aggiornare, rispondi con tutti i campi vuoti e la lista vuota."""
