"""Jeu de données de démonstration pour la maquette du site.

Part de la vraie liste des villes (`data/villes_etudiantes.csv`) et de leurs vrais
centres (API Découpage administratif). Les effectifs et les formations sont réels ;
les autres indicateurs sont tirés au hasard (graine = code INSEE) dans des
fourchettes plausibles et listés dans `indicateurs_demo` pour être signalés à
l'affichage. Les notes par axe sortent du vrai `scoring.scorer`.

    uv run python -m explora.site.demo --sortie web/data/villes.demo.geojson
"""

import argparse
import asyncio
import csv
import math
import random
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from explora.adapters import GeoApiAdapter
from explora.core.config import get_settings
from explora.core.http import RetryPolicy, SourceClient
from explora.modules.etudiant.indicators import rendement_locatif_brut
from explora.modules.etudiant.scoring import Axe, scorer
from explora.site.donnees import (
    Axes,
    Details,
    ExportVilles,
    FeatureVille,
    Indicateurs,
    Metadonnees,
    PointGeo,
    ProprietesVille,
    SourceExport,
    ecrire,
)

# Petite couronne : loyers et prix sans commune mesure avec le reste du pays.
PARIS_ET_PETITE_COURONNE = frozenset({"75", "92", "93", "94"})
RISQUES = (
    "Inondation",
    "Mouvement de terrain",
    "Séisme",
    "Retrait-gonflement des argiles",
    "Radon",
    "Feu de forêt",
    "Risque industriel",
    "Transport de marchandises dangereuses",
)
INDICATEURS_REELS = frozenset({"effectifs_etudiants", "nb_etablissements", "nb_filieres"})


def _ville_demo(ligne: Mapping[str, str]) -> tuple[Indicateurs, list[str]]:
    rng = random.Random(ligne["code_insee"])
    population = int(ligne["population"] or 0)
    effectif = int(ligne["effectif_etudiants"] or 0)
    formations = [f for f in ligne["formations"].split(";") if f]
    taille = math.log10(max(population, 1000))  # 3 (bourg) à ~6.3 (Paris)
    dep = ligne["code_departement"]

    if dep in PARIS_ET_PETITE_COURONNE:
        loyer = rng.uniform(22, 32)
        prix = rng.uniform(5500, 10500)
    else:
        loyer = rng.uniform(8.5, 11) + (taille - 3) * rng.uniform(1.2, 2.2)
        prix = rng.uniform(1100, 1900) + (taille - 3) * rng.uniform(450, 1100)
    risques = rng.sample(RISQUES, rng.randint(1, 5))
    indicateurs = Indicateurs(
        effectifs_etudiants=effectif,
        nb_etablissements=max(1, round(len(formations) * rng.uniform(1, 1 + effectif / 4000))),
        nb_filieres=len(formations),
        loyer_m2=round(loyer, 1),
        prix_m2=round(prix, -1),
        rendement_brut=round(rendement_locatif_brut(round(loyer, 1), round(prix, -1)) or 0, 4),
        tension_locative=round(rng.uniform(3, 12) + effectif / 6000, 1),
        commerces_pour_1000=round(rng.uniform(6, 14) + (taille - 3) * 2.5, 1),
        equipements_culture_sport_pour_1000=round(rng.uniform(2, 9), 1),
        vitalite_commerciale=round(rng.uniform(-0.02, 0.05) * population / 10),
        arrets_transport_pour_1000=round(rng.uniform(0.5, 3) + (taille - 3) * 1.1, 1),
        stations_velo=round(max(0.0, rng.uniform(-20, 15) + (taille - 3.5) * 60)),
        indice_qualite_air=round(rng.uniform(1.6, 2.4) + (taille - 3) * 0.3, 1),
        nb_risques=len(risques),
    )
    return indicateurs, risques


def construire(
    lignes: list[dict[str, str]], centres: Mapping[str, tuple[float, float]]
) -> ExportVilles:
    tirages = {ligne["code_insee"]: _ville_demo(ligne) for ligne in lignes}
    scores = scorer({code: ind.model_dump() for code, (ind, _) in tirages.items()})
    demo = sorted(set(Indicateurs.model_fields) - INDICATEURS_REELS)
    features = []
    for ligne in lignes:
        code = ligne["code_insee"]
        indicateurs, risques = tirages[code]
        score = scores[code]
        features.append(
            FeatureVille(
                geometry=PointGeo(coordinates=centres[code]),
                properties=ProprietesVille(
                    code_insee=code,
                    nom=ligne["nom"],
                    code_departement=ligne["code_departement"],
                    departement=ligne["departement"],
                    population=int(ligne["population"] or 0) or None,
                    effectif_etudiants=int(ligne["effectif_etudiants"] or 0) or None,
                    formations=[f for f in ligne["formations"].split(";") if f],
                    axes=Axes(**{axe.value: _arrondi(score.axes[axe]) for axe in Axe}),
                    score=_arrondi(score.global_),
                    couverture=score.couverture,
                    indicateurs=indicateurs,
                    risques=risques,
                    details=Details(
                        tension_methode="places_residences",
                        loyer_fiable=True,
                        prix_m2_typologie="appartements",
                        prix_m2_annee=2025,
                    ),
                    indicateurs_demo=demo,
                ),
            )
        )
    return ExportVilles(
        metadata=Metadonnees(
            genere_le=datetime.now(UTC).replace(microsecond=0),
            demo=True,
            sources=[
                SourceExport(
                    id="effectifs",
                    attribution="Atlas régional des effectifs étudiants, MESR",
                    licence="Licence Ouverte 2.0",
                ),
                SourceExport(
                    id="geo-api",
                    attribution="API Découpage administratif, DINUM",
                    licence="Licence Ouverte 2.0",
                ),
            ],
        ),
        features=features,
    )


def _arrondi(valeur: float | None) -> float | None:
    return None if valeur is None else round(valeur, 1)


async def _centres(codes: set[str]) -> dict[str, tuple[float, float]]:
    async with SourceClient(
        "geo-api",
        "https://geo.api.gouv.fr",
        retry=RetryPolicy(max_attempts=10),
        timeout_s=120,
        user_agent=get_settings().http_user_agent,
    ) as client:
        communes = await GeoApiAdapter(client).communes()
    return {
        c.code_insee: (c.centre.lon, c.centre.lat)
        for c in communes
        if c.centre and c.code_insee in codes
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--villes", type=Path, default=Path("data/villes_etudiantes.csv"))
    parser.add_argument("--sortie", type=Path, default=Path("web/data/villes.demo.geojson"))
    args = parser.parse_args()
    with args.villes.open(encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    centres = asyncio.run(_centres({ligne["code_insee"] for ligne in lignes}))
    ecrire(construire(lignes, centres), args.sortie)


if __name__ == "__main__":
    main()
