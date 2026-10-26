"""API HTTP d'Explora."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Path

from explora import __version__
from explora.adapters import ALL_ADAPTERS
from explora.adapters.geo_api import GeoApiAdapter
from explora.api.deps import geo_api
from explora.core.errors import SourceError, SourceUnavailableError
from explora.core.models import Commune

app = FastAPI(
    title="Explora",
    version=__version__,
    description="Explorateur de données publiques françaises. Outil indépendant.",
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/sources")
async def sources() -> list[dict[str, Any]]:
    """Sources utilisées, avec licence et mention d'attribution."""
    return [asdict(adapter.info) for adapter in ALL_ADAPTERS]


@app.get("/communes/{code_insee}", response_model=Commune)
async def commune(
    code_insee: Annotated[str, Path(pattern=r"^[0-9][0-9AB][0-9]{3}$")],
    adapter: Annotated[GeoApiAdapter, Depends(geo_api)],
) -> Commune:
    try:
        return await adapter.commune(code_insee)
    except SourceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SourceError as exc:
        status = 404 if exc.status_code == 404 else 502
        raise HTTPException(status_code=status, detail=str(exc)) from exc
