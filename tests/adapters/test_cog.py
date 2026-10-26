from collections.abc import Callable

import respx

from explora.adapters.cog import DEPARTEMENTS_2025, CogAdapter
from explora.core.http import SourceClient
from tests.conftest import fixture_bytes


@respx.mock
async def test_departements(make_client: Callable[..., SourceClient]) -> None:
    respx.get(f"https://insee.test{DEPARTEMENTS_2025}").respond(
        content=fixture_bytes("cog_departements_extrait.csv")
    )
    async with make_client("https://insee.test") as client:
        deps = await CogAdapter(client).departements()
    assert [(d.code, d.chef_lieu) for d in deps] == [
        ("01", "01053"),
        ("2A", "2A004"),
        ("75", "75056"),
        ("971", "97105"),
    ]
    assert deps[1].nom == "Corse-du-Sud"
