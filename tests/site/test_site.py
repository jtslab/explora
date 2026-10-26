import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from explora.core.models import OffreFormation
from explora.site import demo
from explora.site import formations as fm
from explora.site.donnees import (
    Axes,
    ExportVilles,
    FeatureVille,
    Indicateurs,
    Metadonnees,
    PointGeo,
    ProprietesVille,
    charger,
    ecrire,
    slugifier,
    slugs,
)
from explora.site.generer import generer, nombre, pourcent, teinte

RACINE = Path(__file__).resolve().parents[2]


def _ville(code: str, nom: str, dep: str, lon: float, lat: float, score: float) -> FeatureVille:
    return FeatureVille(
        geometry=PointGeo(coordinates=(lon, lat)),
        properties=ProprietesVille(
            code_insee=code,
            nom=nom,
            code_departement=dep,
            departement="Département " + dep,
            population=100_000,
            effectif_etudiants=20_000,
            formations=["UNIV", "STS"],
            axes=Axes(etudes=score, budget=40, vie=None, mobilite_cadre=55),
            score=score,
            couverture=0.75,
            indicateurs=Indicateurs(loyer_m2=12.4, prix_m2=3100, rendement_brut=0.048),
            risques=["Inondation"],
        ),
    )


def _offre(commune: str, departement: str, mention: str, uai: str, code: str) -> OffreFormation:
    return OffreFormation(
        session="2026",
        code=code,
        code_uai=uai,
        etablissement=f"Lycée {uai} (35)",
        secteur="Publics",
        types=["BTS - BTSA - BTSM"],
        mentions=[mention],
        commune=commune,
        departement=departement,
    )


@pytest.fixture
def formations() -> fm.IndexFormations:
    villes = [
        {"code_insee": "35238", "nom": "Rennes", "departement": "Ille-et-Vilaine"},
        {"code_insee": "97411", "nom": "Saint-Denis", "departement": "La Réunion"},
        {"code_insee": "93066", "nom": "Saint-Denis", "departement": "Seine-Saint-Denis"},
    ]
    offres = [
        _offre("Rennes", "Ille-et-Vilaine", "BTS - Tourisme", "A", "1"),
        _offre("Rennes", "Ille-et-Vilaine", "BTS - Tourisme", "A", "1"),  # doublon
        _offre("Saint-Denis", "La Réunion", "BTS - Tourisme", "B", "2"),
        _offre("Saint-Denis", "Seine-Saint-Denis", "BTS - Communication", "C", "3"),
        _offre("Brest", "Finistère", "BTS - Tourisme", "D", "4"),  # hors liste
    ]
    return fm.construire(offres, villes)


def test_index_formations(formations: fm.IndexFormations) -> None:
    assert [m.libelle for m in formations.mentions] == ["BTS - Communication", "BTS - Tourisme"]
    assert formations.villes_par_mention() == [["93066"], ["35238", "97411"]]
    assert len(formations.offres["35238"]) == 1
    assert formations.etablissements["A"].nom == "Lycée A"


def test_generer_avec_formations(
    export: ExportVilles, formations: fm.IndexFormations, tmp_path: Path
) -> None:
    generer(export, RACINE / "web", tmp_path, "https://explora.app", formations)
    index = json.loads((tmp_path / "data" / "formations-index.json").read_text())
    assert index["mentions"][1] == ["BTS - Tourisme", 0, ["35238", "97411"]]
    html = (tmp_path / "villes" / "saint-denis-974" / "index.html").read_text()
    assert "1 formation après le bac à Saint-Denis" in html
    assert "g_ta_cod=2&" in html


@pytest.fixture
def export() -> ExportVilles:
    return ExportVilles(
        metadata=Metadonnees(genere_le=datetime(2026, 10, 26, tzinfo=UTC)),
        features=[
            _ville("35238", "Rennes", "35", -1.68, 48.11, 70),
            _ville("93066", "Saint-Denis", "93", 2.36, 48.93, 50),
            _ville("97411", "Saint-Denis", "974", 55.45, -20.89, 60),
        ],
    )


def test_slugs() -> None:
    assert slugifier("L'Haÿ-les-Roses") == "l-hay-les-roses"
    assert slugifier("Saint-Étienne") == "saint-etienne"
    assert slugifier("Schœlcher") == "schoelcher"


def test_slugs_homonymes(export: ExportVilles) -> None:
    assert slugs([f.properties for f in export.features]) == {
        "35238": "rennes",
        "93066": "saint-denis-93",
        "97411": "saint-denis-974",
    }


def test_formats() -> None:
    assert nombre(72322) == "72\u202f322"
    assert nombre(12.34, 1, "€/m²") == "12,3\u00a0€/m²"
    assert nombre(None) == "n.d."
    assert pourcent(0.0482) == "4,8\u00a0%"
    assert teinte(0).startswith("background:#f2e3b0;color:#10201c")
    assert teinte(100).startswith("background:#1b3354;color:#ffffff")


def test_generer(export: ExportVilles, tmp_path: Path) -> None:
    pages = generer(export, RACINE / "web", tmp_path, "https://explora.app/")
    assert len(pages) == 4

    html = (tmp_path / "villes" / "rennes" / "index.html").read_text()
    assert (
        "<title>Logement étudiant à Rennes : loyers, prix, vie étudiante | Explora</title>" in html
    )
    assert '<link rel="canonical" href="https://explora.app/villes/rennes/">' in html
    assert "estimations à l'échelle de la commune" in html
    assert "ne constitue pas un conseil en investissement" in html
    assert "outil indépendant" in html
    assert 'href="../../villes/saint-denis-93/"' in html  # villes proches, liens relatifs
    for bloc in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        assert json.loads(bloc)["@context"] == "https://schema.org"

    carte = json.loads((tmp_path / "data" / "villes.geojson").read_text())
    props = carte["features"][0]["properties"]
    assert props["slug"] == "rennes"
    assert props["axe_vie"] is None
    assert "https://explora.app/villes/saint-denis-974/" in (tmp_path / "sitemap.xml").read_text()


def test_mentions_interdites(export: ExportVilles, tmp_path: Path) -> None:
    """Le site ne doit pas reprendre les marques des organismes publics dans ses textes."""
    generer(export, RACINE / "web", tmp_path, "https://explora.app")
    for fichier in tmp_path.rglob("*"):
        if fichier.suffix in {".html", ".js", ".css", ".json", ".geojson"}:
            # Les liens vers les fiches officielles des formations sont permis.
            texte = re.sub(r"https://\S+", "", fichier.read_text()).lower()
            assert "crous" not in texte and "parcoursup" not in texte, fichier


def test_demo_est_signalee(tmp_path: Path) -> None:
    lignes = [
        {
            "code_insee": code,
            "nom": nom,
            "code_departement": dep,
            "departement": dep,
            "population": pop,
            "effectif_etudiants": eff,
            "formations": "UNIV;STS",
        }
        for code, nom, dep, pop, eff in [
            ("35238", "Rennes", "35", "230000", "72000"),
            ("22278", "Saint-Brieuc", "22", "44000", "3500"),
            ("75056", "Paris", "75", "2100000", "350000"),
        ]
    ]
    centres = {"35238": (-1.68, 48.11), "22278": (-2.76, 48.51), "75056": (2.35, 48.86)}
    export = demo.construire(lignes, centres)
    assert export.metadata.demo
    rennes = export.features[0].properties
    assert "loyer_m2" in rennes.indicateurs_demo
    assert "effectifs_etudiants" not in rennes.indicateurs_demo
    assert rennes.axes.etudes is not None
    paris = export.features[2].properties.indicateurs
    assert paris.loyer_m2 is not None and paris.loyer_m2 > 20

    ecrire(export, tmp_path / "v.geojson")
    assert charger(tmp_path / "v.geojson") == export


def test_jeu_de_demo_valide() -> None:
    export = charger(RACINE / "web" / "data" / "villes.demo.geojson")
    assert len(export.features) == 400
    assert export.metadata.demo


def test_contrat_tolere_les_champs_en_plus() -> None:
    brut = {
        "type": "FeatureCollection",
        "metadata": {"genere_le": "2026-10-26T00:00:00Z", "indicateurs_manquants": ["x"]},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 2]},
                "properties": {
                    "code_insee": "35238",
                    "nom": "Rennes",
                    "code_departement": "35",
                    "departement": "Ille-et-Vilaine",
                    "details": {"tension_methode": "locataires_meubles", "nb_residences": 12},
                    "nouveau": 1,
                },
            }
        ],
    }
    export = ExportVilles.model_validate(brut)
    assert export.features[0].properties.details.tension_methode == "locataires_meubles"
