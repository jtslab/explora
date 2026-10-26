import io
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from explora.core.models import OffreFormation
from explora.site import formations as fm
from explora.site import metiers as mt
from explora.site.donnees import ExportVilles, Metadonnees
from explora.site.generer import generer

RACINE = Path(__file__).resolve().parents[2]

XML = """<?xml version="1.0" encoding="UTF-8"?>
<FICHES>
  <FICHE>
    <NUMERO_FICHE>RNCP1</NUMERO_FICHE><INTITULE>BTS Tourisme</INTITULE>
    <ABREGE><CODE>BTS</CODE></ABREGE><ACTIF>Oui</ACTIF>
    <CODES_ROME>
      <ROME><CODE>G1201</CODE><LIBELLE>Accompagnement de voyages</LIBELLE></ROME>
      <ROME><CODE>G1303</CODE><LIBELLE>Vente de voyages</LIBELLE></ROME>
    </CODES_ROME>
  </FICHE>
  <FICHE>
    <NUMERO_FICHE>RNCP2</NUMERO_FICHE><INTITULE>BTS Tourisme</INTITULE>
    <ABREGE><CODE>BTS</CODE></ABREGE><ACTIF>Non</ACTIF>
    <CODES_ROME><ROME><CODE>G1303</CODE><LIBELLE>Vente</LIBELLE></ROME></CODES_ROME>
  </FICHE>
</FICHES>
"""


def _fiche(numero: str, intitule: str, abrege: str, *romes: str) -> mt.FicheRncp:
    return mt.FicheRncp(numero, intitule, abrege, True, [(r, "Métier " + r) for r in romes])


@pytest.fixture
def fiches() -> list[mt.FicheRncp]:
    return [
        _fiche("RNCP10", "Informatique : Réalisation d'applications", "BUT", "M1805"),
        _fiche("RNCP11", "Informatique : Déploiement d'applications", "BUT", "M1810"),
        _fiche("RNCP12", "Génie électrique et informatique industrielle", "BUT", "H1209"),
        _fiche("RNCP20", "Droit", "LICENCE", "K1903"),
        _fiche("RNCP30", "Infirmier", "DE", "J1506"),
        _fiche("RNCP40", "Audiovisuel option métiers de l'image", "BTS", "E1205"),
    ]


def test_lire_fiches() -> None:
    fiches = list(mt.lire_fiches(io.BytesIO(XML.encode())))
    assert [(f.numero, f.abrege, f.actif) for f in fiches] == [
        ("RNCP1", "BTS", True),
        ("RNCP2", "BTS", False),
    ]
    assert fiches[0].romes[1] == ("G1303", "Vente de voyages")


def test_fiche_active_preferee() -> None:
    fiches = list(mt.lire_fiches(io.BytesIO(XML.encode())))
    trouvees = mt.correspondre("BTS - Tourisme", {"BTS": fiches})
    assert [f.numero for f in trouvees] == ["RNCP1"]


def test_correspondre(fiches: list[mt.FicheRncp]) -> None:
    index = {}
    for f in fiches:
        index.setdefault(f.abrege, []).append(f)

    def numeros(mention: str) -> list[str]:
        return [f.numero for f in mt.correspondre(mention, index)]

    # Les parcours du BUT sont réunis, sans le GEII qui contient aussi « informatique ».
    assert numeros("BUT - Informatique") == ["RNCP10", "RNCP11"]
    assert numeros("L1 - Droits") == ["RNCP20"]  # pluriel
    assert numeros("D.E Infirmier") == ["RNCP30"]
    assert numeros("BTS - Audio-visuel - Option métiers de l'image") == ["RNCP40"]
    assert numeros("BTS - Métiers de la chimie") == []
    assert numeros("CPGE - MPSI") == []  # filière généraliste, pas de fiche
    assert numeros("Sans préfixe") == []


def test_construire(fiches: list[mt.FicheRncp]) -> None:
    index = mt.construire(["BUT - Informatique", "L1 - Droit", "CPGE - MPSI"], fiches, "rncp.zip")
    assert index.mentions["BUT - Informatique"].romes == ["M1805", "M1810"]
    assert "CPGE - MPSI" not in index.mentions
    assert index.metiers["K1903"] == "Métier K1903"
    assert index.domaines == {"K": mt.DOMAINES_ROME["K"], "M": mt.DOMAINES_ROME["M"]}


def test_generer_avec_metiers(fiches: list[mt.FicheRncp], tmp_path: Path) -> None:
    from tests.site.test_site import _ville

    export = ExportVilles(
        metadata=Metadonnees(genere_le=datetime(2026, 10, 26, tzinfo=UTC)),
        features=[_ville("35238", "Rennes", "35", -1.68, 48.11, 70)],
    )
    offre = OffreFormation(
        session="2026",
        code="1",
        code_uai="A",
        etablissement="IUT de Rennes",
        types=["BUT"],
        mentions=["BUT - Informatique"],
        commune="Rennes",
        departement="Ille-et-Vilaine",
    )
    villes = [{"code_insee": "35238", "nom": "Rennes", "departement": "Ille-et-Vilaine"}]
    formations = fm.construire([offre], villes)
    metiers = mt.construire(["BUT - Informatique"], fiches, "rncp.zip")

    generer(export, RACINE / "web", tmp_path, "https://explora.app", formations, metiers)
    index = json.loads((tmp_path / "data" / "formations-index.json").read_text())
    assert index["metiers"] == [["M1805", "Métier M1805", [0]], ["M1810", "Métier M1810", [0]]]
    assert index["secteurs"] == [["M", mt.DOMAINES_ROME["M"]]]
    html = (tmp_path / "villes" / "rennes" / "index.html").read_text()
    assert "Métier M1805" in html
