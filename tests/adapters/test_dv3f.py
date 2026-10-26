from collections.abc import Callable

import pytest
import respx

from explora.adapters.dv3f import Dv3fAdapter, parse_prix
from explora.core.http import SourceClient
from tests.conftest import fixture_json

RENNES = fixture_json("dv3f_prix_35238_extrait.json")
PLATEAU = fixture_json("dv3f_prix_01185_extrait.json")


def test_studios_de_la_derniere_annee() -> None:
    prix = parse_prix("35238", RENNES)
    assert prix is not None
    assert (prix.annee, prix.typologie) == ("2025", "t1")
    assert prix.prix_m2 == pytest.approx(4370.18, abs=0.01)
    assert prix.nb_transactions == 458


def test_repli_sur_tous_les_appartements_sous_le_secret_statistique() -> None:
    prix = parse_prix("01185", PLATEAU)
    assert prix is not None
    assert prix.typologie == "appartements"
    assert prix.prix_m2 == 1250.975
    assert prix.nb_transactions == 12


def test_aucune_vente() -> None:
    assert parse_prix("01185", {"results": []}) is None
    vide = {"results": [{"annee": "2025", "pxm2_median_cod121": None}]}
    assert parse_prix("01185", vide) is None


@respx.mock
async def test_appel_par_commune(make_client: Callable[..., SourceClient]) -> None:
    route = respx.get("https://dv3f.test/indicateurs/dv3f/prix/annuel/").respond(json=RENNES)
    async with make_client("https://dv3f.test") as client:
        prix = await Dv3fAdapter(client).prix("35238")
    assert prix is not None
    assert dict(route.calls.last.request.url.params) == {"code": "35238", "echelle": "communes"}
