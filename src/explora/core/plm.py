"""Paris, Lyon et Marseille : communes publiées par certaines sources à l'arrondissement."""

ARRONDISSEMENTS_PLM = {
    "75056": ("Paris", "751"),
    "69123": ("Lyon", "6938"),
    "13055": ("Marseille", "132"),
}
"""Code INSEE de la commune -> (nom, préfixe des codes d'arrondissement 75101...75120, etc.)."""


def commune_de_rattachement(code_insee: str) -> str:
    """Code de la commune entière pour un arrondissement PLM, sinon le code inchangé."""
    for code, (_, prefixe) in ARRONDISSEMENTS_PLM.items():
        if code_insee.startswith(prefixe):
            return code
    return code_insee
