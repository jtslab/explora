"""Index des formations post-bac des villes du site, pour la recherche par filière.

    uv run python -m explora.site.formations --sortie web/data/formations.json

La source publie la commune et le département en libellés : on rattache chaque
formation aux villes de `data/villes_etudiantes.csv` par (commune, département).
"""

import argparse
import asyncio
import csv
import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from explora.adapters import OffreFormationsAdapter
from explora.core.config import get_settings
from explora.core.http import RetryPolicy, SourceClient
from explora.core.models import OffreFormation

SESSION = "2026"
URL_FICHE = (
    "https://dossierappel.parcoursup.fr/Candidats/public/fiches/afficherFicheFormation"
    "?g_ta_cod={code}&typeBac=0&originePc=0"
)


class Mention(BaseModel):
    libelle: str
    """Mention ou spécialité, ex. « BTS - Tourisme »."""
    type: int
    """Indice dans `IndexFormations.types`."""


class Etablissement(BaseModel):
    nom: str
    secteur: str | None = None


class Offre(BaseModel):
    mention: int
    """Indice dans `IndexFormations.mentions`."""
    uai: str
    code: str
    apprentissage: bool = False


class IndexFormations(BaseModel):
    genere_le: datetime
    session: str
    types: list[str] = Field(default_factory=list)
    mentions: list[Mention] = Field(default_factory=list)
    etablissements: dict[str, Etablissement] = Field(default_factory=dict)
    offres: dict[str, list[Offre]] = Field(default_factory=dict)
    """Formations par code INSEE de ville."""

    def villes_par_mention(self) -> list[list[str]]:
        villes: list[set[str]] = [set() for _ in self.mentions]
        for code, offres in self.offres.items():
            for o in offres:
                villes[o.mention].add(code)
        return [sorted(v) for v in villes]


def normaliser(texte: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", texte.replace("œ", "oe").replace("Œ", "Oe"))
    return re.sub(r"[^a-z0-9]+", " ", ascii_.encode("ascii", "ignore").decode().lower()).strip()


def _nom_etablissement(nom: str) -> str:
    """« Université de Rennes 2 (35) » → « Université de Rennes 2 »."""
    return re.sub(r"\s*\(\d[\dAB]{1,2}\)\s*$", "", nom).strip()


def construire(
    offres: Iterable[OffreFormation],
    villes: Iterable[Mapping[str, str]],
    session: str = SESSION,
) -> IndexFormations:
    codes = {(normaliser(v["nom"]), normaliser(v["departement"])): v["code_insee"] for v in villes}
    types: dict[str, int] = {}
    mentions: dict[str, Mention] = {}
    etablissements: dict[str, Etablissement] = {}
    par_ville: dict[str, list[tuple[str, str, str, bool]]] = {}
    for o in offres:
        code = codes.get((normaliser(o.commune), normaliser(o.departement)))
        if code is None or not o.mentions:
            continue
        type_ = o.types[0] if o.types else "Autres formations"
        types.setdefault(type_, len(types))
        etablissements.setdefault(
            o.code_uai, Etablissement(nom=_nom_etablissement(o.etablissement), secteur=o.secteur)
        )
        for libelle in o.mentions:
            mentions.setdefault(libelle, Mention(libelle=libelle, type=types[type_]))
            par_ville.setdefault(code, []).append((libelle, o.code_uai, o.code, o.apprentissage))

    # Indices stables d'une génération à l'autre : types et mentions triés.
    ordre_types = sorted(types, key=normaliser)
    rang_type = {t: i for i, t in enumerate(ordre_types)}
    ancien_type = {i: t for t, i in types.items()}
    ordre_mentions = sorted(mentions, key=normaliser)
    rang_mention = {m: i for i, m in enumerate(ordre_mentions)}
    return IndexFormations(
        genere_le=datetime.now(UTC).replace(microsecond=0),
        session=session,
        types=ordre_types,
        mentions=[
            Mention(libelle=m, type=rang_type[ancien_type[mentions[m].type]])
            for m in ordre_mentions
        ],
        etablissements=dict(sorted(etablissements.items())),
        offres={
            code: [
                Offre(mention=rang_mention[m], uai=uai, code=c, apprentissage=app)
                for m, uai, c, app in sorted(set(lignes))
            ]
            for code, lignes in sorted(par_ville.items())
        },
    )


def charger(chemin: Path) -> IndexFormations:
    return IndexFormations.model_validate_json(chemin.read_text(encoding="utf-8"))


async def _offres(session: str) -> list[OffreFormation]:
    async with SourceClient(
        "offre-formations",
        "https://data.education.gouv.fr/api/explore/v2.1",
        retry=RetryPolicy(max_attempts=10),
        timeout_s=180,
        user_agent=get_settings().http_user_agent,
    ) as client:
        return await OffreFormationsAdapter(client).offres(session)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--villes", type=Path, default=Path("data/villes_etudiantes.csv"))
    parser.add_argument("--session", default=SESSION)
    parser.add_argument("--sortie", type=Path, default=Path("web/data/formations.json"))
    args = parser.parse_args()
    with args.villes.open(encoding="utf-8") as f:
        villes = list(csv.DictReader(f))
    index = construire(asyncio.run(_offres(args.session)), villes, args.session)
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(index.model_dump_json(exclude_defaults=True), encoding="utf-8")
    total = sum(len(o) for o in index.offres.values())
    print(f"{total} formations dans {len(index.offres)} villes, {len(index.mentions)} mentions")


if __name__ == "__main__":
    main()
