"""Indicateurs clés du module villes étudiantes.

Tous les indicateurs renvoient `None` quand une donnée manque, pour ne jamais
afficher une valeur inventée.
"""


def rendement_locatif_brut(loyer_m2_mensuel: float | None, prix_m2: float | None) -> float | None:
    """Loyer annuel ÷ prix d'achat, à surface égale (la surface du studio s'annule).

    Valeur indicative, pas un conseil en investissement.
    """
    if loyer_m2_mensuel is None or not prix_m2:
        return None
    return loyer_m2_mensuel * 12 / prix_m2


def tension_locative(etudiants: int | None, places_logement: int | None) -> float | None:
    """Nombre d'étudiants par place de logement étudiant public ou conventionné."""
    if etudiants is None or not places_logement:
        return None
    return etudiants / places_logement


def vitalite_commerciale(creations: int | None, fermetures: int | None) -> int | None:
    """Solde créations - fermetures d'établissements sur la période (3 ans)."""
    if creations is None or fermetures is None:
        return None
    return creations - fermetures
