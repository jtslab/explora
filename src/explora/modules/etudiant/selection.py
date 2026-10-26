"""Sélection des ~400 villes étudiantes à partir des effectifs inscrits (atlas MESR).

La règle est décrite dans `docs/selection-villes.md`. Usage :

    uv run python -m explora.modules.etudiant.selection --sortie data/villes_etudiantes.csv
"""

import argparse
import asyncio
import csv
import logging
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from explora.adapters import CogAdapter, EffectifsEtudiantsAdapter, GeoApiAdapter
from explora.core.config import get_settings
from explora.core.http import RetryPolicy, SourceClient
from explora.core.models import Commune, Departement, EffectifCommune
from explora.core.plm import commune_de_rattachement

logger = logging.getLogger(__name__)

# Départements de l'unité urbaine de Paris : y plafonner par unité urbaine
# reviendrait à n'y garder que 3 communes pour toute l'agglomération.
SANS_PLAFOND_UNITE_URBAINE = frozenset({"75", "77", "78", "91", "92", "93", "94", "95"})

COLONNES = (
    "code_insee",
    "nom",
    "code_departement",
    "departement",
    "population",
    "effectif_etudiants",
    "rang_departement",
    "prefecture",
    "motif",
    "unite_urbaine",
    "formations",
    "rentree",
)


@dataclass(frozen=True)
class Regle:
    rentree: str = "2025"
    seuil_effectif: int = 100
    """Étudiants inscrits minimum dans la commune."""
    seuil_population: int = 3000
    """Écarte les villages qui n'accueillent qu'une section de BTS (souvent agricole)..."""
    effectif_campus: int = 500
    """... sauf s'ils accueillent un vrai campus (Sevenans, Dury, Saint-Contest...)."""
    par_departement: int = 4
    par_unite_urbaine: int = 3
    cible: int = 400
    """Total visé ; les places laissées libres sont redistribuées aux plus gros effectifs."""
    complement_par_departement: int = 2


@dataclass
class Candidate:
    commune: Commune
    effectif: int
    unite_urbaine: str | None
    formations: set[str] = field(default_factory=set)
    rang: int = 0


@dataclass(frozen=True)
class VilleRetenue:
    code_insee: str
    nom: str
    code_departement: str
    departement: str
    population: int | None
    effectif_etudiants: int
    rang_departement: int
    prefecture: bool
    motif: str
    """`effectif` (dans le top du département), `prefecture` (ajoutée) ou `complement`."""
    unite_urbaine: str | None
    formations: tuple[str, ...]


def candidates(
    effectifs: Iterable[EffectifCommune], communes: Iterable[Commune]
) -> dict[str, list[Candidate]]:
    """Communes avec des étudiants, par département, triées par effectif décroissant.

    Les arrondissements de Paris, Lyon et Marseille sont regroupés en une commune.
    """
    par_code = {c.code_insee: c for c in communes}
    retenues: dict[str, Candidate] = {}
    for eff in effectifs:
        code = commune_de_rattachement(eff.code_insee)
        commune = par_code.get(code)
        if commune is None:
            # Étranger (99xxx) ou code absent du référentiel courant.
            logger.debug("commune %s (%s) ignorée", eff.code_insee, eff.nom)
            continue
        cand = retenues.setdefault(code, Candidate(commune, 0, eff.unite_urbaine))
        if eff.regroupement == "TOTAL":
            cand.effectif += eff.effectif
        elif eff.effectif > 0:
            cand.formations.add(eff.regroupement)
    par_dep: dict[str, list[Candidate]] = defaultdict(list)
    for cand in retenues.values():
        if cand.effectif > 0:
            par_dep[cand.commune.code_departement].append(cand)
    for liste in par_dep.values():
        liste.sort(key=lambda c: (-c.effectif, c.commune.code_insee))
        for rang, cand in enumerate(liste, start=1):
            cand.rang = rang
    return par_dep


def eligible(cand: Candidate, regle: Regle) -> bool:
    if cand.effectif < regle.seuil_effectif:
        return False
    return (cand.commune.population or 0) >= regle.seuil_population or (
        cand.effectif >= regle.effectif_campus
    )


def selectionner(
    effectifs: Iterable[EffectifCommune],
    communes: Iterable[Commune],
    departements: Iterable[Departement],
    regle: Regle | None = None,
) -> list[VilleRetenue]:
    regle = regle or Regle()
    par_dep = candidates(effectifs, communes)
    deps = {d.code: d for d in departements}
    choix: dict[str, list[tuple[Candidate, str]]] = {}
    par_uu: Counter[str] = Counter()

    def plafonne(dep: str, cand: Candidate) -> bool:
        if dep in SANS_PLAFOND_UNITE_URBAINE or cand.unite_urbaine is None:
            return False
        return par_uu[cand.unite_urbaine] >= regle.par_unite_urbaine

    for dep, departement in deps.items():
        retenus: list[tuple[Candidate, str]] = []
        for cand in par_dep.get(dep, []):
            if len(retenus) == regle.par_departement:
                break
            if eligible(cand, regle) and not plafonne(dep, cand):
                retenus.append((cand, "effectif"))
                if cand.unite_urbaine:
                    par_uu[cand.unite_urbaine] += 1
        prefecture = next(
            (c for c in par_dep.get(dep, []) if c.commune.code_insee == departement.chef_lieu),
            None,
        )
        if (
            prefecture is not None
            and eligible(prefecture, regle)
            and all(c is not prefecture for c, _ in retenus)
        ):
            if len(retenus) == regle.par_departement:
                sortant, _ = retenus.pop()
                if sortant.unite_urbaine:
                    par_uu[sortant.unite_urbaine] -= 1
            retenus.append((prefecture, "prefecture"))
            if prefecture.unite_urbaine:
                par_uu[prefecture.unite_urbaine] += 1
        choix[dep] = retenus

    # Complément : les places libres (départements ruraux, Paris) vont aux plus gros
    # effectifs restants, quel que soit leur département. Sans plafond par unité urbaine :
    # ce sont souvent les communes-campus d'une grande ville (Talence, La Tronche...).
    places = regle.cible - sum(len(v) for v in choix.values())
    deja = {c.commune.code_insee for v in choix.values() for c, _ in v}
    reserve = sorted(
        (
            c
            for dep in deps
            for c in par_dep.get(dep, [])
            if c.commune.code_insee not in deja and eligible(c, regle)
        ),
        key=lambda c: (-c.effectif, c.commune.code_insee),
    )
    ajouts: Counter[str] = Counter()
    for cand in reserve:
        if places <= 0:
            break
        dep = cand.commune.code_departement
        if ajouts[dep] >= regle.complement_par_departement:
            continue
        choix[dep].append((cand, "complement"))
        ajouts[dep] += 1
        places -= 1

    villes = []
    for dep in sorted(choix):
        for cand, motif in sorted(choix[dep], key=lambda cm: cm[0].rang):
            villes.append(
                VilleRetenue(
                    code_insee=cand.commune.code_insee,
                    nom=cand.commune.nom,
                    code_departement=dep,
                    departement=deps[dep].nom,
                    population=cand.commune.population,
                    effectif_etudiants=cand.effectif,
                    rang_departement=cand.rang,
                    prefecture=cand.commune.code_insee == deps[dep].chef_lieu,
                    motif=motif,
                    unite_urbaine=cand.unite_urbaine,
                    formations=tuple(sorted(cand.formations)),
                )
            )
    return villes


def ecrire_csv(villes: Iterable[VilleRetenue], chemin: Path, rentree: str) -> None:
    with chemin.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(COLONNES)
        for v in villes:
            writer.writerow(
                [
                    v.code_insee,
                    v.nom,
                    v.code_departement,
                    v.departement,
                    v.population if v.population is not None else "",
                    v.effectif_etudiants,
                    v.rang_departement,
                    "oui" if v.prefecture else "non",
                    v.motif,
                    v.unite_urbaine or "",
                    ";".join(v.formations),
                    rentree,
                ]
            )


async def charger(regle: Regle) -> list[VilleRetenue]:
    settings = get_settings()

    def client(source: str, base_url: str) -> SourceClient:
        # Les sources publiques coupent parfois la connexion TLS : tentatives généreuses.
        return SourceClient(
            source,
            base_url,
            retry=RetryPolicy(max_attempts=10),
            timeout_s=120,
            user_agent=settings.http_user_agent,
        )

    async with (
        client("effectifs-etudiants", settings.effectifs_etudiants_url) as c_eff,
        client("geo-api", settings.geo_api_url) as c_geo,
        client("cog", settings.cog_url) as c_cog,
    ):
        effectifs, communes, departements = await asyncio.gather(
            EffectifsEtudiantsAdapter(c_eff).par_commune(regle.rentree),
            GeoApiAdapter(c_geo).communes(),
            CogAdapter(c_cog).departements(),
        )
    return selectionner(effectifs, communes, departements, regle)


def resume(villes: list[VilleRetenue]) -> str:
    motifs = Counter(v.motif for v in villes)
    par_dep = Counter(v.code_departement for v in villes)
    maigres = sorted(dep for dep, n in par_dep.items() if n < 3)
    return (
        f"{len(villes)} villes dans {len(par_dep)} départements "
        f"({', '.join(f'{m} : {n}' for m, n in sorted(motifs.items()))}). "
        f"Moins de 3 villes : {', '.join(maigres) or 'aucun'}."
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rentree", default=Regle.rentree)
    parser.add_argument("--cible", type=int, default=Regle.cible)
    parser.add_argument("--sortie", type=Path, default=Path("data/villes_etudiantes.csv"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    regle = Regle(rentree=args.rentree, cible=args.cible)
    villes = asyncio.run(charger(regle))
    ecrire_csv(villes, args.sortie, regle.rentree)
    print(resume(villes), file=sys.stderr)


if __name__ == "__main__":
    main()
