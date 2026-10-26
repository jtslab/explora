"""Code officiel géographique (INSEE) : départements et leur chef-lieu."""

import csv
import io

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.models import Departement

# Fichier millésimé : le numéro de publication change chaque année.
DEPARTEMENTS_2025 = "/fr/statistiques/fichier/8377162/v_departement_2025.csv"


def parse_departements(text: str) -> list[Departement]:
    return [
        Departement(code=row["DEP"], nom=row["LIBELLE"], chef_lieu=row["CHEFLIEU"])
        for row in csv.DictReader(io.StringIO(text))
    ]


class CogAdapter(SourceAdapter):
    info = SourceInfo(
        id="cog",
        name="Code officiel géographique",
        producer="INSEE",
        licence="Licence Ouverte 2.0",
        url="https://www.insee.fr/fr/information/2560452",
        attribution="INSEE, Code officiel géographique",
        caveats="Les départements d'outre-mer y figurent, pas les collectivités d'outre-mer.",
    )

    async def departements(self, path: str = DEPARTEMENTS_2025) -> list[Departement]:
        return parse_departements(await self.client.get_text(path))
