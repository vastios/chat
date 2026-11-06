"""Regole di combattimento di base; non modifica direttamente il database."""

import random


def calculate_player_damage(strength, weapon_bonus=0):
    """Calcola il danno base inflitto dal personaggio."""
    return max(1, int(strength) // 2 + int(weapon_bonus))


def calculate_enemy_damage(enemy_attack, armor_defense=0):
    """Calcola il danno dopo aver applicato la difesa."""
    return max(0, int(enemy_attack) - int(armor_defense))


def player_attack(strength, weapon_bonus=0):
    """Esegue un attacco con una piccola componente casuale."""
    base_damage = calculate_player_damage(strength, weapon_bonus)
    return max(1, base_damage + random.randint(-1, 2))


def enemy_attack(enemy_strength, armor_defense=0):
    """Simula l'attacco di un nemico."""
    lower = max(1, int(enemy_strength) - 2)
    upper = max(lower, int(enemy_strength) + 2)
    raw_damage = random.randint(lower, upper)
    return calculate_enemy_damage(raw_damage, armor_defense)


def is_enemy_defeated(enemy_hp):
    return int(enemy_hp) <= 0


def is_player_defeated(player_hp):
    return int(player_hp) <= 0
