"""CAP, bacs pro, brevets professionnels et mentions complémentaires des villes du site.

Ces diplômes se préparent après la 3e (ou après un CAP), en lycée professionnel ou en
apprentissage, hors de la plateforme d'admission post-bac. On les tire d'InserJeunes
(DEPP), qui recense chaque formation des lycées professionnels et des CFA avec le devenir
de ses sortants, et on situe chaque établissement par l'annuaire de l'Éducation nationale.

    uv run python -m explora.site.voie_pro --sortie web/data/voie_pro.json

Les CFA ne figurent pas tous dans l'annuaire : on les situe aussi par les formations post-bac
qu'ils proposent (`web/data/formations.json`), puis par la ville qui termine leur nom
(« … - Angers »). Les autres sont laissés de côté.
"""

import argparse
import asyncio
import csv
import json
import re
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from explora.site import formations as fm
from explora.site import insertion as ins

LYCEE = "/catalog/datasets/fr-en-inserjeunes-lycee_pro-formation-fine/exports/json"
CFA = "/catalog/datasets/fr-en-inserjeunes-cfa-formation_fine/exports/json"
ANNUAIRE = "/catalog/datasets/fr-en-annuaire-education/exports/json"
CHAMPS = (
    "annee,uai,libelle,type_diplome,libelle_formation,taux_emploi_12_mois,taux_poursuite_etudes"
)

# Type de diplôme InserJeunes → (type affiché, préfixe de la mention, point de départ).
DIPLOMES = {
    "CAP": ("CAP", "CAP", "Après la 3e"),
    "BAC PRO": ("Bac professionnel", "Bac pro", "Après la 3e"),
    "BP": ("Brevet professionnel", "BP", "Après un CAP"),
    "MC3": ("Mention complémentaire", "MC", "Après un CAP"),
    "MC4": ("Mention complémentaire", "MC", "Après un bac pro"),
}
TYPES = tuple(dict.fromkeys(t for t, _, _ in DIPLOMES.values()))
DEPARTS = {t: d for t, _, d in DIPLOMES.values()}
PREFIXE_CODE = "ij-"

# Arrondissements de Paris, Lyon et Marseille → commune.
ARRONDISSEMENTS = (("751", "75056"), ("6938", "69123"), ("132", "13055"))


class IndexVoiePro(BaseModel):
    genere_le: datetime
    annee: str
    """Cohorte InserJeunes, ex. « cumul 2023-2024 »."""
    formations: fm.IndexFormations
    insertion: dict[str, ins.Insertion] = Field(default_factory=dict)
    """Devenir des sortants, par code d'offre (`Offre.code`)."""


def _commune(code: str) -> str:
    for prefixe, commune in ARRONDISSEMENTS:
        if code.startswith(prefixe) and len(code) == 5:
            return commune
    return code


def mention(type_diplome: str, libelle: str) -> str:
    """(« CAP », « boulanger ») → « CAP - Boulanger »."""
    libelle = re.sub(r"\s+", " ", libelle).strip()
    return f"{DIPLOMES[type_diplome][1]} - {libelle[:1].upper()}{libelle[1:]}"


def _ville_du_nom(nom: str, villes: Mapping[str, str]) -> str | None:
    """Ville qui termine le nom d'un CFA (« CFA du BTP de Agen » → Agen), si une seule."""
    fin = fm.normaliser(nom)
    trouvees = {code for n, code in villes.items() if fin == n or fin.endswith(" " + n)}
    return trouvees.pop() if len(trouvees) == 1 else None


def construire(
    lycees: Iterable[Mapping[str, Any]],
    cfa: Iterable[Mapping[str, Any]],
    annuaire: Iterable[Mapping[str, Any]],
    villes: Iterable[Mapping[str, str]],
    formations: fm.IndexFormations | None = None,
) -> IndexVoiePro:
    villes = list(villes)
    codes = {v["code_insee"] for v in villes}
    # Les noms courts (« Vire », « Eu ») trouveraient des faux amis dans les noms de CFA.
    noms = {fm.normaliser(v["nom"]): v["code_insee"] for v in villes if len(v["nom"]) >= 4}
    situes = {a["identifiant_de_l_etablissement"]: a for a in annuaire}
    post_bac = (
        {o.uai: code for code, offres in formations.offres.items() for o in offres}
        if formations
        else {}
    )

    lignes = [(r, False) for r in lycees] + [(r, True) for r in cfa]
    annees = sorted({r["annee"] for r, _ in lignes if r.get("annee")})
    annee = annees[-1] if annees else ""
    types: list[str] = []
    mentions: dict[str, int] = {}
    types_: dict[str, str] = {}
    etablissements: dict[str, fm.Etablissement] = {}
    offres: dict[str, list[fm.Offre]] = {}
    insertion: dict[str, ins.Insertion] = {}
    for r, apprentissage in lignes:
        if r.get("annee") != annee or r.get("type_diplome") not in DIPLOMES:
            continue
        uai = r["uai"]
        etab = situes.get(uai)
        code = _commune(etab["code_commune"]) if etab and etab.get("code_commune") else None
        if code is None or code not in codes:
            code = post_bac.get(uai) or (
                _ville_du_nom(r.get("libelle") or "", noms) if apprentissage else None
            )
        if code is None or code not in codes:
            continue
        type_ = DIPLOMES[r["type_diplome"]][0]
        if type_ not in types:
            types.append(type_)
        libelle = mention(r["type_diplome"], r["libelle_formation"])
        indice = mentions.setdefault(libelle, len(mentions))
        types_[libelle] = type_
        etablissements.setdefault(
            uai,
            fm.Etablissement(
                nom=(etab or {}).get("nom_etablissement") or r.get("libelle") or uai,
                secteur="Publics" if (etab or {}).get("statut_public_prive") == "Public" else None,
            ),
        )
        cle = f"{PREFIXE_CODE}{uai}-{indice}{'-a' if apprentissage else ''}"
        offres.setdefault(code, []).append(
            fm.Offre(mention=indice, uai=uai, code=cle, apprentissage=apprentissage)
        )
        emploi = ins._nombre(r.get("taux_emploi_12_mois"))
        poursuite = ins._nombre(r.get("taux_poursuite_etudes"))
        if emploi is not None or poursuite is not None:
            insertion[cle] = ins.Insertion(
                emploi=round(emploi) if emploi is not None else None,
                poursuite=round(poursuite) if poursuite is not None else None,
                promo=annee.removeprefix("cumul "),
                source="inserjeunes",
            )

    # Indices stables : types dans l'ordre de DIPLOMES, mentions triées.
    ordre_types = [t for t in TYPES if t in types]
    ordre = sorted(mentions, key=fm.normaliser)
    rang = {mentions[m]: i for i, m in enumerate(ordre)}
    return IndexVoiePro(
        genere_le=datetime.now(UTC).replace(microsecond=0),
        annee=annee,
        formations=fm.IndexFormations(
            genere_le=datetime.now(UTC).replace(microsecond=0),
            session=annee,
            types=ordre_types,
            mentions=[fm.Mention(libelle=m, type=ordre_types.index(types_[m])) for m in ordre],
            etablissements=dict(sorted(etablissements.items())),
            offres={
                code: sorted(
                    {
                        o.code: o.model_copy(update={"mention": rang[o.mention]}) for o in liste
                    }.values(),
                    key=lambda o: (o.mention, o.uai, o.code),
                )
                for code, liste in sorted(offres.items())
            },
        ),
        insertion=dict(sorted(insertion.items())),
    )


def fusionner(index: fm.IndexFormations, voie_pro: fm.IndexFormations) -> fm.IndexFormations:
    """Ajoute les formations de la voie professionnelle à la suite de l'index post-bac.

    Les indices des types et des mentions post-bac ne changent pas.
    """
    types = list(index.types)
    rang_type = {}
    for i, t in enumerate(voie_pro.types):
        if t not in types:
            types.append(t)
        rang_type[i] = types.index(t)
    decalage = len(index.mentions)
    offres = {code: list(liste) for code, liste in index.offres.items()}
    for code, liste in voie_pro.offres.items():
        offres.setdefault(code, []).extend(
            o.model_copy(update={"mention": o.mention + decalage}) for o in liste
        )
    return index.model_copy(
        update={
            "types": types,
            "mentions": index.mentions
            + [m.model_copy(update={"type": rang_type[m.type]}) for m in voie_pro.mentions],
            "etablissements": {**voie_pro.etablissements, **index.etablissements},
            "offres": dict(sorted(offres.items())),
        }
    )


def charger(chemin: Path) -> IndexVoiePro:
    return IndexVoiePro.model_validate_json(chemin.read_text(encoding="utf-8"))


async def _telecharger() -> tuple[list[Any], list[Any], list[Any]]:
    filtre = "type_diplome in ({})".format(",".join(f"'{t}'" for t in DIPLOMES))
    async with ins._client("inserjeunes", "https://data.education.gouv.fr/api/explore/v2.1") as c:
        lycees = await c.get_json(LYCEE, {"where": filtre, "select": CHAMPS})
        cfa = await c.get_json(CFA, {"where": filtre, "select": CHAMPS})
        annuaire = await c.get_json(
            ANNUAIRE,
            {
                "where": "type_etablissement!='Ecole'",
                "select": "identifiant_de_l_etablissement,nom_etablissement,code_commune,"
                "statut_public_prive",
            },
        )
    return lycees, cfa, annuaire


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--villes", type=Path, default=Path("data/villes_etudiantes.csv"))
    parser.add_argument("--formations", type=Path, default=Path("web/data/formations.json"))
    parser.add_argument("--sortie", type=Path, default=Path("web/data/voie_pro.json"))
    parser.add_argument(
        "--depuis",
        type=Path,
        help="dossier avec inserjeunes-lycee.json, inserjeunes-cfa.json et annuaire.json",
    )
    args = parser.parse_args()
    if args.depuis:
        lycees, cfa, annuaire = (
            json.loads((args.depuis / f).read_text(encoding="utf-8"))
            for f in ("inserjeunes-lycee.json", "inserjeunes-cfa.json", "annuaire.json")
        )
    else:
        lycees, cfa, annuaire = asyncio.run(_telecharger())
    with args.villes.open(encoding="utf-8") as f:
        villes = list(csv.DictReader(f))
    formations = fm.charger(args.formations) if args.formations.exists() else None
    index = construire(lycees, cfa, annuaire, villes, formations)
    args.sortie.write_text(index.model_dump_json(exclude_defaults=True), encoding="utf-8")
    total = sum(len(o) for o in index.formations.offres.values())
    print(
        f"{total} formations ({len(index.formations.mentions)} diplômes) dans "
        f"{len(index.formations.offres)} villes, cohorte {index.annee}"
    )


if __name__ == "__main__":
    main()
