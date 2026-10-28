from datetime import UTC, datetime
from pathlib import Path

from explora.site import voie_pro as vp
from explora.site.donnees import ExportVilles, Metadonnees
from explora.site.generer import formations_par_type, generer
from tests.site.test_insertion import RACINE
from tests.site.test_parcours import _index
from tests.site.test_site import _ville

VILLES = [
    {"code_insee": "35238", "nom": "Rennes", "departement": "Ille-et-Vilaine"},
    {"code_insee": "75056", "nom": "Paris", "departement": "Paris"},
    {"code_insee": "47001", "nom": "Agen", "departement": "Lot-et-Garonne"},
]
ANNUAIRE = [
    {
        "identifiant_de_l_etablissement": "0350001A",
        "nom_etablissement": "Lycée professionnel Coëtlogon",
        "code_commune": "35238",
        "statut_public_prive": "Public",
    },
    {
        "identifiant_de_l_etablissement": "0750001B",
        "nom_etablissement": "Lycée des métiers",
        "code_commune": "75114",
        "statut_public_prive": "Privé",
    },
]


def _ligne(uai: str, type_: str, libelle: str, annee: str = "cumul 2023-2024", **autres: object):
    return {
        "annee": annee,
        "uai": uai,
        "libelle": autres.pop("nom", "Lycée"),
        "type_diplome": type_,
        "libelle_formation": libelle,
        **autres,
    }


LYCEES = [
    _ligne("0350001A", "CAP", "boulanger", taux_emploi_12_mois=80.0, taux_poursuite_etudes=44.0),
    _ligne("0350001A", "BAC PRO", "cuisine"),
    _ligne("0350001A", "CAP", "boulanger", annee="cumul 2022-2023"),  # cohorte ancienne
    _ligne("0750001B", "BP", "coiffure"),  # arrondissement de Paris
    _ligne("0350001A", "BTS", "tourisme"),  # hors voie pro
]
CFA = [
    _ligne("0479999Z", "CAP", "maçon", nom="CFA du BTP du Lot-et-Garonne de Agen"),
    _ligne("0359999Y", "MC3", "boulangerie specialisee", nom="CFA inconnu"),
]


def test_construire() -> None:
    index = vp.construire(LYCEES, CFA, ANNUAIRE, VILLES)
    assert index.annee == "cumul 2023-2024"
    f = index.formations
    assert f.types == ["CAP", "Bac professionnel", "Brevet professionnel"]
    libelles = [m.libelle for m in f.mentions]
    assert libelles == ["Bac pro - Cuisine", "BP - Coiffure", "CAP - Boulanger", "CAP - Maçon"]
    assert sorted(f.offres) == ["35238", "47001", "75056"]
    [macon] = f.offres["47001"]
    assert macon.apprentissage and macon.code.startswith(vp.PREFIXE_CODE)
    boulanger = next(o for o in f.offres["35238"] if libelles[o.mention] == "CAP - Boulanger")
    assert index.insertion[boulanger.code].emploi == 80
    assert f.etablissements["0350001A"].secteur == "Publics"


def test_site(tmp_path: Path) -> None:
    voie = vp.construire(LYCEES, CFA, ANNUAIRE, VILLES)
    formations = vp.fusionner(_index(), voie.formations)
    avant = _index()
    assert formations.mentions[: len(avant.mentions)] == avant.mentions
    groupes = dict(formations_par_type(formations, "35238"))
    [cap] = groupes["CAP"]
    assert cap.depart == "Après la 3e" and cap.offres[0].urls == () and cap.offres[0].nb == 1
    assert groupes["BTS - BTSA - BTSM"][0].offres[0].urls  # fiche post-bac conservée

    export = ExportVilles(
        metadata=Metadonnees(genere_le=datetime(2026, 10, 26, tzinfo=UTC)),
        features=[_ville("35238", "Rennes", "35", -1.68, 48.11, 70)],
    )
    generer(export, RACINE / "web", tmp_path, "https://explora.app", formations)
    page = (tmp_path / "villes" / "rennes" / "index.html").read_text()
    assert "CAP - Boulanger" in page and "Après la 3e" in page and "InserJeunes" in page
