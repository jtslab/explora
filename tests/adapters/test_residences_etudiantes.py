from collections.abc import Callable

import pytest
import respx

from explora.adapters.residences_etudiantes import (
    ResidencesEtudiantesAdapter,
    extraire_places,
    parse_flux,
)
from explora.core.http import SourceClient
from tests.conftest import fixture_bytes

XML = fixture_bytes("residences_grenoble_extrait.xml")


def test_parse_flux() -> None:
    residences = {r.nom: r for r in parse_flux(XML.decode())}
    assert len(residences) == 4
    tom_morel = residences["Annecy - Résidence Tom Morel"]
    assert tom_morel.places_estimees == 171
    assert tom_morel.point is not None and tom_morel.point.lat == pytest.approx(45.919, abs=1e-3)
    assert tom_morel.adresse == "12 chemin de Bellevue - 74940 Annecy-le-Vieux"
    assert residences["Saint-Martin-d'Hères - Résidence Ouest"].places_estimees == 1074


def test_places_depuis_la_description_longue() -> None:
    # Description courte sans effectif : on lit le texte détaillé, qui annonce
    # « 83 T2 à partager et 6 studios PMR » (premier effectif seulement : minorant).
    comte_vert = next(r for r in parse_flux(XML.decode()) if "Comte Vert" in r.nom)
    assert comte_vert.places_estimees == 83


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        ("798 chambres de 9 m²", 798),
        ("Le Crous propose 83 places dans la résidence", 83),
        ("78 T1 bis de 29 à 34 m²", 78),
        ("Tarifs au 01/09/2025 318 studios de 20m²", 318),
        ("1 lit, 1 placard, 2 plaques de cuisson", None),
        ("Campus de Schoelcher", None),
    ],
)
def test_extraire_places(texte: str, attendu: int | None) -> None:
    assert extraire_places(texte) == attendu


@respx.mock
async def test_residences(make_client: Callable[..., SourceClient]) -> None:
    respx.get("http://crous.test/feed/grenoble/grenoble-logement.xml").respond(
        content=XML, headers={"Content-Type": "text/xml"}
    )
    async with make_client("http://crous.test") as client:
        residences = await ResidencesEtudiantesAdapter(client).residences("grenoble")
    assert len(residences) == 4
