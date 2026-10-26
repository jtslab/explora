import pytest

from explora.modules.etudiant.scoring import Axe, rang_centile, scorer


def test_rang_centile() -> None:
    pop = [1.0, 2.0, 3.0]
    assert rang_centile(1.0, pop) == 0
    assert rang_centile(3.0, pop) == 100
    assert rang_centile(2.0, [2.0, 2.0]) == 50
    assert rang_centile(5.0, [5.0]) == 50


def test_sens_des_indicateurs() -> None:
    scores = scorer(
        {
            "a": {"loyer_m2": 10.0, "effectifs_etudiants": 50000},
            "b": {"loyer_m2": 20.0, "effectifs_etudiants": 1000},
        }
    )
    assert scores["a"].axes[Axe.BUDGET] == 100
    assert scores["a"].axes[Axe.ETUDES] == 100
    assert scores["b"].global_ == 0


def test_poids_et_couverture() -> None:
    villes = {
        "a": {"loyer_m2": 10.0, "effectifs_etudiants": 1000},
        "b": {"loyer_m2": 20.0, "effectifs_etudiants": 50000},
    }
    budget_seul = scorer(villes, {Axe.BUDGET: 1, Axe.ETUDES: 0, Axe.VIE: 0, Axe.MOBILITE_CADRE: 0})
    assert budget_seul["a"].global_ == 100
    assert budget_seul["a"].couverture == 1
    egal = scorer(villes)
    assert egal["a"].global_ == 50
    assert egal["a"].couverture == pytest.approx(0.5)
    assert egal["a"].axes[Axe.VIE] is None


def test_ville_sans_donnees() -> None:
    scores = scorer({"a": {}})
    assert scores["a"].global_ is None
    assert scores["a"].couverture == 0


@pytest.mark.parametrize("poids", [{Axe.BUDGET: -1.0}, {axe: 0.0 for axe in Axe}])
def test_poids_invalides(poids: dict[Axe, float]) -> None:
    with pytest.raises(ValueError):
        scorer({"a": {}}, poids)
