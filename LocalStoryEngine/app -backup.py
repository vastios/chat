import streamlit as st

from config import DB_PATH
from game.database import (
    ITEM_RULES,
    add_inventory_item,
    clear_messages,
    initialize_db,
    load_messages,
    remove_inventory_item,
    save_message,
    set_character_location,
    update_character,
    load_game_state,
)
from game.character import get_character
from game.inventory import drink_healing_potion, equip, get_inventory
from game.narrator import generate_response
from game.world import get_available_locations, get_location
from game.combat import player_attack, enemy_attack, is_enemy_defeated, is_player_defeated

st.set_page_config(
    page_title="LocalStoryEngine",
    page_icon="📜",
    layout="wide",
)

# Inizializza le tabelle mancanti senza cancellare la partita o la cronologia.
initialize_db()


def build_state_context(state):
    inventory_text = ", ".join(state["inventory"]) if state["inventory"] else "Vuoto"
    quests_text = (
        ", ".join(state["active_quests"])
        if state["active_quests"]
        else "Nessuna missione registrata"
    )
    return f"""
SCHEDA CANONICA DEL PERSONAGGIO
Nome: {state['character_name']}
Livello: {state['level']}
Esperienza: {state['experience']}
Punti vita: {state['hp']}/{state['max_hp']}
Forza: {state['strength']}
Destrezza: {state['dexterity']}
Costituzione: {state['constitution']}
Intelligenza: {state['intelligence']}
Saggezza: {state['wisdom']}
Carisma: {state['charisma']}
Oro: {state['gold']}
Posizione: {state['location']}
Arma equipaggiata: {state.get('equipped_weapon', '') or 'Nessuna'}
Armatura equipaggiata: {state.get('equipped_armor', '') or 'Nessuna'}
Inventario: {inventory_text}
Missioni attive registrate: {quests_text}

Questi valori sono dati salvati dal programma.
Non affermare che siano cambiati se il programma non li ha aggiornati.

ESPLORAZIONE DEL MONDO
Il gioco usa una mappa di luoghi collegati, ma il giocatore può anche
descrivere liberamente azioni, deviazioni e luoghi da esplorare.
Non dichiarare che la posizione salvata sia cambiata: i viaggi ufficiali
vengono salvati tramite i comandi della mappa. Se il giocatore propone
una meta nuova, narrane l'avvicinamento e chiedi dettagli se necessario.
"""


game = get_character()

st.title("📜 LocalStoryEngine")
st.caption("Fantasy classico originale · Gioco locale")

with st.sidebar:
    st.subheader("⚔️ Personaggio")
    st.write(f"**{game['character_name']}** · Livello {game['level']}")
    st.progress(
        max(0.0, min(1.0, game["hp"] / max(1, game["max_hp"]))),
        text=f"Punti vita: {game['hp']} / {game['max_hp']}",
    )
    st.write(f"✨ Esperienza: {game['experience']}")
    st.write(f"🪙 Oro: {game['gold']}")
    st.write(f"📍 Luogo: {game['location']}")

    with st.expander("Caratteristiche"):
        for key, label in [
            ("strength", "Forza"),
            ("dexterity", "Destrezza"),
            ("constitution", "Costituzione"),
            ("intelligence", "Intelligenza"),
            ("wisdom", "Saggezza"),
            ("charisma", "Carisma"),
        ]:
            st.write(f"{label}: **{game[key]}**")

    with st.expander("🎒 Inventario", expanded=True):
        inventory_items = get_inventory()
        if inventory_items:
            for item in inventory_items:
                st.write(f"• {item}")
        else:
            st.write("L'inventario è vuoto.")

        st.caption(f"Arma: {game.get('equipped_weapon', '') or 'Nessuna'}")
        st.caption(f"Armatura: {game.get('equipped_armor', '') or 'Nessuna'}")

    with st.expander("Gestisci inventario"):
        with st.form("add_inventory_form"):
            st.write("Aggiungi un oggetto")
            new_item = st.text_input(
                "Nome dell'oggetto",
                placeholder="Es. Pozione curativa",
            )
            add_quantity = st.number_input(
                "Quantità da aggiungere",
                min_value=1,
                max_value=99,
                value=1,
                step=1,
            )
            add_submitted = st.form_submit_button(
                "Aggiungi oggetto",
                use_container_width=True,
            )
            if add_submitted:
                if new_item.strip():
                    add_inventory_item(new_item, int(add_quantity))
                    st.rerun()
                else:
                    st.warning("Inserisci il nome dell'oggetto.")

        st.divider()
        with st.form("remove_inventory_form"):
            st.write("Rimuovi un oggetto")
            remove_name = st.text_input(
                "Nome esatto dell'oggetto",
                placeholder="Es. Pozione curativa",
            )
            remove_quantity = st.number_input(
                "Quantità da rimuovere",
                min_value=1,
                max_value=99,
                value=1,
                step=1,
                key="remove_quantity",
            )
            remove_submitted = st.form_submit_button(
                "Rimuovi oggetto",
                use_container_width=True,
            )
            if remove_submitted:
                if remove_name.strip():
                    removed = remove_inventory_item(remove_name, int(remove_quantity))
                    if removed:
                        st.rerun()
                    else:
                        st.warning("Non trovo questo oggetto nell'inventario.")
                else:
                    st.warning("Inserisci il nome dell'oggetto.")

    with st.expander("🛡️ Equipaggiamento"):
        # Mostra la conferma dopo il rerun necessario ad aggiornare la scheda.
        equipment_notice = st.session_state.pop("equipment_notice", None)
        if equipment_notice:
            st.success(equipment_notice)

        weapon_options = [
            name for name, rule in ITEM_RULES.items()
            if rule["type"] == "weapon" and name.casefold() in {
                item.casefold() for item in game["inventory"]
            }
        ]
        armor_options = [
            name for name, rule in ITEM_RULES.items()
            if rule["type"] == "armor" and name.casefold() in {
                item.casefold() for item in game["inventory"]
            }
        ]

        if weapon_options:
            with st.form("equip_weapon_form"):
                weapon_choice = st.selectbox(
                    "Arma da equipaggiare",
                    options=weapon_options,
                )
                weapon_submitted = st.form_submit_button("Equipaggia arma")
                if weapon_submitted:
                    if equip(weapon_choice):
                        st.session_state["equipment_notice"] = (
                            f"Arma equipaggiata: {weapon_choice}."
                        )
                        st.rerun()
                    else:
                        st.warning("Non è stato possibile equipaggiare quest'arma.")
        else:
            st.caption("Aggiungi una spada compatibile per equipaggiare un'arma.")

        if armor_options:
            with st.form("equip_armor_form"):
                armor_choice = st.selectbox(
                    "Armatura da equipaggiare",
                    options=armor_options,
                )
                armor_submitted = st.form_submit_button("Equipaggia armatura")
                if armor_submitted:
                    if equip(armor_choice):
                        st.session_state["equipment_notice"] = (
                            f"Armatura equipaggiata: {armor_choice}."
                        )
                        st.rerun()
                    else:
                        st.warning("Non è stato possibile equipaggiare quest'armatura.")
        else:
            st.caption("Aggiungi un'armatura compatibile per equipaggiare una difesa.")

    with st.expander("🧪 Pozione curativa"):
        if st.button("Bevi una pozione (+8 PF)", use_container_width=True):
            result = drink_healing_potion()
            if result == "used":
                st.success("Hai bevuto una pozione curativa.")
                st.rerun()
            elif result == "full":
                st.info("Hai già tutti i punti ferita.")
            else:
                st.warning("Non hai pozioni curative nell'inventario.")

    with st.expander("📜 Missioni"):
        if game["active_quests"]:
            for quest in game["active_quests"]:
                st.write(f"• {quest}")
        else:
            st.write("Nessuna missione registrata.")

    with st.expander("🗺️ Mappa del regno", expanded=True):
        st.caption("Esplorazione ibrida: usa la mappa per viaggiare oppure descrivi liberamente le tue azioni nella chat.")
        st.write(f"**Posizione attuale:** {game['location']}")
        location = get_location(game["location"])
        if location:
            st.caption(f"Zona: {location.get('region', 'Regione non definita')} · {location.get('kind', 'Luogo')}")
            st.write(location["description"])
            destinations = get_available_locations(game["location"])
            if destinations:
                st.write("**Destinazioni collegate**")
                for destination in destinations:
                    if st.button(f"🚶 Vai a {destination}", key=f"travel_{destination}", use_container_width=True):
                        if set_character_location(destination):
                            st.session_state["travel_notice"] = f"Sei arrivato a: {destination}."
                            st.rerun()
            else:
                st.caption("Da qui non risultano ancora destinazioni collegate.")
        else:
            st.info("Questo luogo non è ancora nella mappa. Puoi continuare a esplorarlo descrivendo le tue azioni nella chat.")
        travel_notice = st.session_state.pop("travel_notice", None)
        if travel_notice:
            st.success(travel_notice)

    # Sezione di combattimento: il nemico resta attivo durante i rerun della pagina.
    st.divider()
    st.header("⚔️ Combattimento")
    st.caption("Gli scontri sono facoltativi. I punti vita persi vengono salvati nella partita.")

    ENEMIES = {
        "Goblin": {"max_hp": 12, "attack": 4, "description": "Una creatura nervosa con un pugnale arrugginito."},
        "Bandito": {"max_hp": 16, "attack": 5, "description": "Un viandante armato che ti sbarra la strada."},
    }

    if "combat_enemy" not in st.session_state:
        st.session_state.combat_enemy = None
    if "combat_log" not in st.session_state:
        st.session_state.combat_log = []

    if st.session_state.combat_enemy is None:
        enemy_choice = st.selectbox("Scegli un avversario", list(ENEMIES.keys()))
        if st.button("Inizia combattimento", key="start_combat"):
            template = ENEMIES[enemy_choice]
            st.session_state.combat_enemy = {
                "name": enemy_choice,
                "hp": template["max_hp"],
                "max_hp": template["max_hp"],
                "attack": template["attack"],
                "description": template["description"],
            }
            st.session_state.combat_log = [f"È apparso un {enemy_choice}! {template['description']}"]
            st.rerun()
    else:
        enemy = st.session_state.combat_enemy
        st.subheader(f"Avversario: {enemy['name']}")
        st.write(enemy["description"])
        st.progress(max(0.0, min(1.0, enemy["hp"] / enemy["max_hp"])),
                    text=f"PF nemico: {enemy['hp']} / {enemy['max_hp']}")

        current = get_character()
        if is_player_defeated(current["hp"]):
            st.error("Sei a terra e non puoi attaccare. Usa una pozione se ne hai una, oppure termina lo scontro.")
        elif is_enemy_defeated(enemy["hp"]):
            st.success(f"Hai sconfitto {enemy['name']}!")
            if st.button("Concludi lo scontro", key="end_combat"):
                st.session_state.combat_enemy = None
                st.session_state.combat_log = []
                st.rerun()
        else:
            if st.button("Attacca", key="player_attack"):
                current = get_character()
                weapon = current.get("equipped_weapon", "")
                weapon_bonus = ITEM_RULES.get(weapon, {}).get("damage_bonus", 0)
                damage = player_attack(current["strength"], weapon_bonus)
                enemy["hp"] = max(0, enemy["hp"] - damage)
                st.session_state.combat_log.append(f"Hai inflitto {damage} danni a {enemy['name']}.")
                if is_enemy_defeated(enemy["hp"]):
                    st.session_state.combat_log.append(f"{enemy['name']} è stato sconfitto!")
                else:
                    armor = current.get("equipped_armor", "")
                    defense = ITEM_RULES.get(armor, {}).get("defense", 0)
                    received = enemy_attack(enemy["attack"], defense)
                    update_character(hp_change=-received)
                    st.session_state.combat_log.append(f"{enemy['name']} ti ha inflitto {received} danni.")
                st.rerun()

        if st.button("Fuggi / termina lo scontro", key="flee_combat"):
            st.session_state.combat_enemy = None
            st.session_state.combat_log = []
            st.rerun()

    if st.session_state.combat_log:
        with st.expander("Registro dello scontro", expanded=True):
            for event in st.session_state.combat_log:
                st.write("• " + event)

    st.divider()
    st.caption("I dati del personaggio sono salvati in SQLite.")
    st.caption(f"Database: {DB_PATH}")

    if st.button("Cancella cronologia chat", use_container_width=True):
        clear_messages()
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.subheader("🧪 Gestione personaggio")
    st.caption("Strumenti di prova: le modifiche sono permanenti.")
    with st.form("character_test_form"):
        hp_change = st.number_input(
            "Modifica punti vita (+ cura, - danno)",
            min_value=-100,
            max_value=100,
            value=0,
            step=1,
        )
        gold_change = st.number_input(
            "Modifica oro (+ ricevi, - spendi)",
            min_value=-1000,
            max_value=1000,
            value=0,
            step=1,
        )
        confirm_changes = st.form_submit_button(
            "Applica modifiche",
            use_container_width=True,
        )
        if confirm_changes:
            update_character(
                hp_change=int(hp_change),
                gold_change=int(gold_change),
            )
            st.success("Modifiche salvate!")
            st.rerun()


if "messages" not in st.session_state:
    st.session_state.messages = load_messages()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Cosa vuoi fare?")

if prompt:
    user_message = {"role": "user", "content": prompt}
    st.session_state.messages.append(user_message)
    save_message("user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)

    # Rileggi lo stato per passare al narratore i valori canonici più recenti.
    current_game = get_character()
    with st.chat_message("assistant"):
        with st.spinner("Il narratore sta pensando..."):
            try:
                answer = generate_response(
                    st.session_state.messages,
                    state_context=build_state_context(current_game),
                    max_tokens=500,
                )
                st.markdown(answer)
                assistant_message = {"role": "assistant", "content": answer}
                st.session_state.messages.append(assistant_message)
                save_message("assistant", answer)
            except Exception as error:
                st.error(
                    "Non sono riuscito a ottenere una risposta da LM Studio. "
                    "Il messaggio è stato salvato; controlla il server e riprova."
                )
                st.code(str(error))
