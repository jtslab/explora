import json
from collections import Counter
from contextlib import AsyncExitStack
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from explora.adapters import (
    Dv3fAdapter,
    GeoApiAdapter,
    GeorisquesAdapter,
    InseeMelodiAdapter,
    LoyersAdapter,
    ResidencesEtudiantesAdapter,
    VoeuxFormationsAdapter,
)
from explora.core.http import RetryPolicy, SourceClient
from explora.core.models import (
    FormationVoeux,
    LogementsCommune,
    LoyerCommune,
    PrixImmobilierCommune,
    ResidenceEtudiante,
    RisqueCommune,
)
from explora.modules.etudiant.ingestion import (
    Collecte,
    IndexCommunes,
    Sources,
    Ville,
    calculer_indicateurs,
    collecter,
    construire_geojson,
    ecrire_geojson,
    lire_villes,
    normaliser_nom,
    rattacher_formations,
    tension,
)
from explora.modules.etudiant.scoring import INDICATEURS
from tests.conftest import fixture_bytes, fixture_json


def ville(
    code: str = "35238",
    nom: str = "Rennes",
    dep: str = "35",
    population: int | None = 200_000,
    effectif: int = 60_000,
) -> Ville:
    return Ville(
        code_insee=code,
        nom=nom,
        code_departement=dep,
        departement=f"Dép. {dep}",
        population=population,
        effectif_etudiants=effectif,
        formations=("STS", "UNIV"),
    )


def residence(places: int | None, adresse: str = "1 rue X - 35000 Rennes") -> ResidenceEtudiante:
    return ResidenceEtudiante(id="1", nom="R", adresse=adresse, places_estimees=places)


def formation(ville: str, dep: str, uai: str = "0350001A", filiere: str = "BTS") -> FormationVoeux:
    return FormationVoeux(
        session="2025",
        code_uai=uai,
        etablissement="E",
        ville=ville,
        code_departement=dep,
        filiere=filiere,
        formation="F",
    )


LOGEMENTS = LogementsCommune(
    code_insee="35238", annee="2023", residences_principales=100_000, locataires_meubles=12_000
)


def test_lire_villes_du_depot() -> None:
    villes = lire_villes(Path("data/villes_etudiantes.csv"))
    assert len(villes) == 400
    assert villes[0].code_insee == "01053"
    assert villes[0].formations == ("CPGE", "EC_COM", "EC_PARAM", "STS", "UNIV")


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("Saint-Martin-d'Hères", "saint martin d heres"),
        ("Saint-Martin-d\u2019Hères", "saint martin d heres"),
        ("St-Étienne", "saint etienne"),
        ("Paris  5e  Arrondissement", "paris"),
        ("Marseille 1er Arrondissement", "marseille"),
        ("Ste-Clotilde", "sainte clotilde"),
        ("Vand\u0153uvre-lès-Nancy", "vandoeuvre les nancy"),
    ],
)
def test_normaliser_nom(brut: str, attendu: str) -> None:
    assert normaliser_nom(brut) == attendu


def test_rattacher_formations_par_libelle_et_departement() -> None:
    villes = [ville(), ville("75056", "Paris", "75"), ville("97411", "Saint-Denis", "974")]
    rattachees = rattacher_formations(
        [
            formation("Rennes", "35"),
            formation("Paris  5e  Arrondissement", "75"),
            formation("Saint-Denis", "93"),  # homonyme hors sélection
            formation("Saint-Denis", "974"),
            formation("Brest", "29"),
        ],
        villes,
    )
    assert {code: len(f) for code, f in rattachees.items()} == {
        "35238": 1,
        "75056": 1,
        "97411": 1,
    }


def test_index_par_adresse() -> None:
    index = IndexCommunes(
        [
            ville("38421", "Saint-Martin-d'Hères", "38"),
            ville("93066", "Saint-Denis", "93"),
            ville("97411", "Saint-Denis", "974"),
        ]
    )
    assert index.par_adresse("107 rue des Taillées - 38400  Saint-Martin-d'Hères") == "38421"
    assert index.par_adresse("1 av. X - 97400 Saint-Denis") == "97411"
    assert index.par_adresse("1 av. X - 93200 Saint-Denis") == "93066"
    assert index.par_adresse("12 chemin de Bellevue - 74940 Annecy-le-Vieux") is None
    assert index.par_adresse(None) is None


def test_tension_sur_les_places_quand_toutes_les_residences_sont_connues() -> None:
    t = tension(1_000, [residence(100), residence(150)], LOGEMENTS)
    assert t.methode == "places_residences"
    assert t.valeur == 4.0
    assert t.places_residences == 250
    assert t.par_meuble == pytest.approx(1_000 / 12_000)


def test_tension_sur_les_meubles_sinon() -> None:
    t = tension(1_200, [residence(100), residence(None)], LOGEMENTS)
    assert t.methode == "locataires_meubles"
    assert t.valeur == t.par_meuble == pytest.approx(0.1)
    assert t.places_residences == 100  # minorant, affiché à titre d'information
    assert tension(1_200, [], LOGEMENTS).methode == "locataires_meubles"
    assert tension(1_200, None, None) == tension(1_200, [], None)
    assert tension(1_200, None, None).methode is None


def collecte_rennes() -> Collecte:
    return Collecte(
        ville=ville(),
        loyer=LoyerCommune(code_insee="35238", nom="Rennes", typologie="t1t2", loyer_m2=15.0),
        prix=PrixImmobilierCommune(
            code_insee="35238", annee="2025", typologie="t1", prix_m2=4500, nb_transactions=400
        ),
        risques=RisqueCommune(code_insee="35238", risques=["Inondation", "Séisme"]),
        logements=LOGEMENTS,
        equipements={"B105": 10, "B201": 30, "A504": 160, "A101": 99, "F101": 40, "F303": 10},
        residences=[residence(1_000)],
        formations=[
            formation("Rennes", "35", "A"),
            formation("Rennes", "35", "A", "BUT"),
            formation("Rennes", "35", "B"),
        ],
    )


def test_indicateurs() -> None:
    ind = calculer_indicateurs(collecte_rennes())
    v = ind.valeurs
    assert set(v) == {i.id for i in INDICATEURS} | {"rendement_brut"}
    assert v["nb_etablissements"] == 2
    assert v["nb_filieres"] == 2
    assert v["rendement_brut"] == pytest.approx(15 * 12 / 4500)
    assert v["commerces_pour_1000"] == pytest.approx(200 * 1000 / 200_000)
    assert v["equipements_culture_sport_pour_1000"] == pytest.approx(50 * 1000 / 200_000)
    assert v["nb_risques"] == 2
    assert v["tension_locative"] == 60.0  # affichée : étudiants par place en résidence
    assert ind.pour_score["tension_locative"] == 5.0  # score : étudiants par meublé
    assert v["vitalite_commerciale"] is None
    assert "rendement_brut" not in ind.pour_score


def test_indicateurs_sources_en_panne() -> None:
    v = calculer_indicateurs(Collecte(ville=ville(population=None))).valeurs
    assert v["effectifs_etudiants"] == 60_000
    assert all(x is None for k, x in v.items() if k != "effectifs_etudiants")


def test_geojson_au_format_du_front(tmp_path: Path) -> None:
    autre = Collecte(ville=ville("35047", "Bruz", population=19_000, effectif=1_000))
    geojson = construire_geojson(
        [collecte_rennes(), autre],
        genere_le=datetime(2026, 10, 26, tzinfo=UTC),
        erreurs=Counter({"dv3f": 2}),
    )
    meta = geojson["metadata"]
    assert meta["genere_le"] == "2026-10-26T00:00:00+00:00"
    assert (meta["demo"], meta["version"], meta["nb_villes"]) == (False, 1, 2)
    assert meta["erreurs_par_source"] == {"dv3f": 2}
    assert {s["id"] for s in meta["sources"]} >= {"dv3f", "carte-loyers", "insee-melodi"}
    rennes, bruz = (f["properties"] for f in geojson["features"])
    assert set(rennes["axes"]) == {"etudes", "budget", "vie", "mobilite_cadre"}
    assert rennes["axes"]["etudes"] == 66.7  # seule à avoir des formations : rang médian
    assert bruz["axes"]["budget"] is None
    assert bruz["couverture"] == 0.25
    assert rennes["risques"] == ["Inondation", "Séisme"]
    assert rennes["indicateurs_demo"] == []
    assert rennes["details"]["tension_methode"] == "places_residences"
    assert rennes["indicateurs"]["rendement_brut"] == 0.04
    assert geojson["features"][1]["geometry"] is None

    chemin = tmp_path / "export" / "villes.geojson"
    ecrire_geojson(geojson, chemin)
    assert json.loads(chemin.read_text(encoding="utf-8")) == geojson


# --- Collecte complète, toutes les sources simulées ------------------------------------

SMH = ville("38421", "Saint-Martin-d'Hères", "38", population=38_000, effectif=30_000)
VILLES = [ville(), SMH]


def _geo(request: httpx.Request) -> httpx.Response:
    if "lat" in request.url.params:  # résidence d'Annecy-le-Vieux : commune déléguée
        return httpx.Response(200, json=[{"code": "74010"}])
    autres = [
        {"code": "38421", "nom": "Saint-Martin-d'Hères", "codeDepartement": "38"},
        {"code": "74010", "nom": "Annecy", "codeDepartement": "74"},
        {"code": "73065", "nom": "Chambéry", "codeDepartement": "73"},
    ]
    return httpx.Response(200, json=[fixture_json("geo_api_commune_35238.json"), *autres])


def _flux(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/feed/grenoble/grenoble-logement.xml":
        return httpx.Response(200, content=fixture_bytes("residences_grenoble_extrait.xml"))
    if request.url.path == "/feed/rennes/rennes-logement.xml":
        return httpx.Response(404)
    return httpx.Response(200, text="<root/>")


def _voeux(request: httpx.Request) -> httpx.Response:
    if request.url.params["where"] == 'dep="38"':
        page = fixture_json("parcoursup_voeux_38_extrait.json")
        return httpx.Response(200, json={**page, "total_count": len(page["results"])})
    return httpx.Response(200, json={"total_count": 0, "results": []})


def _mock_sources() -> None:
    respx.get("https://geo.test/communes").mock(side_effect=_geo)
    respx.get("https://loyers.test/r/t1t2").respond(
        content=fixture_bytes("loyers_app12_extrait.csv")
    )
    respx.get("https://dv3f.test/indicateurs/dv3f/prix/annuel/").respond(
        json=fixture_json("dv3f_prix_35238_extrait.json")
    )
    respx.get("https://georisques.test/gaspar/risques").respond(
        json=fixture_json("georisques_risques_35238.json")
    )
    respx.get("https://insee.test/data/DS_RP_LOGEMENT_PRINC").respond(
        json=fixture_json("melodi_rp_logement_38185.json")
    )
    respx.get("https://insee.test/data/DS_BPE").respond(
        json=fixture_json("melodi_bpe_38185_extrait.json")
    )
    respx.get(url__regex=r"https://crous\.test/feed/.*").mock(side_effect=_flux)
    respx.get("https://voeux.test/catalog/datasets/fr-esr-parcoursup/records").mock(
        side_effect=_voeux
    )


async def _sources(stack: AsyncExitStack) -> Sources:
    async def no_sleep(_: float) -> None:
        return None

    async def client(base_url: str) -> SourceClient:
        return await stack.enter_async_context(
            SourceClient("test", base_url, retry=RetryPolicy(max_attempts=1), sleep=no_sleep)
        )

    return Sources(
        geo=GeoApiAdapter(await client("https://geo.test")),
        loyers=LoyersAdapter(await client("https://loyers.test")),
        dv3f=Dv3fAdapter(await client("https://dv3f.test")),
        georisques=GeorisquesAdapter(await client("https://georisques.test")),
        melodi=InseeMelodiAdapter(await client("https://insee.test")),
        residences=ResidencesEtudiantesAdapter(await client("https://crous.test")),
        voeux=VoeuxFormationsAdapter(await client("https://voeux.test")),
    )


@respx.mock
async def test_collecte_complete() -> None:
    _mock_sources()
    async with AsyncExitStack() as stack:
        sources = await _sources(stack)
        rennes, smh = await collecter(VILLES, sources, loyers_ressource="/r/t1t2")

    assert sources.erreurs == Counter({"residences-etudiantes": 1})
    assert rennes.centre is not None and rennes.centre.lat == 48.1159
    assert smh.centre is None
    assert rennes.loyer is not None and rennes.loyer.fiable
    assert smh.loyer is None
    assert rennes.prix is not None and rennes.prix.typologie == "t1"
    assert rennes.risques is not None and rennes.risques.risques
    assert rennes.logements is not None and rennes.equipements
    # Saint-Martin-d'Hères et Chambéry trouvées par l'adresse, Annecy-le-Vieux (commune
    # déléguée) par les coordonnées ; seules les deux premières sont dans la sélection.
    assert rennes.residences == []
    assert smh.residences is not None and len(smh.residences) == 2
    assert smh.formations is not None and len(smh.formations) == 3
    assert rennes.formations == []
    assert all(route.called for route in respx.routes)
    assert respx.calls.call_count == 1 + 1 + 1 + 26 + 2 + 2 * 4  # geo, point, loyers...


@respx.mock
async def test_collecte_sources_en_panne() -> None:
    respx.route().respond(503)
    async with AsyncExitStack() as stack:
        sources = await _sources(stack)
        collectes = await collecter(VILLES, sources, loyers_ressource="/r/t1t2")
    assert all(c.residences is None and c.formations is None for c in collectes)
    assert all(c.prix is None and c.logements is None for c in collectes)
    assert sources.erreurs["insee-melodi"] == 4
    geojson = construire_geojson(collectes, genere_le=datetime.now(UTC), erreurs=sources.erreurs)
    assert [f["properties"]["axes"]["etudes"] for f in geojson["features"]] == [100.0, 0.0]
