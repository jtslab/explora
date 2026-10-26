"""Offre de formations post-bac par commune (cartographie des formations, MESR)."""

from typing import Any

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.errors import SourceError
from explora.core.models import OffreFormation, Point

DATASET = "/catalog/datasets/fr-esr-cartographie_formations_parcoursup"
CHAMPS = "annee,gta,etab_uai,etab_nom,tc,tf,nm,fl,app,departement,commune,etab_gps"


def parse_offre(row: dict[str, Any]) -> OffreFormation:
    geo = row.get("etab_gps")
    noms = row.get("nm") or []
    return OffreFormation(
        session=str(row.get("annee") or ""),
        code=str(row.get("gta") or ""),
        code_uai=row.get("etab_uai") or "",
        etablissement=row.get("etab_nom") or "",
        secteur=row.get("tc"),
        types=row.get("tf") or [],
        mentions=row.get("fl") or [],
        libelle=noms[0] if noms else "",
        # Le champ liste les modes d'apprentissage proposés ; vide = statut scolaire seul.
        apprentissage=bool(row.get("app")),
        commune=row.get("commune") or "",
        departement=row.get("departement") or "",
        point=Point(lon=geo["lon"], lat=geo["lat"]) if geo else None,
    )


class OffreFormationsAdapter(SourceAdapter):
    info = SourceInfo(
        id="offre-formations",
        name="Cartographie des formations post-bac",
        producer="Ministère de l'Enseignement supérieur",
        licence="Licence Ouverte 2.0",
        url=(
            "https://data.education.gouv.fr/explore/dataset/"
            "fr-esr-cartographie_formations_parcoursup/"
        ),
        attribution="MESR, cartographie des formations post-bac",
        caveats=(
            "Formations accessibles en première année via la plateforme nationale "
            "d'admission : certaines écoles et formations hors plateforme manquent. "
            "Commune et département en libellés, sans code INSEE."
        ),
    )

    async def offres(self, session: str) -> list[OffreFormation]:
        """Toutes les formations d'une session (~26 000 lignes, un seul export)."""
        raw = await self.client.get_json(
            f"{DATASET}/exports/json", {"where": f'annee="{session}"', "select": CHAMPS}
        )
        if not isinstance(raw, list):
            raise SourceError(self.info.id, f"session {session} : réponse inattendue")
        return [parse_offre(row) for row in raw]
