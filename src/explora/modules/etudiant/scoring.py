"""Score « ville étudiante » sur 4 axes avec pondération réglable.

Chaque indicateur est d'abord ramené sur 0-100 par rang centile parmi les
villes comparées, dans le sens où « plus haut = mieux pour un étudiant ».
Un axe est la moyenne de ses indicateurs disponibles ; le score global est la
moyenne pondérée des axes disponibles (les poids sont renormalisés quand un
axe manque, et la couverture est renvoyée pour l'afficher).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class Axe(StrEnum):
    ETUDES = "etudes"
    BUDGET = "budget"
    VIE = "vie"
    MOBILITE_CADRE = "mobilite_cadre"


@dataclass(frozen=True)
class Indicateur:
    id: str
    axe: Axe
    plus_haut_est_mieux: bool


INDICATEURS: tuple[Indicateur, ...] = (
    Indicateur("effectifs_etudiants", Axe.ETUDES, True),
    Indicateur("nb_etablissements", Axe.ETUDES, True),
    Indicateur("nb_filieres", Axe.ETUDES, True),
    Indicateur("loyer_m2", Axe.BUDGET, False),
    Indicateur("prix_m2", Axe.BUDGET, False),
    Indicateur("tension_locative", Axe.BUDGET, False),
    Indicateur("commerces_pour_1000", Axe.VIE, True),
    Indicateur("equipements_culture_sport_pour_1000", Axe.VIE, True),
    Indicateur("vitalite_commerciale", Axe.VIE, True),
    Indicateur("arrets_transport_pour_1000", Axe.MOBILITE_CADRE, True),
    Indicateur("stations_velo", Axe.MOBILITE_CADRE, True),
    Indicateur("indice_qualite_air", Axe.MOBILITE_CADRE, False),
    Indicateur("nb_risques", Axe.MOBILITE_CADRE, False),
)

POIDS_PAR_DEFAUT: Mapping[Axe, float] = {axe: 1.0 for axe in Axe}

Valeurs = Mapping[str, float | None]


@dataclass(frozen=True)
class ScoreVille:
    code_insee: str
    global_: float | None
    axes: Mapping[Axe, float | None]
    couverture: float
    """Part des poids effectivement couverte par des données (0-1)."""


def rang_centile(valeur: float, population: Sequence[float]) -> float:
    """Rang centile (0-100) de `valeur`, ex æquo comptés pour moitié."""
    if len(population) <= 1:
        return 50.0
    inferieurs = sum(1 for v in population if v < valeur)
    egaux = sum(1 for v in population if v == valeur)
    return 100.0 * (inferieurs + 0.5 * (egaux - 1)) / (len(population) - 1)


def _valider_poids(poids: Mapping[Axe, float]) -> None:
    if any(p < 0 for p in poids.values()):
        raise ValueError("les poids doivent être positifs ou nuls")
    if sum(poids.values()) == 0:
        raise ValueError("au moins un poids doit être non nul")


def scorer(
    villes: Mapping[str, Valeurs], poids: Mapping[Axe, float] = POIDS_PAR_DEFAUT
) -> dict[str, ScoreVille]:
    """Calcule le score de chaque ville relativement aux autres villes fournies."""
    _valider_poids(poids)
    populations: dict[str, list[float]] = {
        ind.id: [v for vals in villes.values() if (v := vals.get(ind.id)) is not None]
        for ind in INDICATEURS
    }
    resultats: dict[str, ScoreVille] = {}
    for code, valeurs in villes.items():
        notes_par_axe: dict[Axe, list[float]] = {axe: [] for axe in Axe}
        for ind in INDICATEURS:
            valeur = valeurs.get(ind.id)
            if valeur is None:
                continue
            note = rang_centile(valeur, populations[ind.id])
            notes_par_axe[ind.axe].append(note if ind.plus_haut_est_mieux else 100.0 - note)
        axes: dict[Axe, float | None] = {
            axe: (sum(notes) / len(notes) if notes else None)
            for axe, notes in notes_par_axe.items()
        }
        total_poids = sum(poids.get(axe, 0.0) for axe in Axe)
        poids_couverts = sum(poids.get(a, 0.0) for a, note in axes.items() if note is not None)
        global_ = (
            sum(poids.get(a, 0.0) * note for a, note in axes.items() if note is not None)
            / poids_couverts
            if poids_couverts
            else None
        )
        resultats[code] = ScoreVille(
            code_insee=code,
            global_=global_,
            axes=axes,
            couverture=poids_couverts / total_poids,
        )
    return resultats
