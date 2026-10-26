"""Adaptateurs, un par source de données publiques."""

from explora.adapters.geo_api import GeoApiAdapter
from explora.adapters.geocodage import GeocodageAdapter
from explora.adapters.georisques import GeorisquesAdapter
from explora.adapters.insee_melodi import InseeMelodiAdapter
from explora.adapters.loyers import LoyersAdapter
from explora.adapters.residences_etudiantes import ResidencesEtudiantesAdapter
from explora.adapters.voeux_formations import VoeuxFormationsAdapter

ALL_ADAPTERS = (
    GeoApiAdapter,
    GeocodageAdapter,
    GeorisquesAdapter,
    InseeMelodiAdapter,
    LoyersAdapter,
    ResidencesEtudiantesAdapter,
    VoeuxFormationsAdapter,
)

__all__ = [
    "ALL_ADAPTERS",
    "GeoApiAdapter",
    "GeocodageAdapter",
    "GeorisquesAdapter",
    "InseeMelodiAdapter",
    "LoyersAdapter",
    "ResidencesEtudiantesAdapter",
    "VoeuxFormationsAdapter",
]
