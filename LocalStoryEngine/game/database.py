import json
import sqlite3

from config import DATA_DIR, DB_PATH


def connect_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_db():
    """Crea le tabelle necessarie e aggiunge colonne mancanti senza cancellare dati."""
    with connect_db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS game_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                character_name TEXT NOT NULL,
                level INTEGER NOT NULL,
                experience INTEGER NOT NULL,
                hp INTEGER NOT NULL,
                max_hp INTEGER NOT NULL,
                strength INTEGER NOT NULL,
                dexterity INTEGER NOT NULL,
                constitution INTEGER NOT NULL,
                intelligence INTEGER NOT NULL,
                wisdom INTEGER NOT NULL,
                charisma INTEGER NOT NULL,
                gold INTEGER NOT NULL,
                location TEXT NOT NULL,
                inventory TEXT NOT NULL,
                active_quests TEXT NOT NULL
            )
        """)

        columns = {
            row["name"]
            for row in connection.execute(
                "PRAGMA table_info(game_state)"
            ).fetchall()
        }

        if "equipped_weapon" not in columns:
            connection.execute("""
                ALTER TABLE game_state
                ADD COLUMN equipped_weapon TEXT NOT NULL DEFAULT ''
            """)

        if "equipped_armor" not in columns:
            connection.execute("""
                ALTER TABLE game_state
                ADD COLUMN equipped_armor TEXT NOT NULL DEFAULT ''
            """)

        connection.execute("""
            INSERT OR IGNORE INTO game_state (
                id, character_name, level, experience,
                hp, max_hp, strength, dexterity, constitution,
                intelligence, wisdom, charisma, gold, location,
                inventory, active_quests
            ) VALUES (
                1, 'Avventuriero', 1, 0,
                20, 20, 10, 10, 10,
                10, 10, 10, 10, 'Locanda del Crocevia',
                ?, '[]'
            )
        """, (
            json.dumps(
                ["Abiti da viaggio", "Zaino", "Razioni (3)", "Torcia"],
                ensure_ascii=False,
            ),
        ))


def load_messages():
    with connect_db() as connection:
        rows = connection.execute(
            "SELECT role, content FROM messages ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def save_message(role, content):
    with connect_db() as connection:
        connection.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            (role, content),
        )


def clear_messages():
    """Cancella soltanto la cronologia, non la scheda RPG."""
    with connect_db() as connection:
        connection.execute("DELETE FROM messages")


def load_game_state():
    with connect_db() as connection:
        row = connection.execute(
            "SELECT * FROM game_state WHERE id = 1"
        ).fetchone()

    if row is None:
        raise RuntimeError("Lo stato del personaggio non è stato inizializzato.")

    state = dict(row)
    state["inventory"] = json.loads(state["inventory"])
    state["active_quests"] = json.loads(state["active_quests"])
    return state


def update_character(hp_change=0, gold_change=0):
    """Aggiorna punti vita e oro rispettando i limiti."""
    with connect_db() as connection:
        row = connection.execute(
            "SELECT hp, max_hp, gold FROM game_state WHERE id = 1"
        ).fetchone()

        if row is None:
            raise RuntimeError("Personaggio non inizializzato.")

        new_hp = max(0, min(row["max_hp"], row["hp"] + int(hp_change)))
        new_gold = max(0, row["gold"] + int(gold_change))

        connection.execute("""
            UPDATE game_state
            SET hp = ?, gold = ?
            WHERE id = 1
        """, (new_hp, new_gold))



def set_character_location(location_name):
    """Salva la posizione del personaggio senza modificare gli altri dati."""
    location_name = str(location_name).strip()
    if not location_name:
        return False

    with connect_db() as connection:
        row = connection.execute(
            "SELECT id FROM game_state WHERE id = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("Personaggio non inizializzato.")

        connection.execute(
            "UPDATE game_state SET location = ? WHERE id = 1",
            (location_name,),
        )

    return True


def add_inventory_item(item_name, quantity=1):
    item_name = item_name.strip()
    quantity = int(quantity)
    if not item_name or quantity < 1:
        return

    with connect_db() as connection:
        row = connection.execute(
            "SELECT inventory FROM game_state WHERE id = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("Personaggio non inizializzato.")

        inventory = json.loads(row["inventory"])
        inventory.extend([item_name] * quantity)

        connection.execute(
            "UPDATE game_state SET inventory = ? WHERE id = 1",
            (json.dumps(inventory, ensure_ascii=False),),
        )


def remove_inventory_item(item_name, quantity=1):
    item_name = item_name.strip()
    quantity = int(quantity)
    if not item_name or quantity < 1:
        return 0

    removed = 0
    with connect_db() as connection:
        row = connection.execute(
            "SELECT inventory FROM game_state WHERE id = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("Personaggio non inizializzato.")

        inventory = json.loads(row["inventory"])
        remaining = []

        for item in inventory:
            if item.casefold() == item_name.casefold() and removed < quantity:
                removed += 1
            else:
                remaining.append(item)

        connection.execute(
            "UPDATE game_state SET inventory = ? WHERE id = 1",
            (json.dumps(remaining, ensure_ascii=False),),
        )

    return removed


ITEM_RULES = {
    "Spada semplice": {
        "type": "weapon",
        "damage_bonus": 2,
    },
    "Armatura di cuoio": {
        "type": "armor",
        "defense": 1,
    },
}


def equip_item(item_name, slot):
    """Equipaggia un oggetto se è noto, compatibile e presente nell'inventario."""
    if item_name not in ITEM_RULES:
        return False
    if ITEM_RULES[item_name]["type"] != slot:
        return False

    with connect_db() as connection:
        row = connection.execute(
            "SELECT inventory FROM game_state WHERE id = 1"
        ).fetchone()
        if row is None:
            raise RuntimeError("Personaggio non inizializzato.")

        inventory = json.loads(row["inventory"])
        if not any(item.casefold() == item_name.casefold() for item in inventory):
            return False

        column = "equipped_weapon" if slot == "weapon" else "equipped_armor"
        connection.execute(
            f"UPDATE game_state SET {column} = ? WHERE id = 1",
            (item_name,),
        )

    return True


def use_healing_potion():
    """Consuma una pozione curativa e ripristina fino a 8 punti vita."""
    with connect_db() as connection:
        row = connection.execute("""
            SELECT hp, max_hp, inventory
            FROM game_state
            WHERE id = 1
        """).fetchone()

        if row is None:
            raise RuntimeError("Personaggio non inizializzato.")
        if row["hp"] >= row["max_hp"]:
            return "full"

        inventory = json.loads(row["inventory"])
        potion_index = next(
            (
                i for i, item in enumerate(inventory)
                if item.casefold() == "pozione curativa"
            ),
            None,
        )

        if potion_index is None:
            return "missing"

        inventory.pop(potion_index)
        new_hp = min(row["max_hp"], row["hp"] + 8)

        connection.execute("""
            UPDATE game_state
            SET hp = ?, inventory = ?
            WHERE id = 1
        """, (
            new_hp,
            json.dumps(inventory, ensure_ascii=False),
        ))

    return "used"
