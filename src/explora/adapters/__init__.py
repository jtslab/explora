"""Adaptateurs, un par source de données publiques."""

from explora.adapters.geo_api import GeoApiAdapter
from explora.adapters.geocodage import GeocodageAdapter
from explora.adapters.georisques import GeorisquesAdapter
from explora.adapters.loyers import LoyersAdapter

ALL_ADAPTERS = (GeoApiAdapter, GeocodageAdapter, GeorisquesAdapter, LoyersAdapter)

__all__ = [
    "ALL_ADAPTERS",
    "GeoApiAdapter",
    "GeocodageAdapter",
    "GeorisquesAdapter",
    "LoyersAdapter",
]
