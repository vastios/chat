"""Chat Personaggi — interfaccia Streamlit.

Organizzazione delle schermate:
- MENU  : punto d'ingresso. Si sceglie se continuare un roleplay iniziato,
          crearne uno nuovo o provare il tutorial con Sofia, il personaggio
          d'esempio.
- NUOVO : creazione di un personaggio, con l'IA o campo per campo.
- APP   : il roleplay vero e proprio, con tre linguette in alto:
          💬 Gioco (la chat) · 🪪 Personaggio (scheda e memoria) ·
          🗺️ Luoghi (predisposta, in arrivo).

La barra laterale tiene le impostazioni generali (tuo nome, memoria
automatica). Il salvataggio non cambia: tutto resta nei file JSON che
l'archivista aggiorna dopo ogni scambio.

Avvio:  streamlit run app.py
"""

from datetime import datetime

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


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------

ORIGINI = {
    "demo": ("esempio", "🎓"),
    "ia": ("creato con l'IA", "✨"),
    "giocatore": ("creato da te", "🙋"),
}


def etichetta_origine(origine):
    """Etichetta leggibile per l'origine del personaggio."""
    return ORIGINI.get(origine, ("", "🪄"))[0]


def emoji_origine(origine):
    """Emoji associata all'origine del personaggio."""
    return ORIGINI.get(origine, ("", "🪄"))[1]


def formatta_data(iso):
    """Trasforma '2026-11-06T10:31:22' in 'oggi alle 10:31', 'ieri…', '6 giorni fa'…"""
    if not iso:
        return "mai"
    try:
        momento = datetime.fromisoformat(str(iso))
    except ValueError:
        return "mai"
    differenza = (datetime.now().date() - momento.date()).days
    ora = momento.strftime("%H:%M")
    if differenza <= 0:
        return f"oggi alle {ora}"
    if differenza == 1:
        return f"ieri alle {ora}"
    if differenza < 7:
        return f"{differenza} giorni fa"
    return momento.strftime("%d/%m/%Y")


def apri_roleplay(id_personaggio, tutorial=False):
    """Apre il roleplay di un personaggio (dalla lista o dopo la creazione)."""
    st.session_state.personaggio_id = id_personaggio
    st.session_state.schermata = "app"
    st.session_state.tutorial_attivo = bool(tutorial)


def vai_al_menu():
    """Torna alla schermata iniziale senza toccare nessun dato."""
    st.session_state.schermata = "menu"


def trova_demo():
    """Cerca il personaggio d'esempio (Sofia) tra quelli esistenti."""
    for p in database.lista_personaggi():
        if p.get("origine") == "demo":
            return p["id"]
    return None


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

if "schermata" not in st.session_state:
    st.session_state.schermata = "menu"
if "personaggio_id" not in st.session_state:
    st.session_state.personaggio_id = None
if "tutorial_attivo" not in st.session_state:
    st.session_state.tutorial_attivo = False
if "archivista_attivo" not in st.session_state:
    st.session_state.archivista_attivo = True
if "nome_utente" not in st.session_state:
    st.session_state.nome_utente = database.carica_impostazioni().get("nome_utente", "")


# ---------------------------------------------------------------------------
# Barra laterale: impostazioni generali
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

    st.caption(
        "Modelli: attore "
        f"`{MODELLO_ATTORE or 'automatico'}` · archivista "
        f"`{MODELLO_ARCHIVISTA or 'automatico'}` · server LM Studio `{BASE_URL}`"
    )


# ---------------------------------------------------------------------------
# Schermata MENU
# ---------------------------------------------------------------------------

def schermata_menu():
    st.title("💬 Chat Personaggi")
    st.caption("Storie che continuano: ogni personaggio ricorda te e quanto vissuto insieme.")

    elenco = database.lista_personaggi()

    if elenco:
        st.subheader("▶️ Continua un roleplay")
        for p in elenco:
            with st.container(border=True):
                col_testo, col_apri = st.columns([4, 1])
                with col_testo:
                    riga_descrizione = (
                        f"{emoji_origine(p.get('origine', ''))} {etichetta_origine(p.get('origine', ''))}"
                        or "🪄 roleplay"
                    ).strip()
                    st.markdown(f"**{p['nome']}**")
                    st.caption(
                        riga_descrizione
                        + " · ultimo scambio: "
                        + formatta_data(p.get("aggiornato_il"))
                    )
                with col_apri:
                    st.write("")
                    if st.button(
                        "Apri",
                        key=f"apri_{p['id']}",
                        use_container_width=True,
                        type="primary",
                    ):
                        apri_roleplay(p["id"])
                        st.rerun()

    st.subheader("✨ Nuovo roleplay")
    st.caption("Descrivi un'idea e lo compone l'IA, oppure scrivilo tu campo per campo.")
    if st.button("➕ Crea un nuovo personaggio", use_container_width=True, key="bottone_nuovo"):
        st.session_state.schermata = "nuovo"
        st.rerun()

    st.subheader("🎓 Tutorial")
    st.caption(
        "Cinque minuti con Sofia, il personaggio d'esempio, per scoprire come "
        "funzionano le risposte, la memoria e la fiducia."
    )
    if st.button("🎓 Prova il tutorial", use_container_width=True, key="bottone_tutorial"):
        id_demo = trova_demo()
        if id_demo is None:
            id_demo = crea_personaggio_demo()
        apri_roleplay(id_demo, tutorial=True)
        st.rerun()


# ---------------------------------------------------------------------------
# Schermata NUOVO personaggio
# ---------------------------------------------------------------------------

def schermata_nuovo():
    col_titolo, col_menu = st.columns([5, 1])
    with col_titolo:
        st.header("✨ Nuovo roleplay")
    with col_menu:
        st.write("")
        if st.button("⬅️ Menu", use_container_width=True, key="bottone_menu_da_nuovo"):
            vai_al_menu()
            st.rerun()

    st.caption("Il personaggio nasce con la sua scheda, la sua memoria e un saluto d'apertura.")

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
        if st.button("Genera con l'IA", use_container_width=True, type="primary", key="bottone_ia"):
            if not idea.strip():
                st.warning("Scrivi prima un'idea, anche di una riga.")
            else:
                with st.spinner("Creo il personaggio…"):
                    try:
                        nome, scheda, saluto = modulo_personaggio.genera_scheda_con_ia(idea)
                        apri_roleplay(database.crea_personaggio(
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
                    apri_roleplay(database.crea_personaggio(
                        nome_manuale.strip(), scheda, origine="giocatore"
                    ))
                    st.rerun()


# ---------------------------------------------------------------------------
# Schermata APP: le tre linguette
# ---------------------------------------------------------------------------

def schermata_app():
    pid = st.session_state.personaggio_id
    if not pid or database.trova_personaggio(pid) is None:
        # Il personaggio non esiste più (eliminato altrove): torna al menu.
        vai_al_menu()
        st.rerun()
        return

    scheda = database.carica_scheda(pid)
    memoria_dati = modulo_memoria.normalizza_memoria(database.carica_memoria(pid))
    nome_personaggio = scheda.get("nome", "Personaggio")

    col_titolo, col_menu = st.columns([5, 1])
    with col_titolo:
        st.header("💬 " + nome_personaggio)
        prima_frase = scheda.get("aspetto") or scheda.get("personalita") or ""
        if prima_frase:
            st.caption(prima_frase)
    with col_menu:
        st.write("")
        if st.button("⬅️ Menu", use_container_width=True, key="bottone_menu_da_app"):
            vai_al_menu()
            st.rerun()

    tab_gioco, tab_personaggio, tab_luoghi = st.tabs(
        ["💬 Gioco", "🪪 Personaggio", "🗺️ Luoghi"]
    )

    with tab_gioco:
        if st.session_state.tutorial_attivo:
            with st.container(border=True):
                st.markdown("### 🎓 Benvenuto! Questo è un tutorial di cinque minuti")
                st.markdown(
                    "1. **Scrivi qui sotto**: Sofia ti risponde da sé, restando in character.\n"
                    "2. Apri la linguetta **🪪 Personaggio**: dopo ogni scambio la sua "
                    "memoria (umore, fiducia, ricordi) si aggiorna da sola.\n"
                    "3. Sofia ha un **segreto** in scheda: lo rivelerà solo se la fiducia "
                    "arriva a 70 o più. Gentilezza si paga.\n"
                    "4. Hai sbagliato qualcosa? In 🪪 Personaggio trovi "
                    "**↩️ Annulla ultima modifica della memoria**."
                )
                if st.button("Ho capito, iniziamo!", type="primary", key="bottone_fine_tutorial"):
                    st.session_state.tutorial_attivo = False
                    st.rerun()

        conversazione = database.carica_conversazione(pid)
        for voce in conversazione.get("messaggi", []):
            avatar = "user" if voce.get("ruolo") == "utente" else "🪄"
            with st.chat_message(
                "user" if voce.get("ruolo") == "utente" else "assistant",
                avatar=avatar,
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

    with tab_personaggio:
        st.markdown("**Scheda di " + nome_personaggio + "** (fonte canonica del personaggio)")
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

        st.divider()
        st.markdown("**🧠 Memoria** (i file JSON aggiornati dall'archivista)")
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

        colonna_ricordo, colonna_relazione = st.columns(2)
        with colonna_ricordo:
            with st.form("form_ricordo_manuale"):
                testo_ricordo = st.text_area("Aggiungi un ricordo a mano")
                importanza = st.slider("Importanza", 1, 5, 3, key="slider_importanza")
                if st.form_submit_button("Salva ricordo", use_container_width=True):
                    if testo_ricordo.strip():
                        modulo_memoria.aggiungi_ricordo_manuale(pid, testo_ricordo, importanza)
                        st.rerun()
                    else:
                        st.warning("Scrivi prima il testo del ricordo.")
        with colonna_relazione:
            with st.form("form_relazione_manuale"):
                delta = st.number_input(
                    "Variazione fiducia (es. -20 o +20)", min_value=-100, max_value=100,
                    value=0, step=5,
                )
                nota_relazione = st.text_input(
                    "Nota sulla relazione (facoltativa)",
                    value=memoria_dati["relazione"]["nota"],
                )
                if st.form_submit_button("Aggiorna relazione", use_container_width=True):
                    if delta:
                        modulo_memoria.modifica_fiducia_manuale(
                            pid, int(delta), nota_relazione or None
                        )
                        st.rerun()

        if st.button("↩️ Annulla ultima modifica della memoria", use_container_width=True):
            if database.annulla_ultima_modifica(pid):
                st.rerun()
            else:
                st.info("Non c'è nessuna modifica da annullare.")

        st.divider()
        st.markdown("**Manutenzione**")
        colonna_cron, colonna_elim = st.columns(2)
        with colonna_cron:
            if st.button("🧹 Svuota cronologia", use_container_width=True,
                         help="Cancella i messaggi ma non la memoria."):
                database.svuota_conversazione(pid)
                st.rerun()
        with colonna_elim:
            conferma = st.checkbox("Confermo l'eliminazione", key="conferma_eliminazione")
            if st.button("🗑️ Elimina personaggio", use_container_width=True,
                         disabled=not conferma):
                database.elimina_personaggio(pid)
                vai_al_menu()
                st.rerun()

    with tab_luoghi:
        st.info(
            "🚧 **Gestione dei luoghi — in arrivo**\n\n"
            "Qui potrai definire i posti della vita del personaggio (casa, lavoro, "
            "i luoghi dove la storia si svolge) e usarli nelle conversazioni. "
            "È l'idea che nel vecchio LocalStoryEngine era in `world.py`, adattata "
            "a una chat di personaggi.",
            icon="🗺️",
        )


# ---------------------------------------------------------------------------
# Rotte
# ---------------------------------------------------------------------------

if st.session_state.schermata == "nuovo":
    schermata_nuovo()
elif st.session_state.schermata == "app":
    schermata_app()
else:
    schermata_menu()
