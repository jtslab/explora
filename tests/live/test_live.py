"""Appels réels aux API publiques : `uv run pytest -m live`.

Désactivés par défaut (CI comprise) : ils dépendent du réseau et de la disponibilité
des sources. Ils vérifient que les adaptateurs comprennent toujours les vraies réponses.
"""

import pytest

from explora.adapters import (
    GeoApiAdapter,
    GeocodageAdapter,
    GeorisquesAdapter,
    InseeMelodiAdapter,
    LoyersAdapter,
    ResidencesEtudiantesAdapter,
    VoeuxFormationsAdapter,
)
from explora.core.config import get_settings
from explora.core.http import RetryPolicy, SourceClient

pytestmark = pytest.mark.live

# Ressource « appartement 1-2 pièces » de la carte des loyers 2025.
LOYERS_T1T2 = "/api/1/datasets/r/14a1fe11-b2d1-49b3-9f6b-83d12df9482c"


def client(source: str, base_url: str) -> SourceClient:
    settings = get_settings()
    return SourceClient(
        source,
        base_url,
        retry=RetryPolicy(max_attempts=10),
        timeout_s=60,
        user_agent=settings.http_user_agent,
    )


async def test_geo_api() -> None:
    async with client("geo-api", get_settings().geo_api_url) as c:
        rennes = await GeoApiAdapter(c).commune("35238")
        corse = await GeoApiAdapter(c).communes_du_departement("2A")
    assert rennes.nom == "Rennes"
    assert rennes.centre is not None
    assert rennes.population and rennes.population > 200_000
    assert "2A004" in {commune.code_insee for commune in corse}


async def test_geocodage() -> None:
    async with client("geocodage", get_settings().geocodage_url) as c:
        results = await GeocodageAdapter(c).search("rennes", limit=1, type="municipality")
    assert results[0].code_insee == "35238"


async def test_georisques() -> None:
    async with client("georisques", get_settings().georisques_url) as c:
        risques = await GeorisquesAdapter(c).risques("35238")
    assert "Inondation" in risques.risques
    assert all(r not in risques.risques for r in risques.sous_risques)


async def test_loyers() -> None:
    async with client("carte-loyers", "https://www.data.gouv.fr") as c:
        loyers = await LoyersAdapter(c).loyers(LOYERS_T1T2, "t1t2")
    par_code = {loyer.code_insee: loyer for loyer in loyers}
    assert len(par_code) > 34_000
    assert par_code["01001"].nom == "L'Abergement-Clémenciat"
    for code in ("75056", "69123", "13055", "35238"):
        assert par_code[code].fiable, code


async def test_voeux_formations() -> None:
    async with client("voeux-formations", get_settings().voeux_formations_url) as c:
        formations = await VoeuxFormationsAdapter(c).formations("38")
    assert len(formations) > 200
    assert {"BTS", "BUT", "Licence"} <= {f.filiere for f in formations}
    assert any(f.ville == "Grenoble" and f.capacite for f in formations)


async def test_residences_etudiantes() -> None:
    async with client("residences-etudiantes", get_settings().residences_etudiantes_url) as c:
        residences = await ResidencesEtudiantesAdapter(c).residences("grenoble")
    assert len(residences) > 30
    assert all(r.point for r in residences)
    avec_places = [r for r in residences if r.places_estimees]
    assert len(avec_places) > len(residences) / 2


async def test_insee_melodi() -> None:
    async with client("insee-melodi", get_settings().insee_melodi_url) as c:
        adapter = InseeMelodiAdapter(c)
        logements = await adapter.logements("38185")
        equipements = await adapter.equipements("38185", "2025")
    assert logements is not None and logements.annee >= "2022"
    assert logements.locataires and logements.residences_principales
    assert 0.4 < logements.locataires / logements.residences_principales < 0.8
    assert equipements["A504"] > 100  # restaurants
