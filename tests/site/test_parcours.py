import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from explora.site import formations as fm
from explora.site import parcours as pc
from explora.site.donnees import ExportVilles, Metadonnees
from explora.site.generer import bac_plus, bacs, formations_par_type, generer
from tests.site.test_insertion import RACINE, RENNES, _offre
from tests.site.test_site import _ville


@pytest.mark.parametrize(
    ("type_", "libelle", "attendu"),
    [
        ("BTS - BTSA - BTSM", "BTS - Tourisme", ("bts", 2)),
        ("BTS - BTSA - BTSM", "BTSA - Aquaculture", ("bts", 2)),
        ("BUT", "BUT - Informatique", ("but", 3)),
        ("Licence", "L1 - Droit", ("licence", 3)),
        ("Licence sélective", "L1 - Droit, Economie", ("licence-renforcee", 3)),
        ("Etudes de santé", "L1 - Parcours d'Accès Spécifique Santé (PASS)", ("pass", 5)),
        ("Etudes de santé", "L1 - Lettres", ("las", 3)),
        ("Etudes de santé", "D.E Infirmier", ("paramedical", 3)),
        ("Etudes de santé", "Certificat de capacité d'Orthophoniste", ("paramedical", 5)),
        ("Formations diplômantes du travail social", "D.E Educateur Spécialisé", ("social", 3)),
        ("CPGE", "CPGE - MPSI", ("cpge", 5)),
        ("Formations des écoles d'ingénieurs", "Formation Bac + 3", ("ingenieur", 3)),
        ("Formations des écoles d'ingénieurs", "Formation d'ingénieur Bac + 5", ("ingenieur", 5)),
        (
            "Formations des écoles de commerce et de management",
            "Formation des écoles de commerce et de management Bac + 4",
            ("commerce", 4),
        ),
        ("Formations des écoles vétérinaires", "Véto - Formation Bac+6", ("veterinaire", 6)),
        ("Formations professionnelles", "FP - Gestionnaire de Paie (Bac +2)", ("ecole-pro", 2)),
        ("Formations professionnelles", "FP - Aumônerie protestante", ("ecole-pro", None)),
        (
            "Certificats de spécialisation et FCIL",
            "CSA - Arboriste-grimpeur",
            ("specialisation", 1),
        ),
        ("Formations aux métiers du sport", "BPJEPS - Spécialité Animateur", ("sport", 1)),
        (
            "Sciences Po - Instituts d'études politiques",
            "Sciences Po / Instituts d'études politiques - Sciences Humaines et Sociales - "
            "Grade Master",
            ("iep", 5),
        ),
    ],
)
def test_classer(type_: str, libelle: str, attendu: tuple[str, int | None]) -> None:
    assert pc.classer(type_, libelle) == attendu
    assert attendu[0] in pc.FAMILLES


def _spe(groupe: str, niveau: str, formation: str, doublette: list[str], n: int) -> dict:
    return {
        "regroupement_de_formations_abrege": groupe,
        "niveau_d_agregation": niveau,
        "formation": formation,
        "doublette": doublette,
        "acceptations": n,
    }


MATHS_PC = ["Mathématiques Spécialité", "Physique-Chimie Spécialité"]
SES_HGGSP = [
    "Sciences Economiques et Sociales Spécialité",
    "Histoire-Géographie, Géopolitique et Sciences politiques",
]
SPECIALITES = [
    _spe("BTS serv", "2", "Tourisme", SES_HGGSP, 30),
    _spe("BTS serv", "2", "Tourisme", MATHS_PC, 10),
    _spe("Licence Sciences juridiques", "1", "Licence Sciences juridiques", SES_HGGSP, 80),
    _spe("Licence Sciences juridiques", "2", "Licence Sciences juridiques", SES_HGGSP, 80),
    _spe("CPGE S", "2", "MPSI", MATHS_PC, 50),
    _spe("Ensemble", "0", "Ensemble", MATHS_PC, 9999),
]


def test_formation_specialites() -> None:
    cles = pc._cumuls_specialites(SPECIALITES)
    assert pc.formation_specialites("bts", "BTS - Tourisme", cles) == ("BTS serv", "Tourisme")
    assert pc.formation_specialites("licence", "L1 - Droit", cles) == (
        "Licence Sciences juridiques",
        "Licence Sciences juridiques",
    )
    assert pc.formation_specialites("cpge", "CPGE - MPSI", cles) == ("CPGE S", "MPSI")
    assert pc.formation_specialites("cpge", "CPGE - PCSI", cles) is None
    # Le niveau 1 d'une licence ne compte qu'une fois, le niveau 2 identique est ignoré.
    assert cles[("Licence Sciences juridiques", "Licence Sciences juridiques")].total == 80


def _index() -> fm.IndexFormations:
    return fm.construire(
        [
            _offre("1", "LYC", "BTS - BTSA - BTSM", "BTS - Tourisme"),
            _offre("2", "UNIV", "Licence", "L1 - Droit"),
            _offre("3", "LYC", "CPGE", "CPGE - MPSI"),
        ],
        RENNES,
    )


VOEUX = [
    {
        "cod_aff_form": "1",
        "select_form": "formation sélective",
        "acc_bg": 6,
        "acc_bt": 12,
        "acc_bp": 12,
        "taux_acces_ens": 64.0,
    },
    {
        "cod_aff_form": "2",
        "select_form": "formation non sélective",
        "acc_bg": 90,
        "acc_bt": 8,
        "acc_bp": 2,
        "taux_acces_ens": 95,
    },
    {
        "cod_aff_form": "3",
        "select_form": "formation sélective",
        "acc_bg": 5,
        "acc_bt": 0,
        "acc_bp": 0,
        "taux_acces_ens": 30,
        "detail_forma2": None,
    },
]


def test_construire() -> None:
    index = pc.construire(_index(), VOEUX, SPECIALITES, "2025")
    bts = index.mentions["BTS - Tourisme"]
    assert (bts.famille, bts.sortie, bts.acces) == ("bts", 2, "dossier")
    assert bts.profil and bts.profil.bacs == (20, 40, 40)
    assert bts.specialites and bts.specialites.doublettes[0] == ("SES + HGGSP", 75)
    droit = index.mentions["L1 - Droit"]
    assert droit.acces == "libre"
    mpsi = index.mentions["CPGE - MPSI"]
    assert mpsi.profil is None  # moins de 20 admis
    assert mpsi.specialites and mpsi.specialites.doublettes == [("Maths + Physique-chimie", 100)]
    assert index.offres["1"] == pc.OffreAcces(taux=64, selective=True)
    assert index.offres["2"].selective is False
    assert index.familles["licence"].bacs == (90, 8, 2)


def test_formats() -> None:
    assert bac_plus(3) == "Bac+3"
    assert bac_plus(1) == "1 an"
    assert bac_plus(None) == "Niveau variable"
    assert bacs((100, 0, 0)) == "100\u00a0% bac général"
    assert bacs((20, 40, 40), long=True).endswith("40\u00a0% professionnels")


def test_site(tmp_path: Path) -> None:
    formations = _index()
    parcours = pc.construire(formations, VOEUX, SPECIALITES, "2025")
    groupes = dict(formations_par_type(formations, "35238", parcours=parcours))
    [tourisme] = groupes["BTS - BTSA - BTSM"]
    assert tourisme.parcours and tourisme.parcours.sortie == 2
    assert tourisme.offres[0].acces and tourisme.offres[0].acces.taux == 64

    export = ExportVilles(
        metadata=Metadonnees(genere_le=datetime(2026, 10, 26, tzinfo=UTC)),
        features=[_ville("35238", "Rennes", "35", -1.68, 48.11, 70)],
    )
    pages = generer(
        export, RACINE / "web", tmp_path, "https://explora.app", formations, parcours=parcours
    )
    assert tmp_path / "parcours" / "index.html" in pages
    ville = (tmp_path / "villes" / "rennes" / "index.html").read_text()
    assert 'data-sortie="2"' in ville and "taux d'accès 64" in ville
    assert 'href="../../parcours/#bts"' in ville
    assert "SES + HGGSP (75" in ville
    page = (tmp_path / "parcours" / "index.html").read_text()
    for famille in pc.FAMILLES.values():
        assert famille.titre.replace("'", "&#39;") in page
    assert "/parcours/</loc>" in (tmp_path / "sitemap.xml").read_text()
    index = json.loads((tmp_path / "data" / "formations-index.json").read_text())
    assert index["familles"]["bts"][2] == []
    mentions = {m[0]: m for m in index["mentions"]}
    assert mentions["BTS - Tourisme"][3:6] == ["bts", 2, "dossier"]
