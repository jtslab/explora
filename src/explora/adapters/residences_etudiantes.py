"""Résidences universitaires publiques (flux XML régionaux publiés sur data.gouv.fr)."""

import html
import re
import xml.etree.ElementTree as ET

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.models import Point, ResidenceEtudiante

# Identifiants des 26 flux régionaux (chemin `/feed/{id}/{id}-logement.xml`).
FLUX = (
    "aix.marseille", "amiens", "antilles.guyane", "bfc", "bordeaux", "clermont.ferrand",
    "corte", "creteil", "grenoble", "lille", "limoges", "lyon", "montpellier", "nancy.metz",
    "nantes", "nice", "normandie", "orleans.tours", "paris", "poitiers", "reims", "rennes",
    "reunion", "strasbourg", "toulouse", "versailles",
)  # fmt: skip

# « 171 logements », « 1074 lits », « 798 chambres de 9 m² », « 78 T1 bis »...
_CAPACITE = re.compile(
    r"(?<![\d,./])(\d{1,4})\s+(?:[\w'\u2019-]+\s+)?"
    r"(?:logements?|chambres?|lits|studios|places|appartements|T[1-6](?:\s?bis)?)\b",
    re.IGNORECASE,
)
_BALISES = re.compile(r"<[^>]+>")
CAPACITE_MIN = 5


def extraire_places(*textes: str) -> int | None:
    """Premier effectif plausible trouvé dans les textes, dans l'ordre donné.

    Quand la description détaille plusieurs types (« 83 T2 et 6 studios »), seul le premier
    est retenu : la valeur est alors un minorant.
    """
    for texte in textes:
        for match in _CAPACITE.finditer(texte):
            places = int(match.group(1))
            if places >= CAPACITE_MIN:
                return places
    return None


def _texte(html_echappe: str | None) -> str:
    return " ".join(_BALISES.sub(" ", html.unescape(html_echappe or "")).split())


def parse_flux(xml: str) -> list[ResidenceEtudiante]:
    residences = []
    for node in ET.fromstring(xml.encode()).iter("residence"):
        lat, lon = node.get("lat"), node.get("lon")
        description = node.get("short_desc") or ""
        residences.append(
            ResidenceEtudiante(
                id=node.get("id", ""),
                nom=" ".join(node.get("title", "").split()),
                zone=node.get("zone") or None,
                adresse=(node.findtext("address") or "").strip() or None,
                point=Point(lon=float(lon), lat=float(lat)) if lat and lon else None,
                places_estimees=extraire_places(description, _texte(node.findtext("infos"))),
            )
        )
    return residences


class ResidencesEtudiantesAdapter(SourceAdapter):
    info = SourceInfo(
        id="residences-etudiantes",
        name="Logements étudiants (résidences universitaires)",
        producer="CNOUS",
        licence="Licence Ouverte 2.0",
        url="https://www.data.gouv.fr/datasets/logements-etudiants/",
        attribution="CNOUS, data.gouv.fr",
        caveats=(
            "Pas de champ « nombre de places » : estimation extraite des descriptions, "
            "disponible pour environ 60 % des résidences et très inégale selon les régions."
        ),
    )

    async def residences(self, flux: str) -> list[ResidenceEtudiante]:
        """`flux` : un identifiant de `FLUX`. Le serveur ne répond qu'en HTTP sur le port 80."""
        xml = await self.client.get_text(f"/feed/{flux}/{flux}-logement.xml")
        return parse_flux(xml)
