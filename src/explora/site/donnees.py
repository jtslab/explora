"""Contrat de données entre le job d'ingestion et le site.

Le job exporte un GeoJSON (une Feature Point par ville) que le site lit tel quel :
la carte le charge côté navigateur, le générateur en tire une page par ville.
"""

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from explora.modules.etudiant.scoring import Axe

VERSION_CONTRAT = 1


class Axes(BaseModel):
    """Note 0-100 de chaque axe, relative aux villes comparées (None = pas de données)."""

    etudes: float | None = None
    budget: float | None = None
    vie: float | None = None
    mobilite_cadre: float | None = None

    def note(self, axe: Axe) -> float | None:
        value: float | None = getattr(self, axe.value)
        return value


class Indicateurs(BaseModel):
    """Valeurs brutes affichées sur la fiche ville (None = donnée manquante)."""

    model_config = ConfigDict(extra="allow")

    effectifs_etudiants: float | None = None
    nb_etablissements: float | None = None
    nb_filieres: float | None = None
    loyer_m2: float | None = None
    """Loyer mensuel charges comprises, non meublé (T1-T2), €/m², estimation à la commune."""
    prix_m2: float | None = None
    """Prix de vente médian des studios (repli : tous appartements), €/m²."""
    rendement_brut: float | None = None
    """Loyer annuel ÷ prix, à surface égale (0.05 = 5 %)."""
    tension_locative: float | None = None
    """Étudiants par logement étudiant (voir `Details.tension_methode`)."""
    commerces_pour_1000: float | None = None
    equipements_culture_sport_pour_1000: float | None = None
    vitalite_commerciale: float | None = None
    """Solde créations - fermetures d'établissements sur 3 ans."""
    arrets_transport_pour_1000: float | None = None
    stations_velo: float | None = None
    indice_qualite_air: float | None = None
    """Indice ATMO moyen (1 bon à 6 extrêmement mauvais)."""
    nb_risques: float | None = None


class Details(BaseModel):
    """Précisions de méthode qui changent la lecture d'un indicateur."""

    model_config = ConfigDict(extra="allow")

    tension_methode: str | None = None
    """« places_residences » ou « locataires_meubles » (repli sans places connues)."""
    loyer_fiable: bool | None = None
    prix_m2_typologie: str | None = None
    """« t1 » (studios) ou « appartements » (repli, tous appartements)."""
    prix_m2_annee: int | None = None


class ProprietesVille(BaseModel):
    model_config = ConfigDict(extra="allow")

    code_insee: str
    nom: str
    code_departement: str
    departement: str
    population: int | None = None
    effectif_etudiants: int | None = None
    formations: list[str] = Field(default_factory=list)
    axes: Axes = Field(default_factory=Axes)
    score: float | None = None
    """Score global à poids égaux ; le site le recalcule avec les poids de l'utilisateur."""
    couverture: float = 0.0
    indicateurs: Indicateurs = Field(default_factory=Indicateurs)
    risques: list[str] = Field(default_factory=list)
    details: Details = Field(default_factory=Details)
    indicateurs_demo: list[str] = Field(default_factory=list)
    """Indicateurs dont la valeur est fictive (maquette) : à signaler à l'affichage."""


class PointGeo(BaseModel):
    type: str = "Point"
    coordinates: tuple[float, float]


class FeatureVille(BaseModel):
    type: str = "Feature"
    geometry: PointGeo
    properties: ProprietesVille


class SourceExport(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    attribution: str
    licence: str


class Metadonnees(BaseModel):
    model_config = ConfigDict(extra="allow")

    genere_le: datetime
    demo: bool = False
    version: int = VERSION_CONTRAT
    sources: list[SourceExport] = Field(default_factory=list)
    indicateurs_manquants: list[str] = Field(default_factory=list)


class ExportVilles(BaseModel):
    type: str = "FeatureCollection"
    metadata: Metadonnees
    features: list[FeatureVille]


def charger(chemin: Path) -> ExportVilles:
    return ExportVilles.model_validate_json(chemin.read_text(encoding="utf-8"))


def ecrire(export: ExportVilles, chemin: Path) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    data = export.model_dump(mode="json")
    chemin.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), "utf-8")


def slugifier(texte: str) -> str:
    """« Saint-Étienne » → « saint-etienne », « Vandœuvre-lès-Nancy » → « vandoeuvre-les-nancy »."""
    ligatures = texte.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae").replace("Æ", "Ae")
    ascii_ = unicodedata.normalize("NFKD", ligatures).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


def slugs(villes: Sequence[ProprietesVille]) -> dict[str, str]:
    """Slug d'URL par code INSEE ; les homonymes (Saint-Denis 93 / 974) prennent le département."""
    bruts = {v.code_insee: slugifier(v.nom) for v in villes}
    doublons = Counter(bruts.values())
    return {
        v.code_insee: (
            f"{bruts[v.code_insee]}-{v.code_departement.lower()}"
            if doublons[bruts[v.code_insee]] > 1
            else bruts[v.code_insee]
        )
        for v in villes
    }
