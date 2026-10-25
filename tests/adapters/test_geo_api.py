"""Les réponses simulées reprennent le format documenté de geo.api.gouv.fr."""

from collections.abc import Callable

import respx

from explora.adapters.geo_api import GeoApiAdapter
from explora.core.http import SourceClient

RENNES = {
    "nom": "Rennes",
    "code": "35238",
    "codeDepartement": "35",
    "codeRegion": "53",
    "codesPostaux": ["35000", "35200", "35700"],
    "population": 225081,
    "centre": {"type": "Point", "coordinates": [-1.6743, 48.112]},
}


@respx.mock
async def test_commune(make_client: Callable[..., SourceClient]) -> None:
    respx.get("https://geo.test/communes/35238").respond(json=RENNES)
    async with make_client("https://geo.test") as client:
        commune = await GeoApiAdapter(client).commune("35238")
    assert commune.nom == "Rennes"
    assert commune.code_departement == "35"
    assert commune.centre is not None
    assert commune.centre.lat == 48.112


@respx.mock
async def test_communes_du_departement_sans_centre(
    make_client: Callable[..., SourceClient],
) -> None:
    corse = {"nom": "Ajaccio", "code": "2A004", "codeDepartement": "2A"}
    respx.get("https://geo.test/departements/2A/communes").respond(json=[corse])
    async with make_client("https://geo.test") as client:
        communes = await GeoApiAdapter(client).communes_du_departement("2A")
    assert [c.code_insee for c in communes] == ["2A004"]
    assert communes[0].centre is None
