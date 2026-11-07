"""Chat Personaggi — interfaccia Streamlit.

Organizzazione delle schermate:
- MENU  : punto d'ingresso. Si sceglie se continuare un roleplay iniziato,
          crearne uno nuovo o provare il tutorial con Sofia, il personaggio
          d'esempio.
- NUOVO : creazione di un personaggio, con l'IA o campo per campo.
- APP   : il roleplay vero e proprio. In alto, al centro, il titolo della
          chat; subito sotto una riga d'informazioni sul personaggio
          (origine, umore, fiducia, messaggi, ultimo scambio); ancora
          sotto la barra delle linguette a bottone — ⬅️ Menu, 💬 Gioco,
          🪪 Personaggio, 🗺️ Luoghi — pronta ad accoglierne di nuove
          (basta aggiungerle a LINGUETTE_APP).

Nella linguetta Gioco lo schermo è diviso in due pannelli con cornice
propria, larghi quanto tutto lo schermo: a sinistra la chat con bolle
tonde per i dialoghi e riquadri tratteggiati per le azioni scritte in
*asterischi* — ogni PNG ha il suo colore, che è anche il colore del suo
nome nei selettori —; a destra in alto la 🛠️ Regia, la chat di servizio
con la macchina (nuovi PNG che entrano in scena, uscite, aggiornamenti
della memoria da confermare), e in basso i selettori: i PNG in scena con
i nomi colorati, la tendina per far entrare un PNG esistente, il bottone
➕ Nuovo PNG (entra nella scena attuale, non apre una chat a parte), il
cambio roleplay e i luoghi.

Il roleplay può avere più PNG in scena: quando ne partecipano più di
uno, l'attore scrive le battute di tutti (una per riga, col nome davanti)
e l'app le spezza in bolle colorate per personaggio.

La pagina resta fissa alle dimensioni dello schermo: a muoversi sono solo
la conversazione e la regia, ognuna dentro il proprio pannello.

La barra laterale tiene le impostazioni generali (tuo nome, memoria
automatica). Il salvataggio non cambia: tutto resta nei file JSON che
l'archivista aggiorna dopo ogni scambio.

Avvio:  streamlit run app.py
"""

import html as modulo_html
import re
from contextlib import contextmanager
from datetime import datetime

import streamlit as st
from streamlit.components.v1 import html as html_js

from config import MODELLO_ARCHIVISTA, MODELLO_ATTORE, MODELLO_REGIA, BASE_URL
from personaggi import archivista, database
from personaggi import memoria as modulo_memoria
from personaggi import narratore
from personaggi import personaggio as modulo_personaggio
from personaggi import regia as modulo_regia
from personaggi.lmstudio import ErroreLMStudio, attivo

st.set_page_config(
    page_title="Chat Personaggi",
    page_icon="💬",
    layout="wide",
)

database.inizializza_archivio()

# Chrome di Streamlit ridotto all'osso su tutte le schermate: la barra in
# alto diventa una striscia trasparente e bassa, senza menù né indicatori
# (il bottone per riaprire la barra laterale resta usabile, sta nel
# toolbar che appare solo quando serve) e il contenuto parte subito sotto.
CSS_BASE = """
<style>
[data-testid="stHeader"] {
  background: transparent !important;
  height: 1.6rem !important; min-height: 0 !important;
  border: none !important; box-shadow: none !important;
  overflow: visible !important;
}
[data-testid="stMainMenu"], [data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"] {
  display: none !important;
}
[data-testid="stMainBlockContainer"] { padding-top: 0.9rem !important; }
</style>
"""
st.markdown(CSS_BASE, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------

ORIGINI = {
    "demo": ("esempio", "🎓"),
    "ia": ("creato con l'IA", "✨"),
    "giocatore": ("creato da te", "🙋"),
}

# Linguette della schermata di gioco: per aggiungerne una in futuro basta
# una nuova voce qui e un ramo `elif` più sotto: la barra a bottone si
# adatta da sola.
LINGUETTE_APP = [
    ("gioco", "💬 Gioco"),
    ("personaggio", "🪪 Personaggio"),
    ("luoghi", "🗺️ Luoghi"),
]


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
    st.session_state.linguetta = "gioco"


def vai_al_menu():
    """Torna alla schermata iniziale senza toccare nessun dato."""
    st.session_state.schermata = "menu"
    # Se la creazione era partita da un roleplay aperto, quel proposito
    # scade tornando al menu: il prossimo PNG creato apre la sua chat.
    st.session_state.pop("entrata_in_scena", None)


def dopo_creazione(id_nuovo, nome_nuovo=""):
    """Dopo la creazione di un PNG.

    Se la creazione è partita da un roleplay aperto (bottone ➕ Nuovo PNG
    nei selettori) il nuovo personaggio entra nella scena attuale — nessuna
    chat a parte — e si torna al roleplay di provenienza. Se invece nasce
    dal menu, si apre direttamente il suo roleplay come sempre.
    """
    destinazione = st.session_state.pop("entrata_in_scena", None)
    if destinazione and database.trova_personaggio(destinazione):
        database.aggiungi_in_scena(destinazione, id_nuovo)
        apri_roleplay(destinazione)
        st.toast("🎭 " + (nome_nuovo or "Nuovo PNG") + " è entrato in scena.", icon="🎭")
    else:
        apri_roleplay(id_nuovo)


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
# Scena: chi è in scena e i colori dei PNG
# ---------------------------------------------------------------------------

# Palette delle bolle per i PNG: tonalità pastello, testo sempre leggibile.
# L'azzurro resta all'utente: nella palette non ci sono blu pieni.
PALETTE_PNG = [
    {"sfondo": "#fbe3e4", "bordo": "#dca3ab", "tema": "#a34752"},   # rosa cipria
    {"sfondo": "#e2f0e4", "bordo": "#a3c9ab", "tema": "#3e7a55"},   # verde salvia
    {"sfondo": "#ece6fa", "bordo": "#b3a6de", "tema": "#67599f"},   # lavanda
    {"sfondo": "#ffeadb", "bordo": "#e2b28c", "tema": "#b06b3b"},   # pesca
    {"sfondo": "#fbf3d2", "bordo": "#d8c06a", "tema": "#8a741f"},   # giallo burro
    {"sfondo": "#dcf1ea", "bordo": "#9ecfc0", "tema": "#2f8471"},   # menta
    {"sfondo": "#f2e7d9", "bordo": "#c8ab8c", "tema": "#8a6d4b"},   # sabbia
    {"sfondo": "#eceff4", "bordo": "#b3bfce", "tema": "#5a7089"},   # grigio tenue
]


def carica_scena(pid):
    """I PNG in scena con nome, colore e ruolo (proprietario o ospite).

    I colori mancanti vengono assegnati con la prima tinta libera della
    palette e salvati nella conversazione: restano stabili nel tempo.
    Chi è stato eliminato dall'archivio viene tolto dalla scena.
    """
    in_scena, colori = database.carica_scena(pid)
    validi = [pid] + [
        voce for voce in in_scena
        if voce != pid and database.trova_personaggio(voce)
    ]
    if validi != in_scena:
        database.salva_scena(pid, validi)
        in_scena = validi
    tinte = {voce["sfondo"] for voce in PALETTE_PNG}
    usate = {colori.get(voce) for voce in in_scena if colori.get(voce) in tinte}
    cambiati = False
    for id_png in in_scena:
        if colori.get(id_png) not in tinte:
            libero = next(
                (voce["sfondo"] for voce in PALETTE_PNG if voce["sfondo"] not in usate),
                PALETTE_PNG[len(usate) % len(PALETTE_PNG)]["sfondo"],
            )
            colori[id_png] = libero
            usate.add(libero)
            cambiati = True
    if cambiati:
        database.salva_scena(pid, in_scena, colori)
    nomi = {p["id"]: p.get("nome", "?") for p in database.lista_personaggi()}
    scena = []
    for id_png in in_scena:
        tinta = next(
            (voce for voce in PALETTE_PNG if voce["sfondo"] == colori[id_png]),
            PALETTE_PNG[0],
        )
        scena.append({
            "id": id_png,
            "nome": nomi.get(id_png, id_png),
            "sfondo": tinta["sfondo"],
            "bordo": tinta["bordo"],
            "tema": tinta["tema"],
            "proprietario": id_png == pid,
        })
    return scena


def css_scena(scena):
    """Stile delle bolle per i PNG in scena: ogni personaggio la sua tinta."""
    blocchi = []
    for voce in scena:
        blocchi.append(
            f".chat-bolle .bolla.pg.p-{voce['id']} {{ "
            f"background:{voce['sfondo']}; border-color:{voce['bordo']}; }}"
        )
        blocchi.append(
            f".chat-bolle .bolla.azioni.p-{voce['id']} {{ "
            f"border-color:{voce['bordo']}; background:{voce['sfondo']}59; }}"
        )
    return "<style>\n" + "\n".join(blocchi) + "\n</style>"


def chip_scena_html(scena):
    """Chips dei PNG in scena: nome colorato con la tinta delle sue bolle."""
    pezzi = ['<div class="chips-scena">']
    for voce in scena:
        stella = " 🌟" if voce["proprietario"] else ""
        pezzi.append(
            f'<span class="chip-png" style="background:{voce["sfondo"]}66;'
            f'border-color:{voce["bordo"]}">'
            f'<span class="punto" style="background:{voce["tema"]}"></span>'
            f'<span style="color:{voce["tema"]};font-weight:700">'
            + modulo_html.escape(voce["nome"]) + "</span>" + stella + "</span>"
        )
    pezzi.append("</div>")
    return "".join(pezzi)


# ---------------------------------------------------------------------------
# Aspetto della chat: bolle di dialogo e riquadri d'azione
# ---------------------------------------------------------------------------

CSS_GIOCO = """
<style>
.chat-bolle { display:flex; flex-direction:column; gap:10px; padding:6px 2px 12px; }
.chat-bolle .riga { display:flex; flex-direction:column; max-width:84%; }
.chat-bolle .riga.destra { align-self:flex-end; align-items:flex-end; }
.chat-bolle .riga.sinistra { align-self:flex-start; align-items:flex-start; }
.chat-bolle .riga.centro { align-self:center; align-items:center; max-width:72%; }
.chat-bolle .autore { font-size:0.72rem; opacity:0.55; margin:0 8px 2px; }
.chat-bolle .bolla { padding:9px 14px; line-height:1.5; overflow-wrap:break-word; max-width:720px; }
.chat-bolle .bolla.pg {
  background:rgba(134,142,150,0.15); border:1px solid rgba(134,142,150,0.35);
  border-radius:16px 16px 16px 4px;
}
.chat-bolle .bolla.ut {
  background:rgba(88,131,242,0.16); border:1px solid rgba(88,131,242,0.40);
  border-radius:16px 16px 4px 16px;
}
.chat-bolle .bolla.azioni {
  background:transparent; border:1px dashed rgba(134,142,150,0.55);
  border-radius:4px; font-style:italic; opacity:0.92; text-align:center;
  padding:6px 14px; font-size:0.94em;
}
.chat-bolle .bolla .az { font-style:italic; opacity:0.65; }
/* Chips dei PNG in scena (zona selettori). */
.chips-scena { display:flex; flex-wrap:wrap; gap:6px; margin:0 0 10px; }
.chip-png {
  display:inline-flex; align-items:center; gap:6px;
  padding:3px 10px; border-radius:999px;
  border:1.5px solid rgba(134,142,150,0.4); background:rgba(134,142,150,0.08);
  font-size:0.88rem; line-height:1.4;
}
.chip-png .punto { width:9px; height:9px; border-radius:50%; display:inline-block; }
</style>
"""

# La pagina occupa esattamente lo schermo: nessuno scroll sull'app,
# scrollano soltanto i pannelli di conversazione (chat, regia e il
# contenuto delle linguette secondarie dentro il proprio spazio).
CSS_PAGINA_FISSA = """
<style>
[data-testid="stMain"] {
  height: 100vh; height: 100dvh;
  overflow: hidden !important;
  display: flex !important; flex-direction: column !important;
}
[data-testid="stMainBlockContainer"] {
  flex: 1 1 auto !important; min-height: 0 !important;
  max-width: none !important;
  padding: 0.5rem 1.1rem 0.7rem !important;
  overflow: hidden !important;
  display: flex !important; flex-direction: column !important;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
  flex: 1 1 auto !important; min-height: 0 !important;
  gap: 0.4rem !important;
}
/* Le righe sopra le colonne (titolo, info, linguette, banner tutorial)
   non si lasciano schiacciare quando lo spazio manca: lo assorbono solo
   i pannelli di conversazione. */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] {
  flex-shrink: 0 !important;
}

/* Intestazione della chat: titolo al centro, sotto una riga d'info.
   Le emoji di Streamlit sono immagini: tenute basse per non far uscire
   il titolo dalla sua riga e sovrapporsi alle informazioni. */
.titolo-chat {
  text-align: center !important;
  font-size: 1.8rem !important;
  line-height: 1.25 !important;
  margin: 0 !important; padding: 0 !important;
}
.titolo-chat img {
  height: 1.1em !important; width: 1.1em !important;
  vertical-align: -0.12em !important;
}
.riga-info {
  text-align: center !important;
  font-size: 0.86rem !important;
  line-height: 1.5 !important;
  opacity: 0.8;
  margin: 0 !important;
}
.riga-info img {
  height: 1em !important; width: 1em !important;
  vertical-align: -0.12em !important;
}
/* Streamlit compensa il suo gap di 1rem con un margine negativo sotto
   ogni markdown; con il gap ridotto a 0.4rem il margine fa sovrapporre
   il titolo alla riga d'informazioni: annullato su queste due righe. */
[data-testid="stMarkdown"]:has(.titolo-chat) > div > [data-testid="stMarkdownContainer"],
[data-testid="stMarkdown"]:has(.riga-info) > div > [data-testid="stMarkdownContainer"] {
  margin-bottom: 0 !important;
}

/* Pannello della linguetta attiva (Personaggio, Luoghi): il suo guscio
   (figlio diretto del blocco pagina) riempie lo spazio restante e dentro
   il blocco verticale del pannello scrolla. L'ancora #pannello-secondario
   resta invece un segnaposto basso, altrimenti spingerebbe il contenuto
   in fondo al pannello. */
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:has(#pannello-secondario),
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]:has(#pannello-secondario) {
  flex: 1 1 auto !important; min-height: 0 !important;
  display: flex !important; flex-direction: column !important;
}
[data-testid="stVerticalBlock"]:has(#pannello-secondario) {
  height: auto !important; max-height: none !important;
  flex: 1 1 auto !important; min-height: 0 !important;
  overflow-y: auto !important;
}

/* Schermata di gioco: le due colonne (chat e regia) a tutta altezza. */
[data-testid="stHorizontalBlock"]:has(#fine-chat),
[data-testid="stHorizontalBlock"]:has(#fine-regia) {
  flex: 1 1 auto !important; min-height: 0 !important;
}
[data-testid="stColumn"]:has(#fine-chat),
[data-testid="stColumn"]:has(#fine-regia) {
  display: flex !important; flex-direction: column !important;
  flex: 1 1 auto !important; min-height: 0 !important;
  height: 100% !important; align-self: stretch !important;
}
[data-testid="stColumn"]:has(#fine-chat) > [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(#fine-regia) > [data-testid="stVerticalBlock"] {
  flex: 1 1 auto !important; min-height: 0 !important;
}
[data-testid="stElementContainer"]:has(#fine-chat),
[data-testid="stElementContainer"]:has(#fine-regia),
[data-testid="stLayoutWrapper"]:has(#fine-chat),
[data-testid="stLayoutWrapper"]:has(#fine-regia) {
  display: flex !important; flex-direction: column !important;
  flex: 1 1 auto !important; min-height: 0 !important;
}
/* La regia non si stringe mai sotto una quota usabile: se lo schermo è
   molto basso, la colonna destra scrolla dentro se stessa. */
[data-testid="stColumn"] [data-testid="stLayoutWrapper"]:has(#fine-regia) {
  min-height: 260px !important;
}
[data-testid="stVerticalBlock"]:has(#fine-chat),
[data-testid="stVerticalBlock"]:has(#fine-regia) {
  height: auto !important; max-height: none !important;
  flex: 1 1 auto !important; min-height: 0 !important;
  overflow-y: auto !important;
}

/* ---- Larghezza piena e pannelli nettamente separati ----------------
   Il contenuto non ha più limiti di larghezza; il fondo della pagina è
   grigino e le due metà del gioco diventano due pannelli con cornice,
   fondo e ombra propri: visivamente indipendenti anche su schermi molto
   larghi. */
[data-testid="stMain"] { background: #eef0f4 !important; }
[data-testid="stColumn"]:has(#fine-chat),
[data-testid="stColumn"]:has(#fine-regia) {
  box-sizing: border-box !important;
  border: 1px solid rgba(62,68,80,0.30) !important;
  border-radius: 18px !important;
  box-shadow: 0 3px 14px rgba(20,24,32,0.07) !important;
  padding: 0.7rem 1rem 0.8rem !important;
}
[data-testid="stColumn"]:has(#fine-chat) { background: #ffffff !important; }
[data-testid="stColumn"]:has(#fine-regia) { background: #f4f5f9 !important; }

/* Intestazioni dei pannelli: fisse in cima, non si schiacciano quando
   lo spazio manca. */
[data-testid="stElementContainer"]:has(.titolo-pannello) {
  flex-shrink: 0 !important;
}
.titolo-pannello {
  font-size: 0.95rem !important;
  font-weight: 700 !important;
  opacity: 0.72;
  margin: 0 !important;
  padding: 0 2px 8px !important;
}
.titolo-pannello img {
  height: 1em !important; width: 1em !important;
  vertical-align: -0.12em !important;
}

/* Barra Menu + linguette: centrata sotto il titolo e compatta anche su
   schermi molto larghi. L'ancora invisibile la identifica nel CSS senza
   aggiungere spazio tra i bottoni. */
[data-testid="stHorizontalBlock"]:has(#barra-linguette) {
  max-width: 800px !important;
  margin-left: auto !important; margin-right: auto !important;
}
[data-testid="stHorizontalBlock"]:has(#barra-linguette) [data-testid="stColumn"] [data-testid="stVerticalBlock"] {
  gap: 0 !important;
}
[data-testid="stMarkdown"]:has(#barra-linguette) > div > [data-testid="stMarkdownContainer"] {
  margin-bottom: 0 !important;
}

/* Linguette secondarie (Personaggio, Luoghi): un pannello centrato con
   la stessa cornice delle metà della schermata di gioco, così ogni parte
   dell'app ha il suo spazio ben delimitato. Il guscio è il LayoutWrapper
   del container di pannello_scrollabile(): solo lui contiene l'ancora
   #pannello-secondario tra i discendenti, il blocco pagina no. */
[data-testid="stLayoutWrapper"]:has(#pannello-secondario) {
  box-sizing: border-box !important;
  background: #ffffff !important;
  border: 1px solid rgba(62,68,80,0.30) !important;
  border-radius: 18px !important;
  box-shadow: 0 3px 14px rgba(20,24,32,0.07) !important;
  padding: 0.9rem 1.3rem 1.1rem !important;
  max-width: 1040px !important;
  margin-left: auto !important; margin-right: auto !important;
  flex: 1 1 auto !important; min-height: 0 !important;
  display: flex !important; flex-direction: column !important;
}
</style>
"""

CSS_SCHERMI_STRETTI = (
    "<style>[data-testid='stMainBlockContainer'],[data-testid='block-container']"
    "{max-width:1040px;margin-left:auto;margin-right:auto;}</style>"
)

JS_AUTOSCROLL = """
<script>
(function() {
  var doc = window.parent.document;
  var marche = doc.querySelectorAll('[id^="fine-"]');
  var scatole = [];
  marche.forEach(function(marca) {
    var el = marca.parentElement;
    while (el) {
      var stile = window.parent.getComputedStyle(el);
      if (stile.overflowY === 'auto' || stile.overflowY === 'scroll') { scatole.push(el); break; }
      el = el.parentElement;
    }
  });
  if (!scatole.length) { return; }
  function a_fondo() {
    scatole.forEach(function(box) { box.scrollTop = box.scrollHeight; });
  }
  a_fondo();
  var avvio = Date.now();
  var timer = setInterval(function() {
    if (!doc.querySelector('[id^="fine-"]')) { clearInterval(timer); return; }
    a_fondo();
    if (Date.now() - avvio > DURATA_MS) { clearInterval(timer); }
  }, 300);
})();
</script>
"""

# Un pezzo d'azione è ciò che sta tra asterischi sulla stessa riga: *sorride*
_MOTIVO_AZIONE = re.compile(r"(\*[^*\n]+\*)")


def parti_parlato_azioni(testo):
    """Divide il testo in coppie (tipo, pezzo): 'parlato' oppure 'azione' (*…*)."""
    parti = []
    for pezzo in _MOTIVO_AZIONE.split(testo or ""):
        if not pezzo:
            continue
        if pezzo.startswith("*") and pezzo.endswith("*") and len(pezzo) > 2:
            parti.append(("azione", pezzo))
        else:
            parti.append(("parlato", pezzo))
    return parti


def bolla_html(voce, mappa_scena, nome_ut):
    """Una riga di chat: bolla tonda se c'è del parlato, riquadro se sono
    solo azioni. `voce` è un messaggio (ruolo, testo, chi): il colore della
    bolla e del nome dell'autore è quello del PNG in scena che ha parlato."""
    testo = voce.get("testo") or ""
    parti = parti_parlato_azioni(testo)
    utente = voce.get("ruolo") == "utente"
    chi = "" if utente else str(voce.get("chi") or "")
    voce_scena = mappa_scena.get(chi) if chi else None
    autore = nome_ut if utente else (
        voce.get("nome_png") or (voce_scena or {}).get("nome") or "Personaggio"
    )
    tema = (voce_scena or {}).get("tema")
    classe_colore = f" p-{chi}" if chi else ""
    stile_autore = (
        f' style="color:{tema};font-weight:600"' if (not utente and tema) else ""
    )
    parlato = any(tipo == "parlato" and pezzo.strip() for tipo, pezzo in parti)
    if parlato:
        classe = "bolla ut" if utente else "bolla pg" + classe_colore
        posizione = "destra" if utente else "sinistra"
        pezzi_corpo = []
        for tipo, pezzo in parti:
            if tipo == "azione":
                pezzi_corpo.append('<span class="az">' + modulo_html.escape(pezzo) + "</span>")
            else:
                pezzi_corpo.append(modulo_html.escape(pezzo).replace("\n", "<br>"))
        corpo = "".join(pezzi_corpo)
    else:
        classe = "bolla azioni" + classe_colore
        posizione = "centro"
        corpo = modulo_html.escape(testo).replace("\n", "<br>")
    return (
        '<div class="riga ' + posizione + '">'
        '<div class="autore"' + stile_autore + ">" + modulo_html.escape(autore) + "</div>"
        '<div class="' + classe + '">' + corpo + "</div></div>"
    )


def chat_html(messaggi, mappa_scena, nome_ut, chi_default=""):
    """Tutta la conversazione in HTML, pronta per st.markdown.

    I messaggi dei personaggi senza `chi` (i vecchi, salvati prima della
    scena multi-PNG) vengono attribuiti al personaggio predefinito.
    """
    bolle = []
    for voce in messaggi:
        voce_completa = dict(voce)
        if voce_completa.get("ruolo") != "utente" and not voce_completa.get("chi"):
            voce_completa["chi"] = chi_default
        bolle.append(bolla_html(voce_completa, mappa_scena, nome_ut))
    return '<div class="chat-bolle">' + "".join(bolle) + '<div id="fine-chat"></div></div>'


def inietta_autoscroll(durata_ms):
    """Tiene le chat agganciate all'ultimo messaggio per `durata_ms` millisecondi."""
    html_js(JS_AUTOSCROLL.replace("DURATA_MS", str(int(durata_ms))), height=0)


@contextmanager
def pannello_scrollabile():
    """Pannello della linguetta attiva (Personaggio, Luoghi): riempie lo
    spazio sotto l'intestazione e scrolla dentro di sé; il CSS è agganciato
    all'ancora #pannello-secondario."""
    with st.container(border=True):
        st.markdown('<div id="pannello-secondario"></div>', unsafe_allow_html=True)
        yield


def pannello_proposta_memoria(pid):
    """Carta di conferma per le modifiche alla memoria proposte dalla regia."""
    proposta = st.session_state.get("proposta_memoria")
    if not proposta or proposta.get("pid") != pid:
        return
    modifiche = proposta.get("modifiche") or {}
    righe = []
    if modifiche.get("umore"):
        righe.append(f"**Umore:** {modifiche['umore']}")
    if modifiche.get("situazione"):
        righe.append(f"**Situazione:** {modifiche['situazione']}")
    relazione = modifiche.get("relazione") or {}
    try:
        delta = int(relazione.get("delta_fiducia") or 0)
    except (TypeError, ValueError):
        delta = 0
    if delta:
        righe.append(f"**Fiducia:** {'+' if delta > 0 else ''}{delta}")
    if relazione.get("nota"):
        righe.append(f"**Nota relazione:** {relazione['nota']}")
    for ricordo in modifiche.get("nuovi_ricordi") or []:
        if isinstance(ricordo, dict) and str(ricordo.get("testo", "")).strip():
            righe.append(f"**Ricordo:** {ricordo['testo']}")
    if not righe:
        return
    with st.container(border=True):
        st.markdown("📝 **Proposta per la memoria** — la applico solo se confermi:")
        for riga in righe:
            st.markdown("- " + riga)
        colonna_si, colonna_no = st.columns(2)
        with colonna_si:
            if st.button("✅ Applica", type="primary", use_container_width=True,
                         key="regia_applica"):
                cambiamenti = modulo_memoria.applica_aggiornamenti(
                    pid, modifiche, nota="Aggiornamento dalla regia",
                    delta_max_fiducia=100,
                )
                st.session_state.pop("proposta_memoria", None)
                if cambiamenti:
                    st.toast("Memoria aggiornata: " + " · ".join(cambiamenti[:3]), icon="🧠")
                st.rerun()
        with colonna_no:
            if st.button("❌ Scarta", use_container_width=True, key="regia_scarta"):
                st.session_state.pop("proposta_memoria", None)
                st.rerun()


def elabora_regia(pid, testo, scheda, memoria_dati):
    """Gestisce una richiesta di servizio: risposta della macchina ed eventuali azioni."""
    database.aggiungi_messaggio_regia(pid, "utente", testo)
    nomi_png = [p["nome"] for p in database.lista_personaggi()]
    try:
        with st.spinner("🎬 La macchina valuta la richiesta…"):
            messaggio, azione = modulo_regia.interpreta(
                testo, scheda, memoria_dati, nomi_png
            )
    except ErroreLMStudio as errore:
        database.aggiungi_messaggio_regia(pid, "macchina", "⚠️ " + str(errore))
        st.rerun()

    if azione["azione"] == "crea_png" and azione["descrizione_png"]:
        try:
            with st.spinner("🎭 La macchina compone il nuovo PNG…"):
                nome_nuovo, scheda_nuova, saluto_nuovo = (
                    modulo_personaggio.genera_scheda_con_ia(azione["descrizione_png"])
                )
                id_nuovo = database.crea_personaggio(
                    nome_nuovo, scheda_nuova, origine="ia", saluto=saluto_nuovo
                )
            # Il nuovo PNG entra nella scena attuale: mai una chat a parte.
            database.aggiungi_in_scena(pid, id_nuovo)
            database.aggiungi_messaggio_regia(
                pid, "macchina",
                messaggio
                + "\n\n✅ **" + nome_nuovo + "** è arrivato ed è subito in scena: "
                "la prossima risposta può dargli la parola.",
            )
            st.rerun()
        except (ErroreLMStudio, modulo_personaggio.ErroreCreazione) as errore:
            database.aggiungi_messaggio_regia(
                pid, "macchina",
                messaggio + f"\n\n⚠️ Non sono riuscito a creare il PNG: {errore}",
            )
            st.rerun()

    if azione["azione"] == "aggiorna_memoria" and azione["modifiche"]:
        st.session_state["proposta_memoria"] = {"pid": pid, "modifiche": azione["modifiche"]}
        database.aggiungi_messaggio_regia(
            pid, "macchina",
            messaggio + "\n\n📝 Ho pronto la proposta: controllala e confermala qui sotto.",
        )
        st.rerun()

    database.aggiungi_messaggio_regia(pid, "macchina", messaggio)
    st.rerun()


# ---------------------------------------------------------------------------
# Stato di sessione
# ---------------------------------------------------------------------------

if "schermata" not in st.session_state:
    st.session_state.schermata = "menu"
if "personaggio_id" not in st.session_state:
    st.session_state.personaggio_id = None
if "tutorial_attivo" not in st.session_state:
    st.session_state.tutorial_attivo = False
if "linguetta" not in st.session_state:
    st.session_state.linguetta = "gioco"
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
        f"`{MODELLO_ARCHIVISTA or 'automatico'}` · regia "
        f"`{MODELLO_REGIA or 'automatico'}` · server LM Studio `{BASE_URL}`"
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

    destinazione_scena = st.session_state.get("entrata_in_scena")
    if destinazione_scena and database.trova_personaggio(destinazione_scena):
        nome_dest = (database.trova_personaggio(destinazione_scena) or {}).get("nome", "?")
        st.info(
            "🎭 Il nuovo PNG entrerà nella scena del roleplay di **" + nome_dest
            + "**: al termine non si apre una chat a parte, si unisce alla conversazione in corso.",
        )

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
                        id_nuovo = database.crea_personaggio(
                            nome, scheda, origine="ia", saluto=saluto
                        )
                        dopo_creazione(id_nuovo, nome)
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
                    id_nuovo = database.crea_personaggio(
                        nome_manuale.strip(), scheda, origine="giocatore"
                    )
                    dopo_creazione(id_nuovo, nome_manuale.strip())
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
    conversazione = database.carica_conversazione(pid)
    messaggi = conversazione.get("messaggi", [])
    dati_indice = database.trova_personaggio(pid) or {}
    nome_utente_mostrato = st.session_state.nome_utente.strip() or "Tu"

    # Chi è in scena e con quale colore (i colori mancanti vengono assegnati
    # e salvati qui: restano stabili). Le schede servono al prompt di scena.
    scena = carica_scena(pid)
    ids_scena = [voce["id"] for voce in scena]
    mappa_scena = {voce["id"]: voce for voce in scena}
    schede_scena = []
    for id_png in ids_scena:
        try:
            scheda_scena = dict(database.carica_scheda(id_png))
            scheda_scena["id"] = id_png
            schede_scena.append(scheda_scena)
        except FileNotFoundError:
            continue

    # --- intestazione: titolo al centro, riga d'informazioni, linguette ---
    st.markdown(
        '<h1 class="titolo-chat">💬 '
        + modulo_html.escape(nome_personaggio)
        + "</h1>",
        unsafe_allow_html=True,
    )

    fiducia = memoria_dati["relazione"]["fiducia"]
    pezzi_info = []
    origine = dati_indice.get("origine", "")
    if etichetta_origine(origine):
        pezzi_info.append(emoji_origine(origine) + " " + etichetta_origine(origine))
    if len(scena) > 1:
        pezzi_info.append("👥 " + ", ".join(voce["nome"] for voce in scena))
    if memoria_dati.get("umore"):
        pezzi_info.append("🧠 umore: " + memoria_dati["umore"])
    pezzi_info.append(f"🤝 fiducia {fiducia}/100")
    pezzi_info.append(f"💬 {len(messaggi)} messaggi")
    pezzi_info.append("🕐 " + formatta_data(dati_indice.get("aggiornato_il")))
    st.markdown(
        '<div class="riga-info">'
        + modulo_html.escape(" · ".join(pezzi_info))
        + "</div>",
        unsafe_allow_html=True,
    )

    # Barra delle linguette: il bottone Menu e le linguette, tutte con la
    # stessa estetica a bottone; quella attiva è evidenziata.
    rapporti = [1.0] + [1.05] * len(LINGUETTE_APP)
    colonne_barra = st.columns(rapporti, gap="small")
    with colonne_barra[0]:
        # Ancora invisibile: identifica la barra nel CSS (centrata e
        # compatta) senza aggiungere spazio tra i bottoni.
        st.markdown('<span id="barra-linguette" style="display:none"></span>',
                    unsafe_allow_html=True)
        if st.button("⬅️ Menu", use_container_width=True, key="bottone_menu_da_app"):
            vai_al_menu()
            st.rerun()
    for numero, (chiave, etichetta) in enumerate(LINGUETTE_APP, start=1):
        with colonne_barra[numero]:
            if st.button(
                etichetta,
                use_container_width=True,
                key=f"linguetta_{chiave}",
                type="primary" if st.session_state.linguetta == chiave else "secondary",
            ):
                st.session_state.linguetta = chiave
                st.rerun()

    st.markdown(CSS_GIOCO, unsafe_allow_html=True)
    st.markdown(css_scena(scena), unsafe_allow_html=True)
    st.markdown(CSS_PAGINA_FISSA, unsafe_allow_html=True)

    if st.session_state.linguetta == "gioco":
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
                    "**↩️ Annulla ultima modifica della memoria**.\n"
                    "5. In alto a destra c'è la **🛠️ Regia**: parli con la macchina, "
                    "fuori dal gioco (far arrivare un nuovo PNG, aggiornamenti della "
                    "memoria da confermare, comunicazioni di servizio)."
                )
                if st.button("Ho capito, iniziamo!", type="primary", key="bottone_fine_tutorial"):
                    st.session_state.tutorial_attivo = False
                    st.rerun()

        # Schermo diviso in due pannelli ben separati: chat a sinistra,
        # regia e selettori a destra.
        colonna_chat, colonna_pannello = st.columns([3, 1], gap="large")

        with colonna_chat:
            st.markdown('<div class="titolo-pannello">💬 Dialogo</div>',
                        unsafe_allow_html=True)
            with st.container(height=540, border=False):
                if not messaggi:
                    st.caption("Nessun messaggio: rompi il ghiaccio con una prima frase.")
                st.markdown(
                    chat_html(messaggi, mappa_scena, nome_utente_mostrato, chi_default=pid),
                    unsafe_allow_html=True,
                )
                bolla_nuova = st.empty()
                segnaposto_stream = st.empty()
            prompt = st.chat_input("Scrivi a " + nome_personaggio + "…")

        with colonna_pannello:
            # In alto: la regia, la linea diretta con la macchina fuori dal gioco.
            storico_regia = database.carica_regia(pid)
            st.markdown('<div class="titolo-pannello">🛠️ Regia</div>',
                        unsafe_allow_html=True)
            with st.container(height=430, border=True):
                st.caption(
                    "Comunicazioni di servizio: far arrivare un nuovo PNG, "
                    "un'uscita di scena, aggiornamenti della memoria da confermare…"
                )
                if not storico_regia.get("messaggi"):
                    st.caption("Nessuna comunicazione: scrivi alla macchina qui sotto.")
                for voce in storico_regia.get("messaggi", []):
                    with st.chat_message(
                        "user" if voce.get("ruolo") == "utente" else "assistant",
                        avatar="🎬" if voce.get("ruolo") == "utente" else "🛠️",
                    ):
                        st.markdown(voce.get("testo", ""))
                pannello_proposta_memoria(pid)
                st.markdown('<div id="fine-regia"></div>', unsafe_allow_html=True)
            # La casella della regia è un form semplice: funziona in ogni
            # versione di Streamlit e non fa conflitto con la chat di gioco.
            with st.form("form_regia", clear_on_submit=True, border=False):
                richiesta_regia = st.text_input(
                    "Messaggio per la macchina",
                    placeholder="Scrivi alla macchina…  (es. fai entrare un barista pettegolo)",
                    label_visibility="collapsed",
                    key="input_regia",
                )
                invia_regia = st.form_submit_button(
                    "🎬 Invia alla macchina", use_container_width=True, type="primary"
                )

            # In basso: i selettori — la scena e chi la abita.
            st.markdown('<div class="titolo-pannello">🎛️ Selettori</div>',
                        unsafe_allow_html=True)
            with st.container(border=True):
                st.caption("🎭 PNG in scena — il colore di ogni nome è quello delle sue bolle.")
                st.markdown(chip_scena_html(scena), unsafe_allow_html=True)

                # Far entrare nella scena un PNG già esistente.
                candidati = [
                    (p["nome"], p["id"]) for p in database.lista_personaggi()
                    if p["id"] not in ids_scena
                ]
                if candidati:
                    scelta_entrata = st.selectbox(
                        "Fai entrare in scena",
                        [("+ — scegli un PNG —", "")] + candidati,
                        index=0,
                        format_func=lambda voce: voce[0],
                        help="Il PNG entra nel roleplay attuale: nessuna chat a parte.",
                        key="selettore_entrata",
                    )
                    if scelta_entrata[1]:
                        database.aggiungi_in_scena(pid, scelta_entrata[1])
                        st.toast("🎭 " + scelta_entrata[0] + " è entrato in scena.", icon="🎭")
                        st.rerun()
                else:
                    st.selectbox(
                        "Fai entrare in scena",
                        ["Tutti i PNG sono già in scena"],
                        disabled=True,
                        key="selettore_entrata_piena",
                    )

                # Creare un PNG nuovo: entra in questa scena, non apre una chat.
                if st.button("➕ Nuovo PNG", use_container_width=True,
                             key="bottone_nuovo_png"):
                    st.session_state["entrata_in_scena"] = pid
                    st.session_state.schermata = "nuovo"
                    st.rerun()

                # Tornare al roleplay di un altro personaggio.
                opzioni_roleplay = [
                    (p["nome"], p["id"]) for p in database.lista_personaggi()
                ]
                indice_roleplay = 0
                for numero, (_, id_png) in enumerate(opzioni_roleplay):
                    if id_png == pid:
                        indice_roleplay = numero
                        break
                scelta_roleplay = st.selectbox(
                    "🗂️ Cambia roleplay",
                    opzioni_roleplay,
                    index=indice_roleplay,
                    format_func=lambda voce: voce[0],
                    help="Apri il roleplay di un altro personaggio.",
                    key="selettore_roleplay",
                )
                if scelta_roleplay[1] != pid:
                    apri_roleplay(scelta_roleplay[1])
                    st.rerun()
                st.selectbox(
                    "Luogo attivo",
                    ["🗺️ In arrivo"],
                    disabled=True,
                    help="La gestione dei luoghi arriverà qui.",
                    key="selettore_luoghi",
                )
                st.caption("Altri selettori in arrivo: oggetti, situazioni…")

        if prompt:
            nome_utente = st.session_state.nome_utente.strip()
            database.aggiungi_messaggio(pid, "utente", prompt)
            bolla_nuova.markdown(
                chat_html(
                    [{"ruolo": "utente", "testo": prompt}],
                    mappa_scena, nome_utente_mostrato, chi_default=pid,
                ),
                unsafe_allow_html=True,
            )
            inietta_autoscroll(240000)

            scheda_fresca = database.carica_scheda(pid)
            memoria_fresca = modulo_memoria.normalizza_memoria(database.carica_memoria(pid))
            conversazione_fresca = database.carica_conversazione(pid)

            accumulo = []
            try:
                for pezzo in narratore.genera_risposta(
                    scheda_fresca, memoria_fresca, conversazione_fresca, nome_utente,
                    scena=scena, schede_scena=schede_scena,
                ):
                    accumulo.append(pezzo)
                    battute_live = narratore.spezza_risposta("".join(accumulo), scena, pid)
                    voci_live = [
                        {"ruolo": "personaggio", "testo": pezzo_battuta, "chi": chi_battuta}
                        for chi_battuta, pezzo_battuta in battute_live
                    ]
                    segnaposto_stream.markdown(
                        chat_html(voci_live, mappa_scena, nome_utente_mostrato, chi_default=pid),
                        unsafe_allow_html=True,
                    )
            except ErroreLMStudio as errore:
                st.error(str(errore))
                st.stop()

            risposta = "".join(accumulo).strip()
            if risposta:
                battute = narratore.spezza_risposta(risposta, scena, pid)
                if battute:
                    for chi_battuta, testo_battuta in battute:
                        database.aggiungi_messaggio(
                            pid, "personaggio", testo_battuta, chi=chi_battuta
                        )
                else:
                    database.aggiungi_messaggio(pid, "personaggio", risposta, chi=pid)

                if st.session_state.archivista_attivo:
                    with st.spinner("🧠 " + nome_personaggio + " aggiorna la memoria…"):
                        cambiamenti = archivista.aggiorna_memoria(pid, nome_utente)
                    if cambiamenti:
                        st.toast("Memoria aggiornata: " + " · ".join(cambiamenti[:3]), icon="🧠")
            else:
                st.warning("Il modello non ha restituito testo: prova a rispedire il messaggio.")

            st.rerun()

        if invia_regia and richiesta_regia.strip():
            elabora_regia(pid, richiesta_regia.strip(), scheda, memoria_dati)

        inietta_autoscroll(6000)

    elif st.session_state.linguetta == "personaggio":
        with pannello_scrollabile():
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

    else:
        with pannello_scrollabile():
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
    st.markdown(CSS_SCHERMI_STRETTI, unsafe_allow_html=True)
    schermata_nuovo()
elif st.session_state.schermata == "app":
    schermata_app()
else:
    st.markdown(CSS_SCHERMI_STRETTI, unsafe_allow_html=True)
    schermata_menu()
