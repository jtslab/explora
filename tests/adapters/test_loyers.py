from collections.abc import Callable

import respx

from explora.adapters.loyers import LoyersAdapter, parse_csv
from explora.core.http import SourceClient

CSV = (
    "﻿id_zone;INSEE_C;LIBGEO;EPCI;DEP;REG;loypredm2;lwr.IPm2;upr.IPm2;TYPPRED;"
    "nbobs_com;nbobs_mail;R2_adj\n"
    "1;35238;Rennes;243500139;35;53;15,2;12,1;19,0;commune;4210;4210;0,71\n"
    "2;1001;L'Abergement-Clémenciat;200069193;01;84;9,8;7,0;13,5;maille;3;120;0,42\n"
    "3;35001;Acigné;243500139;35;53;NA;NA;NA;maille;0;80;NA\n"
)


def test_parse_csv() -> None:
    loyers = parse_csv(CSV, "appartement")
    assert [loyer.code_insee for loyer in loyers] == ["35238", "01001"]
    rennes, petite = loyers
    assert rennes.loyer_m2 == 15.2
    assert rennes.fiable
    assert not petite.fiable
    assert petite.niveau_prediction == "maille"


@respx.mock
async def test_telechargement(make_client: Callable[..., SourceClient]) -> None:
    respx.get("https://data.test/api/1/datasets/r/abc").respond(text=CSV)
    async with make_client("https://data.test") as client:
        loyers = await LoyersAdapter(client).loyers("/api/1/datasets/r/abc", "appartement")
    assert len(loyers) == 2
