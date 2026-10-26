"""Devenir des diplômés de chaque formation : poursuite d'études, emploi, salaire.

Deux sources officielles, rattachées aux formations de `web/data/formations.json` :

- InserSup (MESR) pour les diplômes du supérieur (licence, BUT, écoles d'ingénieurs et
  de commerce) : emploi salarié 12 mois après la sortie et salaire net médian, par
  établissement et au niveau national ;
- InserJeunes (DEPP) pour les BTS des lycées et des CFA : emploi 12 mois après la sortie,
  sans salaire.

Les taux d'emploi portent sur les diplômés qui ont arrêté leurs études (« sortants »).

    uv run python -m explora.site.insertion --sortie web/data/insertion.json
"""

import argparse
import asyncio
import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from explora.core.config import get_settings
from explora.core.http import RetryPolicy, SourceClient
from explora.site import formations as fm
from explora.site import metiers as mt

INSERSUP = "/catalog/datasets/fr-esr-insersup/exports/json"
INSERSUP_CHAMPS = (
    "etablissement,type_diplome_long,libelle_diplome,diplome,promo,"
    "nb_sortants_12,nb_poursuivants_12,tx_sortants_en_emploi_sal_fr_12,salaire_q2_12"
)
INSERJEUNES = {
    "lycee": "/catalog/datasets/fr-en-inserjeunes-lycee_pro-formation-fine/exports/json",
    "cfa": "/catalog/datasets/fr-en-inserjeunes-cfa-formation_fine/exports/json",
}
INSERJEUNES_CHAMPS = "annee,uai,libelle_formation,taux_poursuite_etudes,taux_emploi_12_mois"
NATIONAL = "all"

# Type de formation (index des formations) → types de diplôme InserSup.
LICENCE = ("Licence générale",)
BUT = ("Bachelor universitaire de technologie",)
INGENIEUR = ("Diplôme d'ingénieurs",)
COMMERCE = {
    "Bac + 3": (
        "Diplôme visé niveau bac + 3",
        "Diplôme visé niveau bac + 3 ou bac + 4 grade licence",
    ),
    "Bac + 4": ("Diplôme visé niveau bac + 4",),
    "Bac + 5": ("Diplôme visé niveau bac + 5 grade master", "Diplôme visé niveau bac + 5"),
}


class Insertion(BaseModel):
    emploi: int | None = None
    """Part des sortants en emploi 12 mois après le diplôme, en %."""
    salaire: int | None = None
    """Salaire net mensuel médian des sortants en emploi, 12 mois après, en euros."""
    poursuite: int | None = None
    """Part des diplômés qui poursuivent leurs études, en %."""
    promo: str = ""
    source: str
    """« insersup » ou « inserjeunes »."""
    national: bool = False
    """Chiffre national du diplôme, faute de chiffre pour l'établissement."""


class IndexInsertion(BaseModel):
    genere_le: datetime
    offres: dict[str, Insertion] = Field(default_factory=dict)
    """Par code de formation (celui de l'index des formations)."""


def _nombre(valeur: Any) -> float | None:
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None  # « nd » : secret statistique ou effectif trop faible


def _reste(mention: str) -> str:
    """« BTS - Tourisme » → « Tourisme »."""
    return mention.split(" - ", 1)[1] if " - " in mention else mention


def meme_intitule(a: str, b: str) -> bool:
    """« Fluide, énergie, domotique - option A … » et « fluides-energies-domotique option a … »."""
    for variante in mt._variantes(a):
        x, y = mt._mots(variante), mt._mots(b)
        if not x or not y:
            continue
        communs = len(x & y)
        if communs / len(x | y) >= 0.75 or (communs == min(len(x), len(y)) and communs >= 2):
            return True
    return False


def ligne_insersup(row: Mapping[str, Any]) -> Insertion | None:
    emploi = _nombre(row.get("tx_sortants_en_emploi_sal_fr_12"))
    if emploi is None:
        return None
    sortants = _nombre(row.get("nb_sortants_12")) or 0
    poursuivants = _nombre(row.get("nb_poursuivants_12"))
    salaire = _nombre(row.get("salaire_q2_12"))
    promo = row.get("promo") or []
    return Insertion(
        emploi=round(emploi),
        salaire=round(salaire) if salaire else None,
        poursuite=round(100 * poursuivants / (poursuivants + sortants))
        if poursuivants is not None and poursuivants + sortants
        else None,
        promo="-".join(promo) if isinstance(promo, list) else str(promo),
        source="insersup",
        national=row.get("etablissement") == NATIONAL,
    )


def ligne_inserjeunes(row: Mapping[str, Any]) -> Insertion | None:
    emploi = _nombre(row.get("taux_emploi_12_mois"))
    if emploi is None:
        return None
    poursuite = _nombre(row.get("taux_poursuite_etudes"))
    return Insertion(
        emploi=round(emploi),
        poursuite=round(poursuite) if poursuite is not None else None,
        promo=str(row.get("annee") or "").removeprefix("cumul "),
        source="inserjeunes",
    )


def _rang(ins: Insertion) -> tuple[bool, str]:
    return (ins.salaire is not None, ins.promo)


def _plus_recentes(
    lignes: Iterable[tuple[str, str, str, Insertion]],
) -> dict[str, list[tuple[str, str, Insertion]]]:
    """Par établissement : (type, intitulé, chiffres) de la promotion la plus récente.

    Une promotion avec salaire connu passe devant une plus récente sans salaire.
    """
    meilleures: dict[tuple[str, str, str], Insertion] = {}
    for uai, type_, intitule, ins in lignes:
        cle = (uai, type_, intitule)
        if cle not in meilleures or _rang(ins) > _rang(meilleures[cle]):
            meilleures[cle] = ins
    par_uai: dict[str, list[tuple[str, str, Insertion]]] = defaultdict(list)
    for (uai, type_, intitule), ins in meilleures.items():
        par_uai[uai].append((type_, intitule, ins))
    return par_uai


def construire(
    index: fm.IndexFormations,
    insersup: Iterable[Mapping[str, Any]],
    inserjeunes: Iterable[Mapping[str, Any]],
) -> IndexInsertion:
    sup = _plus_recentes(
        (
            str(r.get("etablissement")),
            str(r.get("type_diplome_long")),
            str(r.get("libelle_diplome")),
            ins,
        )
        for r in insersup
        if (ins := ligne_insersup(r))
    )
    jeunes = _plus_recentes(
        (str(r.get("uai")), "BTS", str(r.get("libelle_formation")), ins)
        for r in inserjeunes
        if (ins := ligne_inserjeunes(r))
    )

    def par_intitule(
        lignes: list[tuple[str, str, Insertion]], types: tuple[str, ...], mention: str
    ) -> Insertion | None:
        return next(
            (
                ins
                for t, intitule, ins in lignes
                if t in types and meme_intitule(_reste(mention), intitule)
            ),
            None,
        )

    def ecole(uai: str, types: tuple[str, ...]) -> Insertion | None:
        # Une école délivre parfois plusieurs diplômes : on garde celui qui a le plus d'emploi
        # renseigné, à défaut de connaître le parcours exact.
        candidats = [ins for t, _, ins in sup.get(uai, []) if t in types]
        return max(candidats, key=_rang, default=None)

    offres: dict[str, Insertion] = {}
    for liste in index.offres.values():
        for o in liste:
            mention = index.mentions[o.mention]
            type_ = index.types[mention.type]
            libelle = mention.libelle
            trouve: Insertion | None = None
            if type_.startswith("BTS"):
                trouve = par_intitule(jeunes.get(o.uai, []), ("BTS",), libelle)
            elif type_ in ("Licence", "BUT"):
                types = LICENCE if type_ == "Licence" else BUT
                trouve = par_intitule(sup.get(o.uai, []), types, libelle) or par_intitule(
                    sup.get(NATIONAL, []), types, libelle
                )
            elif libelle == "Formation d'ingénieur Bac + 5":
                trouve = ecole(o.uai, INGENIEUR)
            elif "commerce" in type_:
                niveau = next((n for n in COMMERCE if libelle.endswith(n)), None)
                trouve = ecole(o.uai, COMMERCE[niveau]) if niveau else None
            if trouve:
                offres[o.code] = trouve
    return IndexInsertion(
        genere_le=datetime.now(UTC).replace(microsecond=0), offres=dict(sorted(offres.items()))
    )


def charger(chemin: Path) -> IndexInsertion:
    return IndexInsertion.model_validate_json(chemin.read_text(encoding="utf-8"))


def _client(source: str, base_url: str) -> SourceClient:
    # Les deux portails coupent souvent la connexion : beaucoup de tentatives.
    return SourceClient(
        source,
        base_url,
        retry=RetryPolicy(max_attempts=25),
        timeout_s=300,
        user_agent=get_settings().http_user_agent,
    )


async def _telecharger() -> tuple[list[Any], list[Any]]:
    async with _client(
        "insersup", "https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1"
    ) as client:
        sup = await client.get_json(
            INSERSUP,
            {
                "where": "genre='ensemble' and obtention_diplome='ensemble' "
                "and nationalite='ensemble' and regime_inscription='ensemble'",
                "select": INSERSUP_CHAMPS,
            },
        )
    jeunes: list[Any] = []
    async with _client("inserjeunes", "https://data.education.gouv.fr/api/explore/v2.1") as client:
        for chemin in INSERJEUNES.values():
            jeunes += await client.get_json(
                chemin, {"where": "type_diplome='BTS'", "select": INSERJEUNES_CHAMPS}
            )
    return sup, jeunes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--formations", type=Path, default=Path("web/data/formations.json"))
    parser.add_argument("--sortie", type=Path, default=Path("web/data/insertion.json"))
    parser.add_argument(
        "--depuis",
        type=Path,
        help="dossier avec insersup.json et inserjeunes-*.json déjà téléchargés",
    )
    args = parser.parse_args()
    if args.depuis:
        sup = json.loads((args.depuis / "insersup.json").read_text(encoding="utf-8"))
        jeunes = [
            r
            for f in sorted(args.depuis.glob("inserjeunes-*.json"))
            for r in json.loads(f.read_text(encoding="utf-8"))
        ]
    else:
        sup, jeunes = asyncio.run(_telecharger())
    index = fm.charger(args.formations)
    resultat = construire(index, sup, jeunes)
    args.sortie.write_text(resultat.model_dump_json(exclude_defaults=True), encoding="utf-8")
    total = sum(len(o) for o in index.offres.values())
    print(f"{len(resultat.offres)}/{total} formations avec des chiffres d'insertion")


if __name__ == "__main__":
    main()
