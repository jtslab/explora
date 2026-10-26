"""API Melodi de l'INSEE : statistiques locales (recensement, BPE...), sans clé."""

from typing import Any

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.models import LogementsCommune

# Toutes les autres dimensions du jeu sont fixées à « total » pour ne garder qu'une série.
_LOGEMENT_TOTAUX = {
    "RP_MEASURE": "DWELLINGS",
    "OCS": "DW_MAIN",
    "TDW": "_T",
    "BUILD_END": "_T",
    "CARS": "_T",
    "NRG_SRC": "_T",
    "CARPARK": "_T",
    "NOR": "_T",
    "L_STAY": "_T",
}
# Statut d'occupation (TSH) : 200 locataires, 212_222 locataires d'un meublé.
_STATUTS = {"_T": "residences_principales", "200": "locataires", "212_222": "locataires_meubles"}


def _valeur(observation: dict[str, Any]) -> float | None:
    mesure = observation.get("measures", {}).get("OBS_VALUE_NIVEAU") or {}
    value = mesure.get("value")
    return None if value is None else float(value)


def parse_logements(code_insee: str, raw: dict[str, Any]) -> LogementsCommune | None:
    """Dernier millésime disponible (le jeu contient aussi les recensements antérieurs)."""
    par_annee: dict[str, dict[str, float | None]] = {}
    for obs in raw.get("observations", []):
        dims = obs["dimensions"]
        champ = _STATUTS.get(dims.get("TSH", ""))
        if champ:
            par_annee.setdefault(dims["TIME_PERIOD"], {})[champ] = _valeur(obs)
    if not par_annee:
        return None
    annee = max(par_annee)
    return LogementsCommune(code_insee=code_insee, annee=annee, **par_annee[annee])


def parse_equipements(raw: dict[str, Any]) -> dict[str, int]:
    """Nombre d'équipements par type BPE (A504 restaurant, F303 cinéma...), hors totaux."""
    equipements: dict[str, int] = {}
    for obs in raw.get("observations", []):
        dims = obs["dimensions"]
        type_ = dims.get("FACILITY_TYPE", "_T")
        valeur = _valeur(obs)
        if type_ != "_T" and dims.get("BPE_MEASURE") == "FACILITIES" and valeur is not None:
            equipements[type_] = int(valeur)
    return equipements


class InseeMelodiAdapter(SourceAdapter):
    info = SourceInfo(
        id="insee-melodi",
        name="API Melodi (statistiques locales)",
        producer="INSEE",
        licence="Licence Ouverte 2.0",
        url="https://portail-api.insee.fr/",
        attribution="INSEE, recensement de la population et base permanente des équipements",
        caveats="Accès anonyme limité en débit : appels espacés et mis en cache.",
    )

    async def logements(self, code_insee: str) -> LogementsCommune | None:
        raw = await self.client.get_json(
            "/data/DS_RP_LOGEMENT_PRINC",
            {"GEO": f"COM-{code_insee}", "TSH": list(_STATUTS), **_LOGEMENT_TOTAUX},
        )
        return parse_logements(code_insee, raw)

    async def equipements(self, code_insee: str, annee: str) -> dict[str, int]:
        raw = await self.client.get_json(
            "/data/DS_BPE",
            {
                "GEO": f"COM-{code_insee}",
                "BPE_MEASURE": "FACILITIES",
                "TIME_PERIOD": annee,
                "maxResult": 10_000,
            },
        )
        return parse_equipements(raw)
