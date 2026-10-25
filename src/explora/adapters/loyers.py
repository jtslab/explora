"""« Carte des loyers » : indicateurs de loyers d'annonce par commune (ANIL / ministère)."""

import csv
import io

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.models import LoyerCommune


def _num(value: str | None) -> float | None:
    if value is None or value.strip() in {"", "NA"}:
        return None
    return float(value.replace(",", ".").replace(" ", ""))


def _int(value: str | None) -> int | None:
    number = _num(value)
    return None if number is None else int(number)


def parse_csv(text: str, typologie: str) -> list[LoyerCommune]:
    """Lit un fichier de la carte des loyers (séparateur `;`, décimales à virgule)."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter=";")
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
    return loyers


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
            "non meublé. Prudence si R² < 0,5 ou moins de 30 observations."
        ),
    )

    async def loyers(self, resource_path: str, typologie: str) -> list[LoyerCommune]:
        """`resource_path` : chemin d'une ressource CSV data.gouv.fr (`/api/1/datasets/r/<id>`)."""
        text = await self.client.get_text(resource_path)
        return parse_csv(text, typologie)
