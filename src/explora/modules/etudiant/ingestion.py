"""Job d'ingestion du module villes étudiantes : collecte, indicateurs, scores, export.

Pour chaque ville de `data/villes_etudiantes.csv`, interroge les sources publiques, calcule
les indicateurs clés et le score sur 4 axes, puis écrit le GeoJSON lu par le front :

    uv run python -m explora.modules.etudiant.ingestion

Une source en panne n'arrête pas le job : ses indicateurs restent à `null` et les erreurs
sont comptées dans les métadonnées de l'export. Les réponses sont gardées en cache disque
(`data/cache/ingestion`), si bien qu'un job interrompu repart de là où il s'était arrêté.
"""

import argparse
import asyncio
import csv
import json
import logging
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Awaitable, Iterable, Sequence
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypeVar

from explora.adapters import (
    Dv3fAdapter,
    GeoApiAdapter,
    GeorisquesAdapter,
    InseeMelodiAdapter,
    LoyersAdapter,
    ResidencesEtudiantesAdapter,
    VoeuxFormationsAdapter,
)
from explora.adapters.residences_etudiantes import FLUX
from explora.core.adapter import SourceAdapter
from explora.core.cache import Cache, FileCache
from explora.core.config import get_settings
from explora.core.errors import SourceError
from explora.core.http import RetryPolicy, SourceClient
from explora.core.models import (
    FormationVoeux,
    LogementsCommune,
    LoyerCommune,
    Point,
    PrixImmobilierCommune,
    ResidenceEtudiante,
    RisqueCommune,
)
from explora.core.ratelimit import RateLimiter
from explora.modules.etudiant import indicators
from explora.modules.etudiant.scoring import INDICATEURS, Axe, scorer

logger = logging.getLogger(__name__)

T = TypeVar("T")

VERSION_EXPORT = 1
# Ressource « appartement 1-2 pièces » de la carte des loyers 2025 (data.gouv.fr).
LOYERS_T1T2 = "/api/1/datasets/r/14a1fe11-b2d1-49b3-9f6b-83d12df9482c"
ANNEE_BPE = "2025"
# Indicateurs du score dont la source n'est pas encore branchée.
INDICATEURS_MANQUANTS = (
    "vitalite_commerciale",
    "arrets_transport_pour_1000",
    "stations_velo",
    "indice_qualite_air",
)
AVERTISSEMENTS = (
    "Outil indépendant, sans lien avec les organismes producteurs des données.",
    "Loyers : estimations à la commune, pas au quartier (charges comprises, non meublé).",
    "Rendement locatif brut indicatif, qui ne constitue pas un conseil en investissement.",
)
SOURCES_UTILISEES: tuple[type[SourceAdapter], ...] = (
    GeoApiAdapter,
    LoyersAdapter,
    Dv3fAdapter,
    GeorisquesAdapter,
    InseeMelodiAdapter,
    ResidencesEtudiantesAdapter,
    VoeuxFormationsAdapter,
)


@dataclass(frozen=True)
class Ville:
    code_insee: str
    nom: str
    code_departement: str
    departement: str
    population: int | None
    effectif_etudiants: int
    formations: tuple[str, ...]


def lire_villes(chemin: Path) -> list[Ville]:
    with chemin.open(encoding="utf-8", newline="") as f:
        return [
            Ville(
                code_insee=row["code_insee"],
                nom=row["nom"],
                code_departement=row["code_departement"],
                departement=row["departement"],
                population=int(row["population"]) if row["population"] else None,
                effectif_etudiants=int(row["effectif_etudiants"]),
                formations=tuple(f for f in row["formations"].split(";") if f),
            )
            for row in csv.DictReader(f)
        ]


@dataclass
class Collecte:
    """Données brutes d'une ville. `None` = source en panne ; liste vide = rien trouvé."""

    ville: Ville
    centre: Point | None = None
    loyer: LoyerCommune | None = None
    prix: PrixImmobilierCommune | None = None
    risques: RisqueCommune | None = None
    logements: LogementsCommune | None = None
    equipements: dict[str, int] | None = None
    residences: list[ResidenceEtudiante] | None = None
    formations: list[FormationVoeux] | None = None


# --- Rattachement des formations post-bac (la source n'a pas de code INSEE) -------------

_ARRONDISSEMENT = re.compile(r"\s+\d+\s*(?:er|e|eme)?\s+arrondissement$")


def normaliser_nom(nom: str) -> str:
    """`Saint-Étienne` -> `saint etienne` ; `Paris  5e  Arrondissement` -> `paris`."""
    texte = re.sub(r"[-'\u2019]", " ", nom.lower())
    texte = texte.replace("\u0153", "oe").replace("\u00e6", "ae")  # ligatures œ, æ
    texte = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    texte = " ".join(texte.split())
    texte = _ARRONDISSEMENT.sub("", texte)
    texte = re.sub(r"\bste\b", "sainte", texte)
    return re.sub(r"\bst\b", "saint", texte)


def rattacher_formations(
    formations: Iterable[FormationVoeux], villes: Iterable[Ville]
) -> dict[str, list[FormationVoeux]]:
    """Formations par code INSEE, en comparant le libellé de la ville dans le département."""
    index = {(v.code_departement, normaliser_nom(v.nom)): v.code_insee for v in villes}
    par_ville: dict[str, list[FormationVoeux]] = defaultdict(list)
    for formation in formations:
        code = index.get((formation.code_departement, normaliser_nom(formation.ville)))
        if code is not None:
            par_ville[code].append(formation)
    return par_ville


# --- Indicateurs ---------------------------------------------------------------------


@dataclass(frozen=True)
class Tension:
    valeur: float | None
    """Valeur affichée : étudiants par place en résidence si toutes les résidences de la ville
    ont une capacité connue, sinon étudiants par logement loué meublé."""
    methode: str | None
    """`places_residences`, `locataires_meubles` ou `None` (aucune donnée)."""
    par_meuble: float | None
    """Étudiants par logement loué meublé : seule mesure disponible partout, utilisée par le
    score pour comparer toutes les villes sur la même base."""
    places_residences: int | None


def tension(
    etudiants: int,
    residences: Sequence[ResidenceEtudiante] | None,
    logements: LogementsCommune | None,
) -> Tension:
    meubles = (
        round(logements.locataires_meubles) if logements and logements.locataires_meubles else None
    )
    par_meuble = indicators.tension_locative(etudiants, meubles)
    places = None
    if residences and all(r.places_estimees for r in residences):
        places = sum(r.places_estimees or 0 for r in residences)
        return Tension(
            indicators.tension_locative(etudiants, places), "places_residences", par_meuble, places
        )
    if residences:
        connues = [r.places_estimees for r in residences if r.places_estimees]
        places = sum(connues) if connues else None
    methode = "locataires_meubles" if par_meuble is not None else None
    return Tension(par_meuble, methode, par_meuble, places)


@dataclass(frozen=True)
class Indicateurs:
    valeurs: dict[str, float | None]
    """Valeurs affichées : ids de `scoring.INDICATEURS` plus `rendement_brut`."""
    pour_score: dict[str, float | None]
    tension: Tension


def calculer_indicateurs(c: Collecte) -> Indicateurs:
    v = c.ville
    formations = c.formations
    t = tension(v.effectif_etudiants, c.residences, c.logements)
    loyer_m2 = c.loyer.loyer_m2 if c.loyer else None
    prix_m2 = c.prix.prix_m2 if c.prix else None
    valeurs: dict[str, float | None] = dict.fromkeys(ind.id for ind in INDICATEURS)
    valeurs.update(
        effectifs_etudiants=v.effectif_etudiants,
        # Rien de rattaché ne prouve pas l'absence de formation : on laisse vide.
        nb_etablissements=len({f.code_uai for f in formations}) if formations else None,
        nb_filieres=len({f.filiere for f in formations}) if formations else None,
        loyer_m2=loyer_m2,
        prix_m2=prix_m2,
        tension_locative=t.valeur,
        commerces_pour_1000=indicators.pour_1000(
            indicators.nb_commerces(c.equipements), v.population
        ),
        equipements_culture_sport_pour_1000=indicators.pour_1000(
            indicators.nb_equipements_culture_sport(c.equipements), v.population
        ),
        nb_risques=len(c.risques.risques) if c.risques else None,
        rendement_brut=indicators.rendement_locatif_brut(loyer_m2, prix_m2),
    )
    pour_score = {ind.id: valeurs[ind.id] for ind in INDICATEURS}
    pour_score["tension_locative"] = t.par_meuble
    return Indicateurs(valeurs, pour_score, t)


# --- Export GeoJSON ------------------------------------------------------------------


def _arrondi(valeur: float | None, chiffres: int = 2) -> float | None:
    return None if valeur is None else round(valeur, chiffres)


def construire_geojson(
    collectes: Sequence[Collecte], *, genere_le: datetime, erreurs: Counter[str]
) -> dict[str, Any]:
    calcules = {c.ville.code_insee: calculer_indicateurs(c) for c in collectes}
    scores = scorer({code: ind.pour_score for code, ind in calcules.items()})
    features = []
    for c in collectes:
        v = c.ville
        ind = calcules[v.code_insee]
        score = scores[v.code_insee]
        valeurs = {
            k: _arrondi(x, 4 if k == "rendement_brut" else 2) for k, x in ind.valeurs.items()
        }
        features.append(
            {
                "type": "Feature",
                "geometry": (
                    {"type": "Point", "coordinates": [c.centre.lon, c.centre.lat]}
                    if c.centre
                    else None
                ),
                "properties": {
                    "code_insee": v.code_insee,
                    "nom": v.nom,
                    "code_departement": v.code_departement,
                    "departement": v.departement,
                    "population": v.population,
                    "effectif_etudiants": v.effectif_etudiants,
                    "formations": list(v.formations),
                    "score": _arrondi(score.global_, 1),
                    "axes": {axe.value: _arrondi(score.axes[axe], 1) for axe in Axe},
                    "couverture": round(score.couverture, 2),
                    "indicateurs": valeurs,
                    "risques": c.risques.risques if c.risques else [],
                    "indicateurs_demo": [],
                    "details": {
                        "tension_methode": ind.tension.methode,
                        "etudiants_par_meuble": _arrondi(ind.tension.par_meuble),
                        "places_residences_estimees": ind.tension.places_residences,
                        "nb_residences": len(c.residences) if c.residences is not None else None,
                        "loyer_fiable": c.loyer.fiable if c.loyer else None,
                        "prix_m2_typologie": c.prix.typologie if c.prix else None,
                        "prix_m2_annee": c.prix.annee if c.prix else None,
                        "prix_m2_nb_ventes": c.prix.nb_transactions if c.prix else None,
                        "recensement_annee": c.logements.annee if c.logements else None,
                    },
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "metadata": {
            "genere_le": genere_le.isoformat(timespec="seconds"),
            "demo": False,
            "version": VERSION_EXPORT,
            "nb_villes": len(features),
            "indicateurs_manquants": list(INDICATEURS_MANQUANTS),
            "erreurs_par_source": dict(sorted(erreurs.items())),
            "avertissements": list(AVERTISSEMENTS),
            "sources": [
                {k: asdict(s.info)[k] for k in ("id", "name", "attribution", "licence", "url")}
                for s in SOURCES_UTILISEES
            ],
        },
        "features": features,
    }


def ecrire_geojson(geojson: dict[str, Any], chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=1)
        f.write("\n")


# --- Collecte ------------------------------------------------------------------------


@dataclass
class Sources:
    geo: GeoApiAdapter
    loyers: LoyersAdapter
    dv3f: Dv3fAdapter
    georisques: GeorisquesAdapter
    melodi: InseeMelodiAdapter
    residences: ResidencesEtudiantesAdapter
    voeux: VoeuxFormationsAdapter
    erreurs: Counter[str] = field(default_factory=Counter)

    async def essayer(self, source: str, appel: Awaitable[T]) -> T | None:
        """Résultat de l'appel, ou `None` (erreur comptée) si la source a échoué."""
        try:
            return await appel
        except SourceError as exc:
            logger.warning("%s", exc)
            self.erreurs[source] += 1
            return None


_CODE_POSTAL_VILLE = re.compile(r"\b(\d{5})\s+([^,\d][^,]*)$")


class Lieu(Protocol):
    @property
    def code_insee(self) -> str: ...
    @property
    def nom(self) -> str: ...
    @property
    def code_departement(self) -> str: ...


class IndexCommunes:
    """Recherche d'une commune par son nom, quelle que soit la graphie."""

    def __init__(self, communes: Iterable[Lieu]) -> None:
        self._par_nom: dict[str, list[Lieu]] = defaultdict(list)
        for c in communes:
            self._par_nom[normaliser_nom(c.nom)].append(c)

    def par_adresse(self, adresse: str | None) -> str | None:
        """Code INSEE d'après la fin de l'adresse (« 38400 Saint-Martin-d'Hères »).

        Le code postal départage les homonymes ; `None` si aucune commune ne correspond.
        """
        match = _CODE_POSTAL_VILLE.search(" ".join((adresse or "").split()))
        if match is None:
            return None
        code_postal, nom = match.groups()
        candidates = self._par_nom.get(normaliser_nom(nom), [])
        if len(candidates) > 1:
            candidates = [c for c in candidates if code_postal.startswith(c.code_departement[:2])]
        return candidates[0].code_insee if len(candidates) == 1 else None


async def _residences_par_ville(
    sources: Sources, villes: Sequence[Ville], communes: Sequence[Lieu] | None
) -> dict[str, list[ResidenceEtudiante]] | None:
    """Résidences rattachées à leur commune par l'adresse, sinon par leurs coordonnées.

    L'adresse est comparée à toutes les communes de France quand la liste est disponible ;
    les coordonnées (un appel par résidence) rattrapent les communes déléguées, comme
    Annecy-le-Vieux dans Annecy, et les adresses sans code postal.
    """
    flux = await asyncio.gather(
        *(sources.essayer("residences-etudiantes", sources.residences.residences(f)) for f in FLUX)
    )
    if all(f is None for f in flux):
        return None
    codes = {v.code_insee for v in villes}
    index = IndexCommunes(communes or villes)
    par_ville: dict[str, list[ResidenceEtudiante]] = defaultdict(list)
    a_localiser = []
    for residence in (r for f in flux if f for r in f):
        code = index.par_adresse(residence.adresse)
        if code is not None:
            if code in codes:
                par_ville[code].append(residence)
        elif residence.point is not None:
            a_localiser.append((residence, residence.point))
    limite = asyncio.Semaphore(10)

    async def localiser(point: Point) -> str | None:
        async with limite:
            return await sources.essayer("geo-api", sources.geo.code_au_point(point))

    trouves = await asyncio.gather(*(localiser(p) for _, p in a_localiser))
    logger.info("%d résidences localisées par leurs coordonnées", len(a_localiser))
    for (residence, _), code in zip(a_localiser, trouves, strict=True):
        if code in codes:
            par_ville[code].append(residence)
    return par_ville


async def _formations_par_ville(
    sources: Sources, villes: Sequence[Ville]
) -> dict[str, list[FormationVoeux]] | None:
    deps = sorted({v.code_departement for v in villes})
    # Un département = une dizaine de pages lues à la suite : tous en même temps, ils
    # épuisent le pool de connexions avant que le serveur, lent, ne réponde.
    limite = asyncio.Semaphore(4)

    async def departement(code: str) -> list[FormationVoeux] | None:
        async with limite:
            return await sources.essayer("voeux-formations", sources.voeux.formations(code))

    resultats = await asyncio.gather(*(departement(d) for d in deps))
    if all(r is None for r in resultats):
        return None
    formations = [f for r in resultats if r for f in r]
    return rattacher_formations(formations, villes)


async def collecter(
    villes: Sequence[Ville],
    sources: Sources,
    *,
    loyers_ressource: str = LOYERS_T1T2,
    annee_bpe: str = ANNEE_BPE,
    villes_en_parallele: int = 8,
) -> list[Collecte]:
    communes = await sources.essayer("geo-api", sources.geo.communes())
    loyers, residences, formations = await asyncio.gather(
        sources.essayer("carte-loyers", sources.loyers.loyers(loyers_ressource, "t1t2")),
        _residences_par_ville(sources, villes, communes),
        _formations_par_ville(sources, villes),
    )
    centres = {c.code_insee: c.centre for c in communes or []}
    loyers_par_code = {loyer.code_insee: loyer for loyer in loyers or []}
    logger.info(
        "Sources nationales : %d communes, %d loyers, résidences dans %s villes, "
        "formations dans %s villes",
        len(centres),
        len(loyers_par_code),
        len(residences) if residences is not None else "aucune",
        len(formations) if formations is not None else "aucune",
    )

    limite = asyncio.Semaphore(villes_en_parallele)
    faites = 0

    async def par_ville(v: Ville) -> Collecte:
        nonlocal faites
        async with limite:
            prix, risques, logements, equipements = await asyncio.gather(
                sources.essayer("dv3f", sources.dv3f.prix(v.code_insee)),
                sources.essayer("georisques", sources.georisques.risques(v.code_insee)),
                sources.essayer("insee-melodi", sources.melodi.logements(v.code_insee)),
                sources.essayer(
                    "insee-melodi", sources.melodi.equipements(v.code_insee, annee_bpe)
                ),
            )
        faites += 1
        if faites % 50 == 0:
            logger.info("%d/%d villes collectées", faites, len(villes))
        return Collecte(
            ville=v,
            centre=centres.get(v.code_insee),
            loyer=loyers_par_code.get(v.code_insee),
            prix=prix,
            risques=risques,
            logements=logements,
            equipements=equipements,
            residences=residences.get(v.code_insee, []) if residences is not None else None,
            formations=formations.get(v.code_insee, []) if formations is not None else None,
        )

    return list(await asyncio.gather(*(par_ville(v) for v in villes)))


async def ouvrir_sources(stack: AsyncExitStack, cache: Cache) -> Sources:
    settings = get_settings()

    async def client(
        source: str, base_url: str, rate: float, timeout_s: float = 60
    ) -> SourceClient:
        # Les sources publiques coupent souvent la négociation TLS : tentatives généreuses.
        return await stack.enter_async_context(
            SourceClient(
                source,
                base_url,
                rate_limiter=RateLimiter(rate=rate, burst=max(1, int(rate))),
                cache=cache,
                cache_ttl_s=settings.cache_ttl_s * 7,
                retry=RetryPolicy(max_attempts=10),
                timeout_s=timeout_s,
                user_agent=settings.http_user_agent,
            )
        )

    return Sources(
        geo=GeoApiAdapter(await client("geo-api", settings.geo_api_url, 10, timeout_s=120)),
        loyers=LoyersAdapter(await client("carte-loyers", settings.carte_loyers_url, 1, 180)),
        dv3f=Dv3fAdapter(await client("dv3f", settings.dv3f_url, 4)),
        georisques=GeorisquesAdapter(await client("georisques", settings.georisques_url, 10)),
        melodi=InseeMelodiAdapter(await client("insee-melodi", settings.insee_melodi_url, 2)),
        residences=ResidencesEtudiantesAdapter(
            await client("residences-etudiantes", settings.residences_etudiantes_url, 4)
        ),
        voeux=VoeuxFormationsAdapter(
            await client("voeux-formations", settings.voeux_formations_url, 4)
        ),
    )


async def executer(villes: Sequence[Ville], cache: Cache) -> dict[str, Any]:
    async with AsyncExitStack() as stack:
        sources = await ouvrir_sources(stack, cache)
        collectes = await collecter(villes, sources)
    return construire_geojson(collectes, genere_le=datetime.now(UTC), erreurs=sources.erreurs)


def resume(geojson: dict[str, Any]) -> str:
    features = geojson["features"]
    remplis: Counter[str] = Counter()
    for f in features:
        for k, x in f["properties"]["indicateurs"].items():
            remplis[k] += x is not None
    taux = ", ".join(f"{k} {n}" for k, n in sorted(remplis.items()) if n)
    erreurs = geojson["metadata"]["erreurs_par_source"]
    return (
        f"{len(features)} villes. Indicateurs renseignés : {taux}. Erreurs : {erreurs or 'aucune'}."
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--villes", type=Path, default=Path("data/villes_etudiantes.csv"))
    parser.add_argument(
        "--sortie", type=Path, default=Path("data/export/villes_etudiantes.geojson")
    )
    parser.add_argument("--cache", type=Path, default=Path("data/cache/ingestion"))
    parser.add_argument("--codes", nargs="*", help="limiter à ces codes INSEE (mise au point)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    villes = lire_villes(args.villes)
    if args.codes:
        villes = [v for v in villes if v.code_insee in set(args.codes)]
    geojson = asyncio.run(executer(villes, FileCache(args.cache)))
    ecrire_geojson(geojson, args.sortie)
    print(resume(geojson), file=sys.stderr)


if __name__ == "__main__":
    main()
