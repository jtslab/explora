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
    )
    return env


def generer(export: ExportVilles, dossier_web: Path, sortie: Path, base_url: str) -> list[Path]:
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
    commun = {"meta": export.metadata, "base_url": base_url, "total": len(villes)}

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
                **commun,
            ),
            encoding="utf-8",
        )
        pages.append(page)

    urls = [f"{base_url}/"] + [f"{base_url}/villes/{v.slug}/" for v in villes]
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
    parser.add_argument("--donnees", type=Path, default=Path("web/data/villes.demo.geojson"))
    parser.add_argument("--web", type=Path, default=Path("web"))
    parser.add_argument("--sortie", type=Path, default=Path("dist/site"))
    parser.add_argument("--base-url", default="https://explora.app")
    args = parser.parse_args()
    pages = generer(charger(args.donnees), args.web, args.sortie, args.base_url)
    print(f"{len(pages)} pages écrites dans {args.sortie}")


if __name__ == "__main__":
    main()
