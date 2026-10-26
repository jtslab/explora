import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from explora.adapters.geo_api import GeoApiAdapter
from explora.api.deps import geo_api
from explora.api.main import app
from explora.core.config import get_settings
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


@pytest.fixture
def export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    chemin = tmp_path / "villes.geojson"
    monkeypatch.setattr(get_settings(), "export_villes_etudiantes", chemin)
    return chemin


def ecrire(chemin: Path, geojson: dict[str, Any]) -> None:
    chemin.write_text(json.dumps(geojson), encoding="utf-8")


async def test_villes_ponderation(api: httpx.AsyncClient, export: Path) -> None:
    axes = {"etudes": 80.0, "budget": 20.0, "vie": None, "mobilite_cadre": 50.0}
    feature = {"type": "Feature", "geometry": None, "properties": {"axes": axes, "score": 50.0}}
    ecrire(export, {"type": "FeatureCollection", "metadata": {}, "features": [feature]})
    defaut = (await api.get("/etudiant/villes")).json()
    assert defaut["features"][0]["properties"]["score"] == 50.0
    assert defaut["features"][0]["properties"]["couverture"] == 0.75
    budget = (await api.get("/etudiant/villes", params={"etudes": 0, "budget": 3})).json()
    props = budget["features"][0]["properties"]
    assert props["score"] == 27.5  # (3 x 20 + 50) / 4
    assert budget["metadata"]["poids"]["budget"] == 3
    assert (await api.get("/etudiant/villes", params={"etudes": -1})).status_code == 422
    zero = {"etudes": 0, "budget": 0, "vie": 0, "mobilite_cadre": 0}
    assert (await api.get("/etudiant/villes", params=zero)).status_code == 422


async def test_villes_export_absent(api: httpx.AsyncClient, export: Path) -> None:
    assert (await api.get("/etudiant/villes")).status_code == 503
