from collections.abc import Callable

import respx

from explora.adapters.georisques import GeorisquesAdapter
from explora.core.http import SourceClient

REPONSE = {
    "data": [
        {
            "code_insee": "35238",
            "libelle_commune": "Rennes",
            "risques_detail": [
                {"num_risque": "11", "libelle_risque_long": "Inondation"},
                {"num_risque": "13", "libelle_risque_long": "Séisme"},
                {"num_risque": "11", "libelle_risque_long": "Inondation"},
            ],
        }
    ]
}


@respx.mock
async def test_risques_dedoublonnes(make_client: Callable[..., SourceClient]) -> None:
    respx.get("https://risques.test/gaspar/risques", params={"code_insee": "35238"}).respond(
        json=REPONSE
    )
    async with make_client("https://risques.test") as client:
        risques = await GeorisquesAdapter(client).risques("35238")
    assert risques.risques == ["Inondation", "Séisme"]
