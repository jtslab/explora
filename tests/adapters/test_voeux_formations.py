from collections.abc import Callable

import httpx
import respx

from explora.adapters.voeux_formations import VoeuxFormationsAdapter, parse_formation
from explora.core.http import SourceClient
from tests.conftest import fixture_json

REPONSE = fixture_json("parcoursup_voeux_38_extrait.json")
URL = "https://edu.test/catalog/datasets/fr-esr-parcoursup/records"


def test_parse_formation() -> None:
    formation = parse_formation(REPONSE["results"][1])
    assert formation.etablissement == "Polytech Grenoble"
    assert formation.ville == "Saint-Martin-d'Hères"
    assert formation.filiere == "Ecole d'Ingénieur"
    assert (formation.capacite, formation.voeux, formation.admis) == (135, 10959, 158)
    assert formation.point is not None and formation.point.lat == 45.1849


def test_arrondissement_parisien_normalise() -> None:
    row = {"ville_etab": "Paris  5e  Arrondissement", "g_olocalisation_des_formations": None}
    formation = parse_formation(row)
    assert formation.ville == "Paris 5e Arrondissement"
    assert formation.point is None


@respx.mock
async def test_pagination(make_client: Callable[..., SourceClient]) -> None:
    def page(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        assert request.url.params["where"] == 'dep="38"'
        rows = REPONSE["results"] if offset < 200 else REPONSE["results"][:1]
        return httpx.Response(200, json={"total_count": 201, "results": rows})

    route = respx.get(URL).mock(side_effect=page)
    async with make_client("https://edu.test") as client:
        formations = await VoeuxFormationsAdapter(client).formations("38")
    assert route.call_count == 3
    assert len(formations) == 7
