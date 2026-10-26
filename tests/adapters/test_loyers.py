from collections.abc import Callable

import pytest
import respx

from explora.adapters.loyers import LoyersAdapter, parse_csv
from explora.core.http import SourceClient
from tests.conftest import fixture_bytes

# Octets d'origine du millésime 2025 : Windows-1252 et CRLF, servis en `charset=utf-8`.
CSV_REEL = fixture_bytes("loyers_app12_extrait.csv")

CSV_UTF8 = (
    "﻿id_zone;INSEE_C;LIBGEO;EPCI;DEP;REG;loypredm2;lwr.IPm2;upr.IPm2;TYPPRED;"
    "nbobs_com;nbobs_mail;R2_adj\n"
    "1;35238;Rennes;243500139;35;53;15,2;12,1;19,0;commune;4210;4210;0,71\n"
    "2;1001;L'Abergement-Clémenciat;200069193;01;84;9,8;7,0;13,5;maille;3;120;0,42\n"
    "3;35001;Acigné;243500139;35;53;NA;NA;NA;maille;0;80;NA\n"
)


def test_parse_csv() -> None:
    loyers = parse_csv(CSV_UTF8, "appartement")
    assert [loyer.code_insee for loyer in loyers] == ["35238", "01001"]
    rennes, petite = loyers
    assert rennes.loyer_m2 == 15.2
    assert rennes.fiable
    assert not petite.fiable
    assert petite.niveau_prediction == "maille"


def test_paris_lyon_agreges_depuis_les_arrondissements() -> None:
    loyers = {loyer.code_insee: loyer for loyer in parse_csv(CSV_REEL.decode("cp1252"), "t1t2")}
    paris = loyers["75056"]
    attendu = (38.1101189200412 * 2403 + 30.9630260902438 * 11187) / (2403 + 11187)
    assert paris.nom == "Paris"
    assert paris.loyer_m2 == pytest.approx(attendu)
    assert paris.nb_observations == 2403 + 11187
    assert paris.niveau_prediction == "arrondissements"
    assert loyers["69123"].loyer_m2 == pytest.approx(19.6723304671415)
    assert "13055" not in loyers


@respx.mock
async def test_telechargement_encodage_windows_1252(
    make_client: Callable[..., SourceClient],
) -> None:
    respx.get("https://data.test/api/1/datasets/r/abc").respond(
        content=CSV_REEL, headers={"Content-Type": "text/csv; charset=utf-8"}
    )
    async with make_client("https://data.test") as client:
        loyers = await LoyersAdapter(client).loyers("/api/1/datasets/r/abc", "t1t2")
    par_code = {loyer.code_insee: loyer for loyer in loyers}
    assert par_code["01001"].nom == "L'Abergement-Clémenciat"
    assert par_code["35238"].loyer_m2 == pytest.approx(17.186133652377)
    assert par_code["35238"].fiable


@respx.mock
async def test_telechargement_utf8(make_client: Callable[..., SourceClient]) -> None:
    respx.get("https://data.test/api/1/datasets/r/abc").respond(
        content=CSV_UTF8.encode(), headers={"Content-Type": "text/csv"}
    )
    async with make_client("https://data.test") as client:
        loyers = await LoyersAdapter(client).loyers("/api/1/datasets/r/abc", "appartement")
    assert [loyer.nom for loyer in loyers] == ["Rennes", "L'Abergement-Clémenciat"]
