"""Operazioni di alto livello relative al personaggio."""

from game.database import load_game_state, update_character


def get_character():
    """Restituisce lo stato attuale del personaggio."""
    return load_game_state()


def change_hit_points(amount):
    """Modifica i punti ferita rispettando i limiti previsti."""
    update_character(hp_change=int(amount))


def change_gold(amount):
    """Modifica l'oro senza permettere un saldo negativo."""
    update_character(gold_change=int(amount))
