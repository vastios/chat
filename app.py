"""Chat Personaggi — interfaccia Streamlit.

Stessa impostazione del vecchio LocalStoryEngine (app.py): barra laterale con
scheda e gestione, area centrale di chat. Cambia il prodotto: non è più un
gioco di ruolo ma una chat con personaggi, e la memoria non è più manuale:
dopo ogni scambio l'archivista aggiorna i file JSON.

Avvio:  streamlit run app.py
"""

import streamlit as st

from config import MODELLO_ARCHIVISTA, MODELLO_ATTORE, BASE_URL
from personaggi import archivista, database
from personaggi import memoria as modulo_memoria
from personaggi import narratore
from personaggi import personaggio as modulo_personaggio
from personaggi.lmstudio import ErroreLMStudio, attivo

st.set_page_config(
    page_title="Chat Personaggi",
    page_icon="💬",
    layout="centered",
)

database.inizializza_archivio()


def etichetta_origine(origine):
    """Etichetta leggibile per l'origine del personaggio."""
    return {
        "demo": "esempio",
        "ia": "creato con l'IA",
        "giocatore": "creato da te",
    }.get(origine, "")


def etichette_personaggi(lista):
    """Mappa etichetta → id per il menu, con etichette sempre univoche."""
    conteggio = {}
    risultato = {}
    for p in lista:
        base = f"{p['nome']} ({etichetta_origine(p.get('origine', ''))})"
        conteggio[base] = conteggio.get(base, 0) + 1
        etichetta = base if conteggio[base] == 1 else f"{base} #{conteggio[base]}"
        risultato[etichetta] = p["id"]
    return risultato


def passa_a_personaggio(id_nuovo):
    """Seleziona un personaggio a codice (dopo la creazione o l'eliminazione)."""
    st.session_state.personaggio_id = id_nuovo
    # Cambiando il contatore, il menu a tendina viene rimontato con la nuova
    # selezione: non si può riscrivere lo stato di un widget già creato, ma
    # si può crearne uno nuovo con l'indice giusto.
    st.session_state.contatore_selettore = st.session_state.get("contatore_selettore", 0) + 1


# ---------------------------------------------------------------------------
# Personaggio di esempio al primo avvio
# ---------------------------------------------------------------------------

def crea_personaggio_demo():
    scheda = {
        "aspetto": "capelli scuri raccolti con una matita, occhi castani, "
                   "grembiule di lino sopra le maniche arrotolate",
        "personalita": "curiosa e diretta ma gentile, ironica quando si sente "
                       "a suo agio, odia i discorsi fatti e le sporcherie di cortesia",
        "storia": "gestisce la piccola libreria di quartiere aperta da sua nonna; "
                  "legge due libri a settimana e organizza il circolo di lettura "
                  "del giovedì sera",
        "modo_di_parlare": "frasi brevi e domande dirette, qualche parola in "
                           "dialetto quando si emoziona",
        "obiettivo": "capire chi ha davvero a cuore la libreria e raccogliere "
                     "le storie delle persone che la frequentano",
        "segreto": "ha rifiutato un lavoro in una grande casa editrice per non "
                   "abbandonare la libreria della nonna",
        "conoscenze": "sa tutto di libri e del quartiere; di tecnologia non capisce quasi niente",
    }
    saluto = ("*posa il libro che stava rilegando e alza gli occhi* Ehilà! "
              "Non ti ho mai visto… o sei uno di quelli che entrano solo per "
              "scaldarsi? *sorride, incuriosita* Dimmi: cerchi un libro o una "
              "conversazione?")
    return database.crea_personaggio(
        "Sofia", scheda, origine="demo", saluto=saluto
    )


# ---------------------------------------------------------------------------
# Stato di sessione
# ---------------------------------------------------------------------------

if "personaggio_id" not in st.session_state:
    st.session_state.personaggio_id = None
if "contatore_selettore" not in st.session_state:
    st.session_state.contatore_selettore = 0
if "archivista_attivo" not in st.session_state:
    st.session_state.archivista_attivo = True
if "nome_utente" not in st.session_state:
    st.session_state.nome_utente = database.carica_impostazioni().get("nome_utente", "")


def id_personaggio_corrente():
    """Restituisce un id valido: il selezionato, oppure il primo disponibile."""
    lista = database.lista_personaggi()
    if not lista:
        return None
    ids = {p["id"] for p in lista}
    if st.session_state.personaggio_id not in ids:
        st.session_state.personaggio_id = lista[0]["id"]
    return st.session_state.personaggio_id


# ---------------------------------------------------------------------------
# Barra laterale
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("💬 Chat Personaggi")
    st.caption("Chat locale con personaggi AI · memoria su JSON · LM Studio")

    if not attivo():
        st.warning(
            "LM Studio non risponde su " + BASE_URL + ". "
            "Apri LM Studio, carica un modello e avvia il server locale "
            "(scheda Developer → Start Server), poi ricarica la pagina."
        )

    lista = database.lista_personaggi()
    if not lista:
        st.session_state.personaggio_id = crea_personaggio_demo()
        lista = database.lista_personaggi()
        st.rerun()

    # --- Selezione del personaggio -------------------------------------------
    opzioni = etichette_personaggi(lista)
    indice = next(
        (i for i, e in enumerate(opzioni) if opzioni[e] == st.session_state.personaggio_id),
        0,
    )
    etichetta_scelta = st.selectbox(
        "Con chi vuoi parlare?",
        list(opzioni.keys()),
        index=indice,
        key=f"selettore_personaggio_{st.session_state.contatore_selettore}",
    )
    st.session_state.personaggio_id = opzioni[etichetta_scelta]

    # --- Nuovo personaggio -----------------------------------------------------
    with st.expander("➕ Nuovo personaggio", expanded=not lista or len(lista) == 1):
        tipo = st.radio(
            "Come crearlo?",
            ["Descrivo un'idea e pensa l'IA", "Lo scrivo io campo per campo"],
            horizontal=False,
            key="tipo_creazione",
        )

        if tipo.startswith("Descrivo"):
            idea = st.text_area(
                "L'idea del personaggio",
                placeholder="Es. un musicista di strada timido ma ragionevolmente cinico",
                key="idea_creazione",
            )
            if st.button("Genera con l'IA", use_container_width=True, key="bottone_ia"):
                if not idea.strip():
                    st.warning("Scrivi prima un'idea, anche di una riga.")
                else:
                    with st.spinner("Creo il personaggio…"):
                        try:
                            nome, scheda, saluto = modulo_personaggio.genera_scheda_con_ia(idea)
                            passa_a_personaggio(database.crea_personaggio(
                                nome, scheda, origine="ia", saluto=saluto
                            ))
                            st.rerun()
                        except (ErroreLMStudio, modulo_personaggio.ErroreCreazione) as errore:
                            st.error(str(errore))
        else:
            with st.form("form_personaggio_manuale"):
                nome_manuale = st.text_input("Nome")
                valori = {}
                for campo, etichetta in modulo_personaggio.CAMPI_SCHEDA:
                    valori[campo] = st.text_area(etichetta, height=60 if campo != "storia" else 90)
                if st.form_submit_button("Crea personaggio", use_container_width=True):
                    scheda = modulo_personaggio.normalizza_scheda(valori)
                    errori = modulo_personaggio.valida_scheda(scheda)
                    if not nome_manuale.strip():
                        st.warning("Il personaggio deve avere un nome.")
                    elif errori:
                        st.warning(" ".join(errori))
                    else:
                        passa_a_personaggio(database.crea_personaggio(
                            nome_manuale.strip(), scheda, origine="giocatore"
                        ))
                        st.rerun()

    pid = id_personaggio_corrente()
    if pid is None:
        st.stop()

    scheda = database.carica_scheda(pid)
    memoria_dati = modulo_memoria.normalizza_memoria(database.carica_memoria(pid))

    # --- Scheda del personaggio corrente -------------------------------------
    with st.expander("🪪 Scheda di " + scheda.get("nome", ""), expanded=True):
        for campo, etichetta in modulo_personaggio.CAMPI_SCHEDA:
            valore = scheda.get(campo, "")
            if valore:
                st.markdown(f"**{etichetta}:** {valore}")
        with st.expander("✏️ Modifica la scheda"):
            with st.form("form_modifica_scheda"):
                nuovi_valori = {}
                for campo, etichetta in modulo_personaggio.CAMPI_SCHEDA:
                    nuovi_valori[campo] = st.text_area(
                        etichetta, value=scheda.get(campo, ""), height=60
                    )
                if st.form_submit_button("Salva scheda", use_container_width=True):
                    scheda.update(modulo_personaggio.normalizza_scheda(nuovi_valori))
                    database.salva_scheda(pid, scheda)
                    st.rerun()

    # --- Memoria ---------------------------------------------------------------
    with st.expander("🧠 Memoria (file JSON aggiornati dall'IA)", expanded=True):
        if memoria_dati["umore"]:
            st.markdown(f"**Umore:** {memoria_dati['umore']}")
        if memoria_dati["situazione"]:
            st.markdown(f"**Situazione:** {memoria_dati['situazione']}")

        fiducia = memoria_dati["relazione"]["fiducia"]
        st.progress(fiducia / 100, text=f"Fiducia: {fiducia}/100")
        if memoria_dati["relazione"]["nota"]:
            st.caption(memoria_dati["relazione"]["nota"])

        st.markdown("**Ricordi**")
        if memoria_dati["ricordi"]:
            for ricordo in sorted(
                memoria_dati["ricordi"], key=lambda r: (r["importanza"], r["data"]), reverse=True
            ):
                st.markdown(f"- *[{ricordo['importanza']}/5]* {ricordo['testo']}")
        else:
            st.caption("Nessun ricordo per ora: si formano chiacchierando.")

        with st.form("form_ricordo_manuale"):
            testo_ricordo = st.text_area("Aggiungi un ricordo a mano")
            importanza = st.slider("Importanza", 1, 5, 3, key="slider_importanza")
            if st.form_submit_button("Salva ricordo", use_container_width=True):
                if testo_ricordo.strip():
                    modulo_memoria.aggiungi_ricordo_manuale(pid, testo_ricordo, importanza)
                    st.rerun()
                else:
                    st.warning("Scrivi prima il testo del ricordo.")

        with st.form("form_relazione_manuale"):
            delta = st.number_input(
                "Variazione fiducia (es. -20 o +20)", min_value=-100, max_value=100, value=0, step=5
            )
            nota_relazione = st.text_input(
                "Nota sulla relazione (facoltativa)",
                value=memoria_dati["relazione"]["nota"],
            )
            if st.form_submit_button("Aggiorna relazione", use_container_width=True):
                if delta:
                    modulo_memoria.modifica_fiducia_manuale(pid, int(delta), nota_relazione or None)
                    st.rerun()

        if st.button("↩️ Annulla ultima modifica della memoria", use_container_width=True):
            if database.annulla_ultima_modifica(pid):
                st.rerun()
            else:
                st.info("Non c'è nessuna modifica da annullare.")

    # --- Impostazioni e manutenzione ------------------------------------------
    st.session_state.archivista_attivo = st.toggle(
        "Memoria automatica (archivista)",
        value=st.session_state.archivista_attivo,
        help="Dopo ogni scambio, "
             f"il modello {MODELLO_ARCHIVISTA or 'caricato in LM Studio'} aggiorna umore, "
             "situazione, fiducia e ricordi. Puoi disattivarlo e gestire tutto a mano.",
    )

    nuovo_nome_utente = st.text_input(
        "Il tuo nome",
        value=st.session_state.nome_utente,
        key="input_nome_utente",
    )
    if nuovo_nome_utente != st.session_state.nome_utente:
        st.session_state.nome_utente = nuovo_nome_utente.strip()
        database.salva_impostazioni({"nome_utente": st.session_state.nome_utente})

    st.divider()
    colonna_a, colonna_b = st.columns(2)
    with colonna_a:
        if st.button("🧹 Cronologia", use_container_width=True):
            database.svuota_conversazione(pid)
            st.rerun()
    with colonna_b:
        conferma = st.checkbox("Confermo", key="conferma_eliminazione")
        if st.button("🗑️ Elimina personaggio", use_container_width=True, disabled=not conferma):
            database.elimina_personaggio(pid)
            passa_a_personaggio(None)
            st.rerun()

    st.caption(
        "Modelli: attore "
        f"`{MODELLO_ATTORE or 'automatico'}` · archivista "
        f"`{MODELLO_ARCHIVISTA or 'automatico'}` · server LM Studio `{BASE_URL}`"
    )


# ---------------------------------------------------------------------------
# Area di chat
# ---------------------------------------------------------------------------

nome_personaggio = scheda.get("nome", "Personaggio")
st.header("💬 " + nome_personaggio)
prima_frase = scheda.get("aspetto") or scheda.get("personalita") or ""
if prima_frase:
    st.caption(prima_frase)
st.divider()

conversazione = database.carica_conversazione(pid)
for voce in conversazione.get("messaggi", []):
    avatar = "user" if voce.get("ruolo") == "utente" else None
    with st.chat_message(
        "user" if voce.get("ruolo") == "utente" else "assistant",
        avatar=avatar if avatar else "🪄",
    ):
        st.markdown(voce.get("testo", ""))

prompt = st.chat_input("Scrivi a " + nome_personaggio + "…")

if prompt:
    nome_utente = st.session_state.nome_utente.strip()
    database.aggiungi_messaggio(pid, "utente", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    scheda_fresca = database.carica_scheda(pid)
    memoria_fresca = modulo_memoria.normalizza_memoria(database.carica_memoria(pid))
    conversazione_fresca = database.carica_conversazione(pid)

    with st.chat_message("assistant", avatar="🪄"):
        try:
            risposta = st.write_stream(
                narratore.genera_risposta(
                    scheda_fresca, memoria_fresca, conversazione_fresca, nome_utente
                )
            )
        except ErroreLMStudio as errore:
            st.error(str(errore))
            st.stop()

    database.aggiungi_messaggio(pid, "personaggio", risposta)

    if st.session_state.archivista_attivo:
        with st.spinner("🧠 " + nome_personaggio + " aggiorna la memoria…"):
            cambiamenti = archivista.aggiorna_memoria(pid, nome_utente)
        if cambiamenti:
            st.toast("Memoria aggiornata: " + " · ".join(cambiamenti[:3]), icon="🧠")

    st.rerun()
