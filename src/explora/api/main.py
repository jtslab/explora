"""API HTTP d'Explora."""

import json
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Path, Query

from explora import __version__
from explora.adapters import ALL_ADAPTERS
from explora.adapters.geo_api import GeoApiAdapter
from explora.api.deps import geo_api
from explora.core.config import get_settings
from explora.core.errors import SourceError, SourceUnavailableError
from explora.core.models import Commune
from explora.modules.etudiant.scoring import Axe, score_global

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


Poids = Annotated[float, Query(ge=0, le=10)]


@app.get("/etudiant/villes")
def villes_etudiantes(
    etudes: Poids = 1.0, budget: Poids = 1.0, vie: Poids = 1.0, mobilite_cadre: Poids = 1.0
) -> dict[str, Any]:
    """Villes étudiantes en GeoJSON (export du job d'ingestion), score global selon les poids."""
    poids = {
        Axe.ETUDES: etudes,
        Axe.BUDGET: budget,
        Axe.VIE: vie,
        Axe.MOBILITE_CADRE: mobilite_cadre,
    }
    if not any(poids.values()):
        raise HTTPException(status_code=422, detail="au moins un poids doit être non nul")
    chemin = get_settings().export_villes_etudiantes
    try:
        geojson: dict[str, Any] = json.loads(chemin.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="export pas encore généré") from exc
    for feature in geojson["features"]:
        props = feature["properties"]
        axes = {Axe(a): note for a, note in props["axes"].items()}
        score, couverture = score_global(axes, poids)
        props["score"] = None if score is None else round(score, 1)
        props["couverture"] = round(couverture, 2)
    geojson["metadata"]["poids"] = {axe.value: p for axe, p in poids.items()}
    return geojson
