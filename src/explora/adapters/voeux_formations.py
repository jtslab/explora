"""Vœux et capacités des formations post-bac (open data de la plateforme Parcoursup)."""

from typing import Any

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.models import FormationVoeux, Point

DATASET = "/catalog/datasets/fr-esr-parcoursup/records"
CHAMPS = (
    "session,cod_uai,g_ea_lib_vx,ville_etab,dep,fili,lib_for_voe_ins,"
    "capa_fin,voe_tot,acc_tot,g_olocalisation_des_formations"
)
PAGE = 100


def parse_formation(row: dict[str, Any]) -> FormationVoeux:
    geo = row.get("g_olocalisation_des_formations")
    return FormationVoeux(
        session=str(row.get("session") or ""),
        code_uai=row.get("cod_uai") or "",
        etablissement=row.get("g_ea_lib_vx") or "",
        # Paris est publié par arrondissement, avec des espaces doublés.
        ville=" ".join((row.get("ville_etab") or "").split()),
        code_departement=row.get("dep") or "",
        filiere=row.get("fili") or "",
        formation=row.get("lib_for_voe_ins") or "",
        capacite=row.get("capa_fin"),
        voeux=row.get("voe_tot"),
        admis=row.get("acc_tot"),
        point=Point(lon=geo["lon"], lat=geo["lat"]) if geo else None,
    )


class VoeuxFormationsAdapter(SourceAdapter):
    info = SourceInfo(
        id="voeux-formations",
        name="Vœux de poursuite d'études et réponses des établissements",
        producer="Ministère de l'Enseignement supérieur (plateforme Parcoursup)",
        licence="Licence Ouverte 2.0",
        url="https://data.education.gouv.fr/explore/dataset/fr-esr-parcoursup/",
        attribution="MESR, open data Parcoursup",
        caveats=(
            "Une session par jeu (2025). Pas de code INSEE : rattachement à la commune "
            "par les coordonnées. Hors formations absentes de la plateforme."
        ),
    )

    async def formations(self, code_departement: str) -> list[FormationVoeux]:
        """Formations d'un département (≤ 1 500 par département, sous la limite de 10 000)."""
        formations: list[FormationVoeux] = []
        offset = 0
        while True:
            raw = await self.client.get_json(
                DATASET,
                {
                    "select": CHAMPS,
                    "where": f'dep="{code_departement}"',
                    "order_by": "cod_aff_form",
                    "limit": PAGE,
                    "offset": offset,
                },
            )
            formations += [parse_formation(row) for row in raw.get("results", [])]
            offset += PAGE
            if offset >= raw.get("total_count", 0):
                return formations
