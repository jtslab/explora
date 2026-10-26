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
    """Familles de risques (Inondation, Séisme...) : base de l'indicateur `nb_risques`."""
    sous_risques: list[str] = Field(default_factory=list)


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


class OffreFormation(BaseModel):
    """Formation post-bac proposée pour une session, avec sa commune d'implantation."""

    session: str
    code: str
    """Identifiant de la formation dans la source (stable d'une année sur l'autre)."""
    code_uai: str
    etablissement: str
    secteur: str | None = None
    """« Publics » ou « Privés … » tel que publié."""
    types: list[str] = Field(default_factory=list)
    """Types de formation (BTS, BUT, Licence, Études de santé...)."""
    mentions: list[str] = Field(default_factory=list)
    """Mentions ou spécialités, ex. « BTS - Tourisme », « L1 - Droit »."""
    libelle: str = ""
    apprentissage: bool = False
    commune: str
    """Libellé de la commune (Paris, Lyon et Marseille sans arrondissement)."""
    departement: str
    """Libellé du département (pas de code dans la source)."""
    point: Point | None = None


class FormationVoeux(BaseModel):
    """Formation post-bac avec ses vœux et sa capacité d'accueil (une session)."""

    session: str
    code_uai: str
    etablissement: str
    ville: str
    """Libellé de la ville tel que publié (pas de code INSEE dans la source)."""
    code_departement: str
    filiere: str
    formation: str
    capacite: int | None = None
    voeux: int | None = None
    admis: int | None = None
    point: Point | None = None


class ResidenceEtudiante(BaseModel):
    """Résidence universitaire publique."""

    id: str
    nom: str
    zone: str | None = None
    adresse: str | None = None
    point: Point | None = None
    places_estimees: int | None = None
    """Extrait du texte descriptif, faute de champ structuré : à traiter comme une estimation."""


class LogementsCommune(BaseModel):
    """Résidences principales selon le statut d'occupation (recensement INSEE)."""

    code_insee: str
    annee: str
    residences_principales: float | None = None
    locataires: float | None = None
    locataires_meubles: float | None = None


class EffectifCommune(BaseModel):
    """Étudiants inscrits dans une commune pour un regroupement de formations (atlas MESR)."""

    code_insee: str
    """Code publié par la source : arrondissement pour Paris, Lyon et Marseille."""
    nom: str
    code_departement: str
    unite_urbaine: str | None = None
    regroupement: str
    """`TOTAL`, `UNIV`, `STS`, `CPGE`, `ING_autres`, `EC_COM`..."""
    effectif: int


class Departement(BaseModel):
    code: str
    nom: str
    chef_lieu: str
    """Code INSEE de la préfecture."""
