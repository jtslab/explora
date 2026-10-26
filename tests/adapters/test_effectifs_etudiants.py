"""Réponses simulées : format réel de l'export Opendatasoft du MESR (voir `tests/fixtures`)."""

from collections.abc import Callable

import pytest
import respx

from explora.adapters.effectifs_etudiants import (
    EffectifsEtudiantsAdapter,
    code_departement,
    parse_effectif,
)
from explora.core.http import SourceClient
from tests.conftest import fixture_json

EXTRAIT = fixture_json("atlas_effectifs_extrait.json")
URL = (
    "https://esr.test/catalog/datasets/"
    "fr-esr-atlas_regional-effectifs-d-etudiants-inscrits/exports/json"
)


@pytest.mark.parametrize(
    ("dep_id", "attendu"),
    [("D035", "35"), ("D001", "01"), ("D02A", "2A"), ("D971", "971"), ("D976", "976")],
)
def test_code_departement(dep_id: str, attendu: str) -> None:
    assert code_departement(dep_id) == attendu


def test_parse_effectif() -> None:
    total = next(r for r in EXTRAIT if r["geo_id"] == "90094" and r["regroupement"] == "TOTAL")
    eff = parse_effectif(total)
    assert (eff.nom, eff.code_departement, eff.effectif) == ("Sevenans", "90", 1264)
    assert eff.unite_urbaine is not None


@respx.mock
async def test_par_commune(make_client: Callable[..., SourceClient]) -> None:
    route = respx.get(URL).respond(json=EXTRAIT)
    async with make_client("https://esr.test") as client:
        effectifs = await EffectifsEtudiantsAdapter(client).par_commune("2025")
    params = route.calls.last.request.url.params
    assert params["where"] == "rentree='2025' and niveau_geo='COMMUNE'"
    assert "regroupement" in params["group_by"]
    assert len(effectifs) == len(EXTRAIT)
    ajaccio = [e for e in effectifs if e.code_insee == "2A004"]
    assert {e.code_departement for e in ajaccio} == {"2A"}
