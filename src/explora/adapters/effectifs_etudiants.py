"""Atlas régional des effectifs d'étudiants inscrits (MESR), agrégé par commune."""

from typing import Any

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.errors import SourceError
from explora.core.models import EffectifCommune

EXPORT = "/catalog/datasets/fr-esr-atlas_regional-effectifs-d-etudiants-inscrits/exports/json"


def code_departement(dep_id: str) -> str:
    """`D035` -> `35`, `D02A` -> `2A`, `D971` -> `971`."""
    code = dep_id.removeprefix("D")
    return code[1:] if len(code) == 3 and code.startswith("0") else code


def parse_effectif(row: dict[str, Any]) -> EffectifCommune:
    return EffectifCommune(
        code_insee=row["geo_id"],
        nom=row["geo_nom"],
        code_departement=code_departement(row["dep_id"]),
        unite_urbaine=row.get("uucr_id"),
        regroupement=row["regroupement"],
        effectif=int(row.get("effectif") or 0),
    )


class EffectifsEtudiantsAdapter(SourceAdapter):
    info = SourceInfo(
        id="effectifs-etudiants",
        name="Atlas régional des effectifs d'étudiants inscrits",
        producer="Ministère de l'Enseignement supérieur (SIES)",
        licence="Licence Ouverte 2.0",
        url=(
            "https://data.enseignementsup-recherche.gouv.fr/explore/dataset/"
            "fr-esr-atlas_regional-effectifs-d-etudiants-inscrits/"
        ),
        attribution="MESR-SIES, atlas régional des effectifs étudiants",
        caveats=(
            "Commune d'implantation de la formation, pas du logement de l'étudiant. "
            "Effectifs hors doubles inscriptions CPGE-université."
        ),
    )

    async def par_commune(self, rentree: str) -> list[EffectifCommune]:
        """Effectifs d'une rentrée par commune et regroupement de formations.

        L'export agrège côté serveur (secteurs public et privé, sexes) : une seule
        requête pour toute la France (~5 000 lignes).
        """
        raw = await self.client.get_json(
            EXPORT,
            {
                "where": f"rentree='{rentree}' and niveau_geo='COMMUNE'",
                "group_by": "geo_id,geo_nom,dep_id,uucr_id,regroupement",
                "select": "sum(effectif_atlas) as effectif",
            },
        )
        if not isinstance(raw, list):
            raise SourceError(self.info.id, f"rentrée {rentree} : réponse inattendue")
        return [parse_effectif(row) for row in raw]
