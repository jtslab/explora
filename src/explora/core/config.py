"""Configuration lue depuis l'environnement (voir `.env.example`)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EXPLORA_", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://explora:explora@localhost:5432/explora"
    http_user_agent: str = "explora/0.1 (+https://github.com/jtslab/explora)"
    http_timeout_s: float = 15.0
    cache_ttl_s: int = 24 * 3600
    export_villes_etudiantes: Path = Path("data/export/villes_etudiantes.geojson")

    geo_api_url: str = "https://geo.api.gouv.fr"
    geocodage_url: str = "https://data.geopf.fr/geocodage"
    georisques_url: str = "https://georisques.gouv.fr/api/v1"
    voeux_formations_url: str = "https://data.education.gouv.fr/api/explore/v2.1"
    # HTTPS renvoie 404 et le port 8080 annoncé sur data.gouv.fr ne répond pas.
    residences_etudiantes_url: str = "http://webservices-v2.crous-mobile.fr"
    insee_melodi_url: str = "https://api.insee.fr/melodi"
    effectifs_etudiants_url: str = "https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1"
    cog_url: str = "https://www.insee.fr"
    dv3f_url: str = "https://apidf-preprod.cerema.fr"
    carte_loyers_url: str = "https://www.data.gouv.fr"


@lru_cache
def get_settings() -> Settings:
    return Settings()
