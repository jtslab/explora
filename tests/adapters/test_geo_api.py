"""Réponses simulées : format réel de geo.api.gouv.fr (voir `tests/fixtures`)."""

from collections.abc import Callable

import respx

from explora.adapters.geo_api import GeoApiAdapter
from explora.core.http import SourceClient
from explora.core.models import Point
from tests.conftest import fixture_json

RENNES = fixture_json("geo_api_commune_35238.json")


@respx.mock
async def test_commune(make_client: Callable[..., SourceClient]) -> None:
    respx.get("https://geo.test/communes/35238").respond(json=RENNES)
    async with make_client("https://geo.test") as client:
        commune = await GeoApiAdapter(client).commune("35238")
    assert commune.nom == "Rennes"
    assert commune.code_departement == "35"
    assert commune.centre is not None
    assert commune.centre.lat == 48.1159
    assert commune.codes_postaux == ["35000", "35200", "35700"]


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


@respx.mock
async def test_toutes_les_communes(make_client: Callable[..., SourceClient]) -> None:
    route = respx.get("https://geo.test/communes").respond(json=[RENNES])
    async with make_client("https://geo.test") as client:
        communes = await GeoApiAdapter(client).communes()
    assert [c.code_insee for c in communes] == ["35238"]
    assert "population" in route.calls.last.request.url.params["fields"]


@respx.mock
async def test_code_au_point(make_client: Callable[..., SourceClient]) -> None:
    route = respx.get("https://geo.test/communes").respond(json=[{"code": "74010"}])
    async with make_client("https://geo.test") as client:
        code = await GeoApiAdapter(client).code_au_point(Point(lon=6.16, lat=45.92))
    assert code == "74010"
    assert route.calls.last.request.url.params["lat"] == "45.92"


@respx.mock
async def test_point_hors_de_france(make_client: Callable[..., SourceClient]) -> None:
    respx.get("https://geo.test/communes").respond(json=[])
    async with make_client("https://geo.test") as client:
        assert await GeoApiAdapter(client).code_au_point(Point(lon=0, lat=0)) is None
