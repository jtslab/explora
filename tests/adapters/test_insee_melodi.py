from collections.abc import Callable

import pytest
import respx

from explora.adapters.insee_melodi import InseeMelodiAdapter, parse_equipements, parse_logements
from explora.core.http import SourceClient
from tests.conftest import fixture_json

LOGEMENT = fixture_json("melodi_rp_logement_38185.json")
BPE = fixture_json("melodi_bpe_38185_extrait.json")


def test_dernier_recensement() -> None:
    logements = parse_logements("38185", LOGEMENT)
    assert logements is not None
    assert logements.annee == "2023"
    assert logements.residences_principales == pytest.approx(84099.4, abs=0.1)
    assert logements.locataires == pytest.approx(51763.4, abs=0.1)
    assert logements.locataires_meubles == pytest.approx(12124.5, abs=0.1)


def test_commune_sans_donnees() -> None:
    assert parse_logements("99999", {"observations": []}) is None


def test_equipements_hors_totaux() -> None:
    equipements = parse_equipements(BPE)
    assert "_T" not in equipements
    assert equipements["C411"] == 2
    assert len(equipements) == len(BPE["observations"]) - 2


@respx.mock
async def test_logements_un_seul_appel(make_client: Callable[..., SourceClient]) -> None:
    route = respx.get("https://insee.test/data/DS_RP_LOGEMENT_PRINC").respond(json=LOGEMENT)
    async with make_client("https://insee.test") as client:
        logements = await InseeMelodiAdapter(client).logements("38185")
    assert logements is not None
    params = route.calls.last.request.url.params
    assert params["GEO"] == "COM-38185"
    assert params.get_list("TSH") == ["_T", "200", "212_222"]
