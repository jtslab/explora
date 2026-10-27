"""Génère le site statique : la carte, une page par ville, le sitemap.

    uv run python -m explora.site.generer --donnees web/data/villes.demo.geojson --sortie dist/site

Les liens internes sont relatifs, pour que le site marche aussi bien sur explora.app
que dans un sous-dossier (GitHub Pages) ; seules les URL canoniques et le sitemap
utilisent `--base-url`.
"""

import argparse
import json
import math
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from explora.modules.etudiant.scoring import Axe
from explora.site import formations as fm
from explora.site import insertion as ins
from explora.site import metiers as mt
from explora.site import parcours as pc
from explora.site.donnees import ExportVilles, FeatureVille, ProprietesVille, charger, slugs

FORMATIONS = {
    "UNIV": "Université",
    "STS": "BTS",
    "CPGE": "Classes préparatoires",
    "EC_COM": "École de commerce",
    "ING_autres": "École d'ingénieurs",
    "INP": "Institut national polytechnique",
    "UT": "Université de technologie",
    "EC_ART": "École d'art ou d'architecture",
    "EC_PARAM": "Formations paramédicales et sociales",
    "EC_JUR": "École juridique ou administrative",
    "ENS": "École normale supérieure",
    "GE": "Grand établissement",
    "EPEU": "Établissement expérimental",
    "EC_autres": "Autres écoles",
}

AXES = {
    Axe.ETUDES: "Études",
    Axe.BUDGET: "Budget",
    Axe.VIE: "Vie étudiante",
    Axe.MOBILITE_CADRE: "Mobilité et cadre",
}

STUDIO_M2 = 20
"""Surface du studio type utilisée pour traduire les €/m² en loyer et prix concrets."""

ESPACE_FINE = "\u202f"
INSECABLE = "\u00a0"

TYPOLOGIES = {"t1": "studios et T1", "appartements": "tous appartements confondus"}
TENSIONS = {
    "places_residences": "Étudiants par place en résidence étudiante publique ou conventionnée.",
    "locataires_meubles": (
        "Étudiants par logement meublé loué (pas de places en résidence connues)."
    ),
}


@dataclass(frozen=True)
class Ville:
    p: ProprietesVille
    slug: str
    lon: float
    lat: float
    rang: int | None
    """Rang national au score à poids égaux (1 = meilleur)."""
    centile: float | None
    """Position 0-100 dans ce classement (100 = meilleure), qui fixe la couleur du score."""


def distance_km(a: Ville, b: Ville) -> float:
    rad = math.radians
    dlat, dlon = rad(b.lat - a.lat), rad(b.lon - a.lon)
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(rad(a.lat)) * math.cos(rad(b.lat)) * math.sin(dlon / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(h))


def nombre(valeur: float | None, decimales: int = 0, unite: str = "") -> str:
    """Format français : espace fine insécable pour les milliers, virgule décimale."""
    if valeur is None:
        return "n.d."
    texte = f"{valeur:,.{decimales}f}".replace(",", ESPACE_FINE).replace(".", ",")
    return f"{texte}{INSECABLE}{unite}" if unite else texte


RAMPE = ("#f2e3b0", "#a9cfa0", "#4e9c8a", "#24607a", "#1b3354")
"""Couleurs des scores 0 → 100, identiques à `--rampe-*` dans explora.css et carte.js."""


def teinte(score: float | None) -> str:
    """Style inline d'une pastille de score : fond pris sur la rampe, texte lisible dessus."""
    if score is None:
        return "background:var(--trait);color:var(--encre)"
    pos = max(0.0, min(score, 100.0)) / 100 * (len(RAMPE) - 1)
    i = min(int(pos), len(RAMPE) - 2)
    a, b = (tuple(int(c[k : k + 2], 16) for k in (1, 3, 5)) for c in RAMPE[i : i + 2])
    rgb = [round(x + (y - x) * (pos - i)) for x, y in zip(a, b, strict=True)]
    clair = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] > 140
    fond = "#{:02x}{:02x}{:02x}".format(*rgb)
    return f"background:{fond};color:{'#10201c' if clair else '#ffffff'}"


def pourcent(valeur: float | None, decimales: int = 1) -> str:
    return "n.d." if valeur is None else nombre(valeur * 100, decimales, "%")


def devenir(chiffres: ins.Insertion) -> str:
    """« 85 % poursuivent leurs études · parmi les autres, 58 % en emploi à 12 mois · … »."""
    morceaux = []
    if chiffres.poursuite is not None:
        morceaux.append(f"{nombre(chiffres.poursuite, 0, '%')} poursuivent leurs études")
    if chiffres.emploi is not None:
        autres = "parmi les autres, " if morceaux else ""
        morceaux.append(f"{autres}{nombre(chiffres.emploi, 0, '%')} en emploi à 12 mois")
    if chiffres.salaire is not None:
        morceaux.append(f"salaire médian {nombre(chiffres.salaire, 0, '€')} net par mois")
    return " · ".join(morceaux)


def bac_plus(sortie: int | None) -> str:
    """Niveau de sortie court pour une étiquette : « Bac+3 », « Bac+5 et plus »."""
    if sortie is None:
        return "Niveau variable"
    if sortie <= 1:
        return "1 an"
    return f"Bac+{sortie}"


def bacs(parts: tuple[int, int, int] | list[int], long: bool = False) -> str:
    """« 62 % bac général, 30 % techno » : les parts nulles sont omises."""
    noms = (
        ("de bacheliers généraux", "technologiques", "professionnels")
        if long
        else ("bac général", "techno", "pro")
    )
    return ", ".join(f"{p}{INSECABLE}% {nom}" for p, nom in zip(parts, noms, strict=True) if p > 0)


def axes_tries(v: Ville) -> list[tuple[str, float]]:
    notes = [(AXES[axe], v.p.axes.note(axe)) for axe in Axe]
    return sorted(((lib, n) for lib, n in notes if n is not None), key=lambda x: -x[1])


def resume(v: Ville, total: int) -> str:
    p = v.p
    phrases = [
        f"{p.nom} ({p.departement}) compte {nombre(p.effectif_etudiants)} étudiants inscrits "
        f"pour {nombre(p.population)} habitants."
    ]
    tries = axes_tries(v)
    if v.rang and len(tries) >= 2:
        phrases.append(
            f"À importance égale des quatre axes, elle se classe "
            f"{v.rang}{'re' if v.rang == 1 else 'e'} sur {total}. Son axe le plus fort est "
            f"« {tries[0][0].lower()} », le plus faible « {tries[-1][0].lower()} »."
        )
    return " ".join(phrases)


def faq(v: Ville) -> list[tuple[str, str]]:
    p, i = v.p, v.p.indicateurs
    questions = []
    if i.loyer_m2 is not None:
        questions.append(
            (
                f"Combien coûte un studio étudiant à {p.nom} ?",
                f"Avec un loyer moyen estimé à {nombre(i.loyer_m2, 1, '€/m²')} charges comprises, "
                f"un studio de {STUDIO_M2} m² revient à environ "
                f"{nombre(i.loyer_m2 * STUDIO_M2, 0, '€')} par mois, hors aides au logement. "
                "C'est une moyenne à l'échelle de la commune : les écarts entre quartiers "
                "peuvent être importants.",
            )
        )
    if p.effectif_etudiants:
        questions.append(
            (
                f"Combien y a-t-il d'étudiants à {p.nom} ?",
                f"{nombre(p.effectif_etudiants)} étudiants sont inscrits dans une formation après "
                f"le bac à {p.nom}, répartis entre {nombre(len(p.formations))} types de "
                "formation : "
                + ", ".join(FORMATIONS.get(f, f).lower() for f in p.formations)
                + ".",
            )
        )
    if i.rendement_brut is not None and i.prix_m2 is not None:
        questions.append(
            (
                f"Investir dans un studio étudiant à {p.nom} est-il rentable ?",
                f"Le rendement locatif brut estimé est de {pourcent(i.rendement_brut)}, pour un "
                f"prix médian de {nombre(i.prix_m2, 0, '€/m²')}. Ce chiffre est indicatif : il "
                "ne tient compte ni des charges, ni de la fiscalité, ni de la vacance, et ne "
                "constitue pas un conseil en investissement.",
            )
        )
    return questions


def faq_jsonld(v: Ville) -> list[dict[str, object]]:
    return [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": r}}
        for q, r in faq(v)
    ]


def villes_de(export: ExportVilles) -> list[Ville]:
    proprietes = [f.properties for f in export.features]
    par_slug = slugs(proprietes)
    classees = sorted(
        (f for f in export.features if f.properties.score is not None),
        key=lambda f: -(f.properties.score or 0),
    )
    rangs = {f.properties.code_insee: i for i, f in enumerate(classees, start=1)}

    def ville(f: FeatureVille) -> Ville:
        lon, lat = f.geometry.coordinates
        code = f.properties.code_insee
        rang = rangs.get(code)
        centile = None if rang is None else 100 * (len(rangs) - rang) / max(len(rangs) - 1, 1)
        return Ville(f.properties, par_slug[code], lon, lat, rang, centile)

    return [ville(f) for f in export.features]


def _environnement(dossier_web: Path) -> Environment:
    env = Environment(
        loader=FileSystemLoader(dossier_web / "templates"),
        autoescape=select_autoescape(),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["nombre"] = nombre
    env.filters["pourcent"] = pourcent
    env.filters["teinte"] = teinte
    env.filters["devenir"] = devenir
    env.filters["bac_plus"] = bac_plus
    env.filters["bacs"] = bacs
    env.globals.update(
        FORMATIONS=FORMATIONS,
        AXES=AXES,
        AXES_ENUM=Axe,
        STUDIO_M2=STUDIO_M2,
        TYPOLOGIES=TYPOLOGIES,
        TENSIONS=TENSIONS,
        resume=resume,
        faq=faq,
        faq_jsonld=faq_jsonld,
        FAMILLES=pc.FAMILLES,
        ACCES=pc.ACCES,
        NIVEAUX_SORTIE=pc.NIVEAUX_SORTIE,
    )
    return env


@dataclass(frozen=True)
class OffreVille:
    """Une formation dans un établissement, avec ses parcours (une fiche chacun)."""

    etablissement: str
    public: bool
    apprentissage: bool
    urls: tuple[str, ...]
    insertion: ins.Insertion | None = None
    """Devenir des diplômés de l'établissement (le chiffre national va sur la formation)."""
    acces: pc.OffreAcces | None = None
    """Sélectivité et taux d'accès de la dernière session (premier parcours connu)."""


@dataclass(frozen=True)
class FormationVille:
    mention: str
    offres: tuple[OffreVille, ...]
    metiers: tuple[str, ...] = ()
    """Métiers visés d'après le RNCP (libellés ROME)."""
    insertion_nationale: ins.Insertion | None = None
    parcours: pc.MentionParcours | None = None
    """Famille, niveau de sortie, profil des admis."""


def formations_par_type(
    index: fm.IndexFormations | None,
    code_insee: str,
    metiers: mt.IndexMetiers | None = None,
    insertion: ins.IndexInsertion | None = None,
    parcours: pc.IndexParcours | None = None,
) -> list[tuple[str, list[FormationVille]]]:
    """Formations d'une ville groupées par type (BTS, Licence...), les plus fournis d'abord.

    Une mention proposée par plusieurs établissements n'apparaît qu'une fois, avec la liste
    de ses établissements.
    """
    if index is None:
        return []
    # mention → établissement → offres (un établissement propose parfois plusieurs parcours)
    par_mention: dict[int, dict[str, list[fm.Offre]]] = defaultdict(lambda: defaultdict(list))
    nationale: dict[int, ins.Insertion] = {}
    for o in index.offres.get(code_insee, []):
        etab = index.etablissements.get(o.uai)
        par_mention[o.mention][etab.nom if etab else o.uai].append(o)
        chiffres = insertion.offres.get(o.code) if insertion else None
        if chiffres and chiffres.national:
            nationale[o.mention] = chiffres

    def offre_ville(nom: str, offres: list[fm.Offre]) -> OffreVille:
        etab = index.etablissements.get(offres[0].uai)
        locaux = [
            c
            for o in offres
            if insertion and (c := insertion.offres.get(o.code)) and not c.national
        ]
        return OffreVille(
            etablissement=nom,
            public=bool(etab and etab.secteur == "Publics"),
            apprentissage=any(o.apprentissage for o in offres),
            urls=tuple(
                fm.URL_FICHE.format(code=o.code) for o in sorted(offres, key=lambda o: o.code)
            ),
            insertion=locaux[0] if locaux else None,
            acces=next(
                (a for o in offres if parcours and (a := parcours.offres.get(o.code))), None
            ),
        )

    groupes: dict[str, list[FormationVille]] = defaultdict(list)
    for i, etabs in par_mention.items():
        mention = index.mentions[i]
        corresp = metiers.mentions.get(mention.libelle) if metiers else None
        groupes[index.types[mention.type]].append(
            FormationVille(
                mention=mention.libelle,
                offres=tuple(offre_ville(nom, o) for nom, o in sorted(etabs.items())),
                metiers=tuple(metiers.metiers[c] for c in corresp.romes)
                if metiers and corresp
                else (),
                insertion_nationale=nationale.get(i),
                parcours=parcours.mentions.get(mention.libelle) if parcours else None,
            )
        )
    return sorted(
        ((t, sorted(f, key=lambda x: fm.normaliser(x.mention))) for t, f in groupes.items()),
        key=lambda g: (-sum(len(f.offres) for f in g[1]), g[0]),
    )


def _index_carte(
    index: fm.IndexFormations,
    metiers: mt.IndexMetiers | None = None,
    parcours: pc.IndexParcours | None = None,
) -> str:
    """Mentions et villes qui les proposent, métiers et secteurs, pour la recherche."""
    villes = index.villes_par_mention()

    def niveaux(libelle: str) -> list[object]:
        # [famille, bac+N de sortie, accès, % bac général/techno/pro, doublettes]
        m = parcours.mentions.get(libelle) if parcours else None
        if m is None:
            return []
        spe = m.specialites or (parcours.specialites_familles.get(m.famille) if parcours else None)
        return [
            m.famille,
            m.sortie,
            m.acces,
            list(m.profil.bacs) if m.profil else None,
            [list(d) for d in spe.doublettes] if spe else None,
        ]

    par_metier: dict[str, list[int]] = defaultdict(list)
    if metiers:
        for i, m in enumerate(index.mentions):
            corresp = metiers.mentions.get(m.libelle)
            for code in corresp.romes if corresp else []:
                par_metier[code].append(i)
    return json.dumps(
        {
            "session": index.session,
            "types": index.types,
            "mentions": [
                [m.libelle, m.type, villes[i], *niveaux(m.libelle)]
                for i, m in enumerate(index.mentions)
            ],
            # famille → [titre, niveau de sortie en clair, admissions parallèles (bac+N)]
            "familles": {k: [f.titre, f.sortie, list(f.entrees)] for k, f in pc.FAMILLES.items()}
            if parcours
            else {},
            # [code ROME, libellé, indices des mentions] ; le secteur est la 1re lettre du code.
            "metiers": [
                [code, metiers.metiers[code], mentions]
                for code, mentions in sorted(par_metier.items())
            ]
            if metiers
            else [],
            "secteurs": sorted(metiers.domaines.items()) if metiers else [],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def generer(
    export: ExportVilles,
    dossier_web: Path,
    sortie: Path,
    base_url: str,
    formations: fm.IndexFormations | None = None,
    metiers: mt.IndexMetiers | None = None,
    insertion: ins.IndexInsertion | None = None,
    parcours: pc.IndexParcours | None = None,
) -> list[Path]:
    """Écrit le site dans `sortie` et renvoie les pages produites."""
    base_url = base_url.rstrip("/")
    env = _environnement(dossier_web)
    villes = villes_de(export)
    par_departement: dict[tuple[str, str], list[Ville]] = defaultdict(list)
    for v in sorted(villes, key=lambda v: (v.p.code_departement, -(v.p.effectif_etudiants or 0))):
        par_departement[(v.p.code_departement, v.p.departement)].append(v)

    if sortie.exists():
        shutil.rmtree(sortie)
    shutil.copytree(dossier_web / "assets", sortie / "assets")
    (sortie / "data").mkdir(parents=True)
    (sortie / "data" / "villes.geojson").write_text(
        _geojson_carte(export, villes), encoding="utf-8"
    )
    if formations is not None:
        (sortie / "data" / "formations-index.json").write_text(
            _index_carte(formations, metiers, parcours), encoding="utf-8"
        )
    commun = {
        "meta": export.metadata,
        "base_url": base_url,
        "total": len(villes),
        "session_formations": formations.session if formations else None,
        "source_metiers": metiers.source if metiers else None,
        "insertion": insertion is not None,
        "parcours": parcours,
    }

    pages = [sortie / "index.html"]
    pages[0].write_text(
        env.get_template("carte.html").render(
            page="carte", racine="./", par_departement=par_departement, **commun
        ),
        encoding="utf-8",
    )
    gabarit = env.get_template("ville.html")
    for v in villes:
        proches = sorted((o for o in villes if o is not v), key=lambda o: distance_km(v, o))[:4]
        page = sortie / "villes" / v.slug / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(
            gabarit.render(
                page="ville",
                racine="../../",
                v=v,
                proches=[(o, distance_km(v, o)) for o in proches],
                formations=formations_par_type(
                    formations, v.p.code_insee, metiers, insertion, parcours
                ),
                **commun,
            ),
            encoding="utf-8",
        )
        pages.append(page)

    if parcours is not None:
        page = sortie / "parcours" / "index.html"
        page.parent.mkdir(parents=True)
        page.write_text(
            env.get_template("parcours.html").render(page="parcours", racine="../", **commun),
            encoding="utf-8",
        )
        pages.append(page)

    urls = [f"{base_url}/"] + [f"{base_url}/villes/{v.slug}/" for v in villes]
    if parcours is not None:
        urls.append(f"{base_url}/parcours/")
    (sortie / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls)
        + "</urlset>\n",
        encoding="utf-8",
    )
    (sortie / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {base_url}/sitemap.xml\n", encoding="utf-8"
    )
    return pages


def _geojson_carte(export: ExportVilles, villes: list[Ville]) -> str:
    """Version allégée et à plat pour la carte (MapLibre n'indexe pas les objets imbriqués)."""
    features = [
        {
            "type": "Feature",
            "id": i,
            "geometry": {"type": "Point", "coordinates": [v.lon, v.lat]},
            "properties": {
                "code": v.p.code_insee,
                "nom": v.p.nom,
                "slug": v.slug,
                "dep": v.p.code_departement,
                "departement": v.p.departement,
                "etudiants": v.p.effectif_etudiants or 0,
                "loyer_m2": v.p.indicateurs.loyer_m2,
                "rendement": v.p.indicateurs.rendement_brut,
                **{f"axe_{axe.value}": v.p.axes.note(axe) for axe in Axe},
            },
        }
        for i, v in enumerate(villes)
    ]
    meta = export.metadata.model_dump(mode="json", include={"genere_le", "demo", "version"})
    return json.dumps(
        {"type": "FeatureCollection", "metadata": meta, "features": features},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--donnees", type=Path, default=Path("data/export/villes_etudiantes.geojson")
    )
    parser.add_argument("--web", type=Path, default=Path("web"))
    parser.add_argument("--sortie", type=Path, default=Path("dist/site"))
    parser.add_argument("--formations", type=Path, default=Path("web/data/formations.json"))
    parser.add_argument("--metiers", type=Path, default=Path("web/data/metiers.json"))
    parser.add_argument("--insertion", type=Path, default=Path("web/data/insertion.json"))
    parser.add_argument("--parcours", type=Path, default=Path("web/data/parcours.json"))
    parser.add_argument("--base-url", default="https://explora.app")
    args = parser.parse_args()
    index = fm.charger(args.formations) if args.formations.exists() else None
    index_metiers = mt.charger(args.metiers) if args.metiers.exists() else None
    index_insertion = ins.charger(args.insertion) if args.insertion.exists() else None
    index_parcours = pc.charger(args.parcours) if args.parcours.exists() else None
    pages = generer(
        charger(args.donnees),
        args.web,
        args.sortie,
        args.base_url,
        index,
        index_metiers,
        index_insertion,
        index_parcours,
    )
    print(f"{len(pages)} pages écrites dans {args.sortie}")


if __name__ == "__main__":
    main()
