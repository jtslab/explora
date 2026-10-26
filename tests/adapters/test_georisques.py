from collections.abc import Callable

import respx

from explora.adapters.georisques import GeorisquesAdapter, parse_risques
from explora.core.http import SourceClient
from tests.conftest import fixture_json

REPONSE = fixture_json("georisques_risques_35238.json")


@respx.mock
async def test_familles_et_sous_risques(make_client: Callable[..., SourceClient]) -> None:
    respx.get("https://risques.test/gaspar/risques", params={"code_insee": "35238"}).respond(
        json=REPONSE
    )
    async with make_client("https://risques.test") as client:
        risques = await GeorisquesAdapter(client).risques("35238")
    assert risques.risques == [
        "Inondation",
        "Séisme",
        "Phénomène lié à l'atmosphère",
        "Transport de marchandises dangereuses",
    ]
    assert risques.sous_risques == [
        "Par une crue à débordement lent de cours d'eau",
        "Tempête et grains (vent)",
    ]


def test_dedoublonnage() -> None:
    detail = [{"num_risque": "13", "libelle_risque_long": "Séisme"}] * 2
    raw = {"data": [{"risques_detail": detail}, {"risques_detail": detail}]}
    assert parse_risques("35238", raw).risques == ["Séisme"]


def test_commune_inconnue() -> None:
    assert parse_risques("99999", {"results": 0, "data": []}).risques == []
