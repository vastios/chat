"""Operazioni di alto livello relative all'inventario."""

from game.database import (
    ITEM_RULES,
    add_inventory_item,
    equip_item,
    load_game_state,
    remove_inventory_item,
    use_healing_potion,
)


def get_inventory():
    """Restituisce la lista degli oggetti posseduti."""
    return load_game_state().get("inventory", [])


def add_item(item_name, quantity=1):
    """Aggiunge una quantità di un oggetto."""
    add_inventory_item(item_name, int(quantity))


def remove_item(item_name, quantity=1):
    """Rimuove una quantità di un oggetto e restituisce quanti ne ha rimossi."""
    return remove_inventory_item(item_name, int(quantity))


def equip(item_name):
    """Equipaggia l'oggetto usando lo slot definito nelle regole."""
    rule = ITEM_RULES.get(item_name)
    if rule is None:
        return False
    return equip_item(item_name, rule["type"])


def drink_healing_potion():
    """Usa una pozione curativa, se disponibile."""
    return use_healing_potion()
