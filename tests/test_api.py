from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from explora.adapters.geo_api import GeoApiAdapter
from explora.api.deps import geo_api
from explora.api.main import app
from explora.core.http import RetryPolicy, SourceClient


async def _fake_geo_api() -> AsyncIterator[GeoApiAdapter]:
    async def no_sleep(_: float) -> None:
        return None

    async with SourceClient(
        "geo-api", "https://geo.test", retry=RetryPolicy(max_attempts=2), sleep=no_sleep
    ) as client:
        yield GeoApiAdapter(client)


@pytest.fixture
async def api() -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[geo_api] = _fake_geo_api
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://app") as client:
        yield client
    app.dependency_overrides.clear()


async def test_health(api: httpx.AsyncClient) -> None:
    response = await api.get("/health")
    assert response.json()["status"] == "ok"


async def test_sources_citent_les_attributions(api: httpx.AsyncClient) -> None:
    sources = (await api.get("/sources")).json()
    assert {s["id"] for s in sources} >= {"geo-api", "carte-loyers"}
    assert all(s["licence"] and s["attribution"] for s in sources)


@respx.mock
async def test_commune(api: httpx.AsyncClient) -> None:
    respx.get("https://geo.test/communes/35238").respond(
        json={"nom": "Rennes", "code": "35238", "codeDepartement": "35"}
    )
    response = await api.get("/communes/35238")
    assert response.status_code == 200, response.text
    assert response.json()["nom"] == "Rennes"


@respx.mock
async def test_commune_inconnue_et_source_hs(api: httpx.AsyncClient) -> None:
    respx.get("https://geo.test/communes/99999").respond(404)
    respx.get("https://geo.test/communes/35238").respond(503)
    assert (await api.get("/communes/99999")).status_code == 404
    assert (await api.get("/communes/35238")).status_code == 503
    assert (await api.get("/communes/abc")).status_code == 422
