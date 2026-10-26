"""Indicateurs de prix DV3F (Cerema, API Données foncières), agrégés par commune."""

from typing import Any

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.errors import SourceError
from explora.core.models import PrixImmobilierCommune

PRIX_ANNUELS = "/indicateurs/dv3f/prix/annuel/"
# Codes de typologie DV3F : 121 appartement, 121x1 appartement d'une pièce.
TYPOLOGIES = (("t1", "121x1"), ("appartements", "121"))


def parse_prix(code_insee: str, raw: dict[str, Any]) -> PrixImmobilierCommune | None:
    """Dernière année publiée, studios de préférence.

    Le Cerema masque la médiane quand il y a trop peu de ventes (secret statistique) :
    on se rabat alors sur l'ensemble des appartements, sinon `None`.
    """
    annees = sorted(raw.get("results", []), key=lambda r: str(r.get("annee")))
    if not annees:
        return None
    derniere = annees[-1]
    for typologie, code in TYPOLOGIES:
        prix = derniere.get(f"pxm2_median_cod{code}")
        if prix is not None:
            return PrixImmobilierCommune(
                code_insee=code_insee,
                annee=str(derniere["annee"]),
                typologie=typologie,
                prix_m2=float(prix),
                nb_transactions=int(derniere.get(f"nbtrans_cod{code}") or 0),
            )
    return None


class Dv3fAdapter(SourceAdapter):
    info = SourceInfo(
        id="dv3f",
        name="Indicateurs de prix DV3F (API Données foncières)",
        producer="Cerema, à partir des DVF de la DGFiP",
        licence="Licence Ouverte 2.0",
        url="https://apidf-preprod.cerema.fr/",
        attribution="Cerema, DV3F d'après DVF (DGFiP)",
        caveats=(
            "Médiane des ventes de l'année, studios ou à défaut tous appartements ; masquée par "
            "le Cerema quand les ventes sont trop peu nombreuses. Domaine de préproduction."
        ),
    )

    async def prix(self, code_insee: str) -> PrixImmobilierCommune | None:
        raw = await self.client.get_json(PRIX_ANNUELS, {"code": code_insee, "echelle": "communes"})
        if not isinstance(raw, dict):
            raise SourceError(self.info.id, f"commune {code_insee} : réponse inattendue")
        return parse_prix(code_insee, raw)
