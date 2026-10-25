"""Modèles normalisés partagés entre sources et modules."""

from pydantic import BaseModel, Field


class Point(BaseModel):
    lon: float
    lat: float


class Commune(BaseModel):
    code_insee: str = Field(pattern=r"^[0-9][0-9AB][0-9]{3}$")
    nom: str
    code_departement: str
    code_region: str | None = None
    codes_postaux: list[str] = Field(default_factory=list)
    population: int | None = None
    centre: Point | None = None


class GeocodeResult(BaseModel):
    label: str
    score: float
    point: Point
    code_insee: str | None = None
    commune: str | None = None
    code_postal: str | None = None
    type: str | None = None


class RisqueCommune(BaseModel):
    code_insee: str
    risques: list[str]


class LoyerCommune(BaseModel):
    """Loyer d'annonce estimé (charges comprises, non meublé) à la commune."""

    code_insee: str
    nom: str
    typologie: str
    loyer_m2: float
    intervalle_bas_m2: float | None = None
    intervalle_haut_m2: float | None = None
    niveau_prediction: str | None = None
    nb_observations: int | None = None
    r2_ajuste: float | None = None

    @property
    def fiable(self) -> bool:
        """Seuils de prudence recommandés par l'ANIL : R² ≥ 0,5 et ≥ 30 observations."""
        if self.r2_ajuste is None or self.nb_observations is None:
            return False
        return self.r2_ajuste >= 0.5 and self.nb_observations >= 30
