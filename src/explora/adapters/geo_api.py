"""API Découpage administratif (geo.api.gouv.fr)."""

from typing import Any

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.errors import SourceError
from explora.core.models import Commune, Point

FIELDS = "nom,code,codeDepartement,codeRegion,codesPostaux,population,centre"


def parse_commune(raw: dict[str, Any]) -> Commune:
    centre = raw.get("centre")
    point = None
    if centre and centre.get("type") == "Point":
        lon, lat = centre["coordinates"]
        point = Point(lon=lon, lat=lat)
    return Commune(
        code_insee=raw["code"],
        nom=raw["nom"],
        code_departement=raw["codeDepartement"],
        code_region=raw.get("codeRegion"),
        codes_postaux=raw.get("codesPostaux", []),
        population=raw.get("population"),
        centre=point,
    )


class GeoApiAdapter(SourceAdapter):
    info = SourceInfo(
        id="geo-api",
        name="API Découpage administratif",
        producer="DINUM / Etalab",
        licence="Licence Ouverte 2.0",
        url="https://geo.api.gouv.fr",
        attribution="geo.api.gouv.fr",
    )

    async def commune(self, code_insee: str) -> Commune:
        raw = await self.client.get_json(f"/communes/{code_insee}", {"fields": FIELDS})
        if not isinstance(raw, dict):
            raise SourceError(self.info.id, f"commune {code_insee} : réponse inattendue")
        return parse_commune(raw)

    async def communes_du_departement(self, code_departement: str) -> list[Commune]:
        raw = await self.client.get_json(
            f"/departements/{code_departement}/communes", {"fields": FIELDS}
        )
        if not isinstance(raw, list):
            raise SourceError(self.info.id, f"département {code_departement} : réponse inattendue")
        return [parse_commune(item) for item in raw]

    async def communes(self) -> list[Commune]:
        """Toutes les communes (~35 000, sans les arrondissements de Paris, Lyon et Marseille)."""
        raw = await self.client.get_json("/communes", {"fields": FIELDS})
        if not isinstance(raw, list):
            raise SourceError(self.info.id, "liste des communes : réponse inattendue")
        return [parse_commune(item) for item in raw]
