"""Configuration lue depuis l'environnement (voir `.env.example`)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="EXPLORA_", extra="ignore")

    env: str = "dev"
    database_url: str = "postgresql+psycopg://explora:explora@localhost:5432/explora"
    http_user_agent: str = "explora/0.1 (+https://github.com/jtslab/explora)"
    http_timeout_s: float = 15.0
    cache_ttl_s: int = 24 * 3600

    geo_api_url: str = "https://geo.api.gouv.fr"
    geocodage_url: str = "https://data.geopf.fr/geocodage"
    georisques_url: str = "https://georisques.gouv.fr/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
