from datetime import UTC, datetime
from pathlib import Path

from explora.core.models import OffreFormation
from explora.site import formations as fm
from explora.site import insertion as ins
from explora.site.donnees import ExportVilles, Metadonnees
from explora.site.generer import devenir, formations_par_type, generer
from tests.site.test_site import _ville

RACINE = Path(__file__).resolve().parents[2]
RENNES = [{"code_insee": "35238", "nom": "Rennes", "departement": "Ille-et-Vilaine"}]


def _offre(code: str, uai: str, type_: str, mention: str) -> OffreFormation:
    return OffreFormation(
        session="2026",
        code=code,
        code_uai=uai,
        etablissement=f"Établissement {uai}",
        secteur="Publics",
        types=[type_],
        mentions=[mention],
        commune="Rennes",
        departement="Ille-et-Vilaine",
    )


def _sup(
    etab: str, type_: str, libelle: str, promo: str, emploi: str, salaire: str = "nd"
) -> dict[str, object]:
    return {
        "etablissement": etab,
        "type_diplome_long": type_,
        "libelle_diplome": libelle,
        "promo": [promo],
        "nb_sortants_12": 20,
        "nb_poursuivants_12": "180",
        "tx_sortants_en_emploi_sal_fr_12": emploi,
        "salaire_q2_12": salaire,
    }


def _index() -> fm.IndexFormations:
    offres = [
        _offre(
            "1",
            "LYC",
            "BTS - BTSA - BTSM",
            "BTS - Fluide, énergie, domotique - option A génie climatique et fluidique",
        ),
        _offre("2", "UNIV", "Licence", "L1 - Droit"),
        _offre("3", "UNIV", "Licence", "L1 - Chimie"),
        _offre("4", "ECOLE", "Formations des écoles d'ingénieurs", "Formation d'ingénieur Bac + 5"),
        _offre("5", "UNIV", "Licence", "L1 - Philosophie"),
    ]
    return fm.construire(offres, RENNES)


def test_meme_intitule() -> None:
    assert ins.meme_intitule(
        "Fluide, énergie, domotique - option A génie climatique et fluidique",
        "fluides-energies-domotique option a genie climatique et fluidique",
    )
    assert ins.meme_intitule("Droit", "DROIT")
    assert not ins.meme_intitule("Droit", "ECONOMIE")


def test_ligne_insersup() -> None:
    ligne = ins.ligne_insersup(_sup("U", "Licence générale", "DROIT", "2022", "41.5", "1660"))
    assert ligne == ins.Insertion(
        emploi=42, salaire=1660, poursuite=90, promo="2022", source="insersup"
    )
    assert ins.ligne_insersup(_sup("U", "Licence générale", "DROIT", "2022", "nd")) is None


def test_construire() -> None:
    insersup = [
        _sup("UNIV", "Licence générale", "DROIT", "2021", "60", "1500"),
        _sup("UNIV", "Licence générale", "DROIT", "2023", "70"),  # plus récente, sans salaire
        _sup(ins.NATIONAL, "Licence générale", "CHIMIE", "2022", "54", "1850"),
        _sup("ECOLE", "Diplôme d'ingénieurs", "INGENIEUR DIPLOME DE L'ECOLE", "2022", "88", "2600"),
    ]
    inserjeunes = [
        {
            "annee": "cumul 2023-2024",
            "uai": "LYC",
            "libelle_formation": (
                "fluides-energies-domotique option a genie climatique et fluidique"
            ),
            "taux_poursuite_etudes": 19.0,
            "taux_emploi_12_mois": 76.0,
        }
    ]
    offres = ins.construire(_index(), insersup, inserjeunes).offres
    assert offres["1"] == ins.Insertion(
        emploi=76, poursuite=19, promo="2023-2024", source="inserjeunes"
    )
    assert offres["2"].salaire == 1500  # promotion avec salaire préférée
    assert offres["3"].national and offres["3"].emploi == 54
    assert offres["4"].salaire == 2600
    assert "5" not in offres


def test_devenir() -> None:
    texte = devenir(ins.Insertion(emploi=54, salaire=1850, poursuite=89, source="insersup"))
    assert texte.startswith("89")
    assert "parmi les autres, 54" in texte and "1" in texte and "net par mois" in texte


def test_formations_regroupees(tmp_path: Path) -> None:
    offres = [
        _offre("10", "A", "BTS - BTSA - BTSM", "BTS - Tourisme"),
        _offre("11", "B", "BTS - BTSA - BTSM", "BTS - Tourisme"),
        _offre("12", "B", "BTS - BTSA - BTSM", "BTS - Tourisme"),  # second parcours
    ]
    index = fm.construire(offres, RENNES)
    chiffres = ins.IndexInsertion(
        genere_le=datetime(2026, 10, 26, tzinfo=UTC),
        offres={"10": ins.Insertion(emploi=80, source="inserjeunes")},
    )
    [(_, [tourisme])] = formations_par_type(index, "35238", insertion=chiffres)
    assert [o.etablissement for o in tourisme.offres] == ["Établissement A", "Établissement B"]
    assert len(tourisme.offres[1].urls) == 2
    assert tourisme.offres[0].insertion and tourisme.offres[0].insertion.emploi == 80

    export = ExportVilles(
        metadata=Metadonnees(genere_le=datetime(2026, 10, 26, tzinfo=UTC)),
        features=[_ville("35238", "Rennes", "35", -1.68, 48.11, 70)],
    )
    generer(export, RACINE / "web", tmp_path, "https://explora.app", index, insertion=chiffres)
    html = (tmp_path / "villes" / "rennes" / "index.html").read_text()
    assert html.count('class="mention">BTS - Tourisme<') == 1
    assert "3 formations après le bac à Rennes" in html
    assert "2 parcours" in html
    assert "80" in html and "en emploi à 12 mois" in html
