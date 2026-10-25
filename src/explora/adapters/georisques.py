"""API Géorisques : risques recensés par commune (base GASPAR)."""

from typing import Any

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.models import RisqueCommune


def parse_risques(code_insee: str, raw: dict[str, Any]) -> RisqueCommune:
    """Sépare les familles de risques (code à 2 chiffres, ex. `11` Inondation) de leurs
    sous-risques (code à 3 chiffres, ex. `112` crue lente), que GASPAR mélange."""
    familles: list[str] = []
    sous_risques: list[str] = []
    for commune in raw.get("data", []):
        for risque in commune.get("risques_detail", []):
            libelle = risque.get("libelle_risque_long")
            cible = sous_risques if len(str(risque.get("num_risque", ""))) > 2 else familles
            if libelle and libelle not in cible:
                cible.append(libelle)
    return RisqueCommune(code_insee=code_insee, risques=familles, sous_risques=sous_risques)


class GeorisquesAdapter(SourceAdapter):
    info = SourceInfo(
        id="georisques",
        name="API Géorisques",
        producer="Ministère de la Transition écologique / BRGM",
        licence="Licence Ouverte 2.0",
        url="https://georisques.gouv.fr/doc-api",
        attribution="Géorisques",
        caveats="Limite publiée : 1 000 requêtes par minute et par IP.",
    )

    async def risques(self, code_insee: str) -> RisqueCommune:
        raw = await self.client.get_json("/gaspar/risques", {"code_insee": code_insee})
        return parse_risques(code_insee, raw)
