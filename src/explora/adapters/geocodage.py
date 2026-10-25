"""Géocodage de la Géoplateforme IGN (successeur de l'API Adresse / BAN)."""

from typing import Any

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.models import GeocodeResult, Point


def parse_features(raw: dict[str, Any]) -> list[GeocodeResult]:
    results = []
    for feature in raw.get("features", []):
        props = feature.get("properties", {})
        lon, lat = feature["geometry"]["coordinates"]
        results.append(
            GeocodeResult(
                label=props["label"],
                score=props.get("score", 0.0),
                point=Point(lon=lon, lat=lat),
                code_insee=props.get("citycode"),
                commune=props.get("city"),
                code_postal=props.get("postcode"),
                type=props.get("type"),
            )
        )
    return results


class GeocodageAdapter(SourceAdapter):
    info = SourceInfo(
        id="geocodage",
        name="Service de géocodage de la Géoplateforme",
        producer="IGN",
        licence="Licence Ouverte 2.0",
        url="https://geoservices.ign.fr/documentation/services/services-geoplateforme/geocodage",
        attribution="IGN - Géoplateforme, données BAN",
    )

    async def search(
        self, q: str, *, limit: int = 5, citycode: str | None = None, type: str | None = None
    ) -> list[GeocodeResult]:
        raw = await self.client.get_json(
            "/search", {"q": q, "limit": limit, "citycode": citycode, "type": type}
        )
        return parse_features(raw)
