"""Archivio persistente dei PNG di LocalStoryEngine.

Questo modulo aggiunge tabelle dedicate ai personaggi non giocanti senza
modificare le tabelle esistenti del salvataggio. Non è ancora collegato
all'interfaccia o al narratore: questo primo passo permette di testare
l'archivio in modo isolato.
"""

import json

from game.database import connect_db


def initialize_npc_tables():
    """Crea le tabelle dei PNG se non esistono, senza cancellare dati."""
    with connect_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS npcs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT NOT NULL DEFAULT '',
                origin_type TEXT NOT NULL DEFAULT 'ai',
                identity_json TEXT NOT NULL,
                current_status TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS npc_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_id INTEGER NOT NULL,
                memory_text TEXT NOT NULL,
                importance INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (npc_id) REFERENCES npcs(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS npc_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                npc_id INTEGER NOT NULL,
                target TEXT NOT NULL DEFAULT 'protagonista',
                trust INTEGER NOT NULL DEFAULT 0,
                relationship_notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (npc_id, target),
                FOREIGN KEY (npc_id) REFERENCES npcs(id) ON DELETE CASCADE
            )
            """
        )


def create_npc(
    name,
    identity,
    location='',
    origin_type='ai',
    current_status='',
):
    """Salva un PNG e restituisce il suo ID.

    identity è un dizionario con i tratti canonici del personaggio, ad esempio
    aspetto, personalità, storia, obiettivi, segreti e conoscenze.
    origin_type può essere 'ai' oppure 'player'.
    """
    clean_name = str(name).strip()
    if not clean_name:
        raise ValueError("Il PNG deve avere un nome.")
    if origin_type not in {'ai', 'player'}:
        raise ValueError("origin_type deve essere 'ai' oppure 'player'.")
    if not isinstance(identity, dict):
        raise TypeError("identity deve essere un dizionario.")

    identity_json = json.dumps(identity, ensure_ascii=False)
    with connect_db() as connection:
        cursor = connection.execute(
            """
            INSERT INTO npcs (name, location, origin_type, identity_json, current_status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (clean_name, str(location).strip(), origin_type, identity_json,
             str(current_status).strip()),
        )
        npc_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO npc_relationships (npc_id, target, trust) VALUES (?, 'protagonista', 0)",
            (npc_id,),
        )
    return npc_id


def get_npc(npc_id):
    """Restituisce la scheda completa di un PNG oppure None."""
    with connect_db() as connection:
        row = connection.execute(
            "SELECT * FROM npcs WHERE id = ?", (int(npc_id),)
        ).fetchone()
        if row is None:
            return None
        npc = dict(row)
        npc['identity'] = json.loads(npc.pop('identity_json'))
        memories = connection.execute(
            """
            SELECT id, memory_text, importance, created_at
            FROM npc_memories WHERE npc_id = ?
            ORDER BY importance DESC, id ASC
            """,
            (int(npc_id),),
        ).fetchall()
        npc['memories'] = [dict(memory) for memory in memories]
        relationship = connection.execute(
            """
            SELECT target, trust, relationship_notes, updated_at
            FROM npc_relationships WHERE npc_id = ? AND target = 'protagonista'
            """,
            (int(npc_id),),
        ).fetchone()
        npc['relationship'] = dict(relationship) if relationship else None
        return npc


def list_npcs(location=None):
    """Elenca i PNG, opzionalmente filtrati per luogo."""
    with connect_db() as connection:
        if location is None:
            rows = connection.execute(
                "SELECT id, name, location, origin_type, current_status FROM npcs ORDER BY name COLLATE NOCASE"
            ).fetchall()
        else:
            rows = connection.execute(
                """SELECT id, name, location, origin_type, current_status
                   FROM npcs WHERE location = ? ORDER BY name COLLATE NOCASE""",
                (str(location),),
            ).fetchall()
    return [dict(row) for row in rows]


def add_npc_memory(npc_id, memory_text, importance=1):
    """Aggiunge un ricordo al PNG; importanza ammessa da 1 a 5."""
    text = str(memory_text).strip()
    if not text:
        raise ValueError("Il ricordo non può essere vuoto.")
    importance = int(importance)
    if not 1 <= importance <= 5:
        raise ValueError("L'importanza deve essere compresa tra 1 e 5.")
    with connect_db() as connection:
        exists = connection.execute(
            "SELECT 1 FROM npcs WHERE id = ?", (int(npc_id),)
        ).fetchone()
        if exists is None:
            raise ValueError("PNG non trovato.")
        connection.execute(
            "INSERT INTO npc_memories (npc_id, memory_text, importance) VALUES (?, ?, ?)",
            (int(npc_id), text, importance),
        )
        connection.execute(
            "UPDATE npcs SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(npc_id),),
        )


def update_npc_relationship(npc_id, trust_change=0, relationship_notes=None):
    """Aggiorna gradualmente la fiducia verso il protagonista, limitata a -100..100."""
    with connect_db() as connection:
        row = connection.execute(
            "SELECT trust, relationship_notes FROM npc_relationships WHERE npc_id = ? AND target = 'protagonista'",
            (int(npc_id),),
        ).fetchone()
        if row is None:
            raise ValueError("PNG non trovato o relazione non inizializzata.")
        trust = max(-100, min(100, int(row['trust']) + int(trust_change)))
        notes = row['relationship_notes'] if relationship_notes is None else str(relationship_notes).strip()
        connection.execute(
            """UPDATE npc_relationships
               SET trust = ?, relationship_notes = ?, updated_at = CURRENT_TIMESTAMP
               WHERE npc_id = ? AND target = 'protagonista'""",
            (trust, notes, int(npc_id)),
        )
        connection.execute(
            "UPDATE npcs SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (int(npc_id),),
        )
    return trust
