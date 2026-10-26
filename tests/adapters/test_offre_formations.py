from collections.abc import Callable

import httpx
import respx

from explora.adapters.offre_formations import OffreFormationsAdapter, parse_offre
from explora.core.http import SourceClient
from tests.conftest import fixture_json

REPONSE = fixture_json("offre_formations_extrait.json")
URL = "https://edu.test/catalog/datasets/fr-esr-cartographie_formations_parcoursup/exports/json"


def test_parse_offre() -> None:
    offre = parse_offre(REPONSE[1])
    assert offre.commune == "Rennes"
    assert offre.departement == "Ille-et-Vilaine"
    assert offre.mentions == ["D.E Educateur Technique Spécialisé"]
    assert offre.apprentissage
    assert offre.code == "26021"
    assert offre.point is not None
    assert not parse_offre(REPONSE[0]).apprentissage


@respx.mock
async def test_offres(make_client: Callable[..., SourceClient]) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=REPONSE))
    async with make_client("https://edu.test") as client:
        offres = await OffreFormationsAdapter(client).offres("2026")
    assert route.calls.last.request.url.params["where"] == 'annee="2026"'
    assert len(offres) == len(REPONSE)
