"""Luoghi e collegamenti iniziali del mondo di gioco."""

KINGDOM_NAME = "Il Regno (nome da definire)"
STARTING_LOCATION = "Locanda del Crocevia"

LOCATIONS = {
    "Locanda del Crocevia": {
        "description": (
            "Una locanda frequentata da mercanti, viaggiatori "
            "e avventurieri. Le conversazioni si interrompono "
            "quando uno sconosciuto entra dalla porta."
        ),
        "region": "Territori centrali",
        "kind": "Locanda",
        "connections": ["Piazza del Mercato", "Strada del Bosco"],
    },
    "Piazza del Mercato": {
        "description": (
            "Una piazza vivace, piena di bancarelle, "
            "artigiani e voci provenienti da ogni angolo."
        ),
        "region": "Territori centrali",
        "kind": "Piazza",
        "connections": ["Locanda del Crocevia"],
    },
    "Strada del Bosco": {
        "description": (
            "Una strada sterrata che si addentra tra alberi "
            "antichi. Dal bosco arrivano rumori difficili da identificare."
        ),
        "region": "Confine del Bosco",
        "kind": "Strada",
        "connections": ["Locanda del Crocevia"],
    },
}


def get_location(location_name):
    """Restituisce le informazioni di un luogo."""
    return LOCATIONS.get(location_name)


def get_available_locations(location_name):
    """Restituisce i luoghi collegati alla posizione attuale."""
    location = get_location(location_name)
    if location is None:
        return []
    return location["connections"]
