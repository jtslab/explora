import pytest

from explora.modules.etudiant.indicators import (
    rendement_locatif_brut,
    tension_locative,
    vitalite_commerciale,
)


def test_rendement() -> None:
    assert rendement_locatif_brut(15.0, 3600.0) == pytest.approx(0.05)
    assert rendement_locatif_brut(None, 3600.0) is None
    assert rendement_locatif_brut(15.0, 0) is None


def test_tension() -> None:
    assert tension_locative(60000, 6000) == 10
    assert tension_locative(1000, 0) is None


def test_vitalite() -> None:
    assert vitalite_commerciale(120, 150) == -30
    assert vitalite_commerciale(None, 3) is None
