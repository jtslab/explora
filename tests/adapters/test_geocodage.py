"""Réponse GeoJSON au format documenté du géocodeur de la Géoplateforme."""

from collections.abc import Callable

import respx

from explora.adapters.geocodage import GeocodageAdapter
from explora.core.http import SourceClient

REPONSE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-1.6778, 48.1173]},
            "properties": {
                "label": "Rennes",
                "score": 0.97,
                "type": "municipality",
                "citycode": "35238",
                "city": "Rennes",
                "postcode": "35000",
            },
        }
    ],
}


@respx.mock
async def test_search(make_client: Callable[..., SourceClient]) -> None:
    route = respx.get("https://geo.test/search").respond(json=REPONSE)
    async with make_client("https://geo.test") as client:
        results = await GeocodageAdapter(client).search("rennes", limit=1, type="municipality")
    assert route.calls.last.request.url.params["type"] == "municipality"
    assert "citycode" not in route.calls.last.request.url.params
    assert results[0].code_insee == "35238"
    assert results[0].point.lon == -1.6778


@respx.mock
async def test_search_vide(make_client: Callable[..., SourceClient]) -> None:
    respx.get("https://geo.test/search").respond(json={"features": []})
    async with make_client("https://geo.test") as client:
        assert await GeocodageAdapter(client).search("zzzz") == []
