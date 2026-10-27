import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from explora.site import formations as fm
from explora.site import metiers_cibles as mc
from explora.site import parcours as pc
from explora.site.donnees import ExportVilles, Metadonnees
from explora.site.generer import generer
from tests.site.test_insertion import RACINE
from tests.site.test_parcours import SPECIALITES, VOEUX, _index
from tests.site.test_site import _ville

FORMATIONS = RACINE / "web" / "data" / "formations.json"
PARCOURS = RACINE / "web" / "data" / "parcours.json"


def test_metiers_uniques() -> None:
    ids = [m.id for m in mc.METIERS]
    assert len(ids) == len(set(ids))
    for m in mc.METIERS:
        assert m.voies and m.lycee
        assert all(v.etapes for v in m.voies)


def test_resoudre() -> None:
    libelles = ["L1 - Droit", "CPGE - ECG - Maths", "CPGE - ECG - Histoire", "L1 - Lettres"]
    familles = {"L1 - Lettres": "las"}
    assert mc.resoudre("L1 - Droit", libelles, familles) == [0]
    assert mc.resoudre("CPGE - ECG*", libelles, familles) == [1, 2]
    assert mc.resoudre("famille:las", libelles, familles) == [3]
    assert mc.resoudre("L1 - Dro", libelles, familles) == []


@pytest.mark.skipif(not FORMATIONS.exists() or not PARCOURS.exists(), reason="données absentes")
def test_formations_citees_existent() -> None:
    """Chaque formation citée dans un chemin désigne au moins une mention réelle."""
    index = fm.charger(FORMATIONS)
    parcours = pc.charger(PARCOURS)
    libelles = [m.libelle for m in index.mentions if m.libelle in parcours.mentions]
    familles = {lib: parcours.mentions[lib].famille for lib in libelles}
    manquantes = [
        (m.id, motif)
        for m in mc.METIERS
        for v in m.voies
        for e in v.etapes
        for motif in e.formations
        if not mc.resoudre(motif, libelles, familles)
    ]
    assert manquantes == []


def test_site(tmp_path: Path) -> None:
    formations = _index()
    parcours = pc.construire(formations, VOEUX, SPECIALITES, "2025")
    export = ExportVilles(
        metadata=Metadonnees(genere_le=datetime(2026, 10, 26, tzinfo=UTC)),
        features=[_ville("35238", "Rennes", "35", -1.68, 48.11, 70)],
    )
    generer(export, RACINE / "web", tmp_path, "https://explora.app", formations, parcours=parcours)
    page = (tmp_path / "parcours" / "index.html").read_text()
    assert 'id="metier-recherche"' in page and "assets/metier.js" in page
    cibles = json.loads((tmp_path / "data" / "metiers-cibles.json").read_text())
    arbre = json.loads((tmp_path / "data" / "parcours-arbre.json").read_text())
    assert [c["id"] for c in cibles["cibles"]] == [m.id for m in mc.METIERS]
    avocat = cibles["cibles"][0]
    licence = avocat["voies"][0]["etapes"][0]
    assert [arbre["mentions"][i][0] for i in licence[3]] == ["L1 - Droit"]
    assert cibles["metiers"] == []
