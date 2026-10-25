"""« Carte des loyers » : indicateurs de loyers d'annonce par commune (ANIL / ministère)."""

import csv
import io

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.models import LoyerCommune

# Paris, Lyon et Marseille ne sont publiés qu'à l'arrondissement (75101...75120, etc.).
ARRONDISSEMENTS_PLM = {
    "75056": ("Paris", "751"),
    "69123": ("Lyon", "6938"),
    "13055": ("Marseille", "132"),
}


def _num(value: str | None) -> float | None:
    if value is None or value.strip() in {"", "NA"}:
        return None
    return float(value.replace(",", ".").replace(" ", ""))


def _int(value: str | None) -> int | None:
    number = _num(value)
    return None if number is None else int(number)


def _moyenne_ponderee(valeurs: list[tuple[float | None, int]]) -> float | None:
    utiles = [(v, p) for v, p in valeurs if v is not None and p > 0]
    total = sum(p for _, p in utiles)
    if not total:
        return None
    return sum(v * p for v, p in utiles) / total


def agreger_arrondissements(loyers: list[LoyerCommune]) -> list[LoyerCommune]:
    """Loyer communal de Paris, Lyon et Marseille, à partir de leurs arrondissements.

    Moyenne pondérée par le nombre d'annonces de chaque arrondissement ; les bornes
    d'intervalle et le R² sont pondérés de la même façon (approximation indicative).
    """
    agreges = []
    for code, (nom, prefixe) in ARRONDISSEMENTS_PLM.items():
        arrs = [
            loyer
            for loyer in loyers
            if loyer.code_insee.startswith(prefixe) and loyer.code_insee != code
        ]
        if not arrs:
            continue
        poids = [loyer.nb_observations or 0 for loyer in arrs]
        loyer_m2 = _moyenne_ponderee([(a.loyer_m2, p) for a, p in zip(arrs, poids, strict=True)])
        if loyer_m2 is None:
            continue
        agreges.append(
            LoyerCommune(
                code_insee=code,
                nom=nom,
                typologie=arrs[0].typologie,
                loyer_m2=loyer_m2,
                intervalle_bas_m2=_moyenne_ponderee(
                    [(a.intervalle_bas_m2, p) for a, p in zip(arrs, poids, strict=True)]
                ),
                intervalle_haut_m2=_moyenne_ponderee(
                    [(a.intervalle_haut_m2, p) for a, p in zip(arrs, poids, strict=True)]
                ),
                niveau_prediction="arrondissements",
                nb_observations=sum(poids),
                r2_ajuste=_moyenne_ponderee(
                    [(a.r2_ajuste, p) for a, p in zip(arrs, poids, strict=True)]
                ),
            )
        )
    return agreges


def parse_csv(text: str, typologie: str) -> list[LoyerCommune]:
    """Lit un fichier de la carte des loyers (séparateur `;`, décimales à virgule).

    Ajoute en fin de liste les lignes communales agrégées de Paris, Lyon et Marseille.
    """
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=";")
    loyers = []
    for row in reader:
        loyer = _num(row.get("loypredm2"))
        if loyer is None:
            continue
        loyers.append(
            LoyerCommune(
                code_insee=row["INSEE_C"].strip().zfill(5),
                nom=row.get("LIBGEO", "").strip(),
                typologie=typologie,
                loyer_m2=loyer,
                intervalle_bas_m2=_num(row.get("lwr.IPm2")),
                intervalle_haut_m2=_num(row.get("upr.IPm2")),
                niveau_prediction=(row.get("TYPPRED") or None),
                nb_observations=_int(row.get("nbobs_com")),
                r2_ajuste=_num(row.get("R2_adj")),
            )
        )
    return loyers + agreger_arrondissements(loyers)


class LoyersAdapter(SourceAdapter):
    info = SourceInfo(
        id="carte-loyers",
        name="Carte des loyers : indicateurs de loyers d'annonce par commune",
        producer="ANIL / Ministère du Logement",
        licence="Licence Ouverte 2.0",
        url="https://www.data.gouv.fr/datasets/693aa2feed1bf4da603faa49/",
        attribution="Estimations ANIL, à partir des données du Groupe SeLoger et de leboncoin",
        caveats=(
            "Estimations expérimentales à la commune, pas au quartier ; charges comprises, "
            "non meublé. Prudence si R² < 0,5 ou moins de 30 observations. Paris, Lyon et "
            "Marseille : moyenne des arrondissements pondérée par le nombre d'annonces."
        ),
    )

    async def loyers(self, resource_path: str, typologie: str) -> list[LoyerCommune]:
        """`resource_path` : chemin d'une ressource CSV data.gouv.fr (`/api/1/datasets/r/<id>`)."""
        # Le millésime 2025 est encodé en Windows-1252 mais servi en `charset=utf-8`.
        text = await self.client.get_text(resource_path, fallback_encoding="cp1252")
        return parse_csv(text, typologie)
