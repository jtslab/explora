# ADR 0001 : stack technique (proposée)

Statut : proposée, à valider.

## Décision

- **Python 3.12 + FastAPI** pour l'API et l'ingestion : écosystème data (pandas,
  geopandas si besoin), typage avec Pydantic, OpenAPI généré.
- **httpx** (async) pour toutes les sources, derrière un `SourceClient` commun.
- **PostgreSQL + PostGIS** pour les géométries communales et les requêtes spatiales.
- **MapLibre GL** côté carte, fonds IGN de la Géoplateforme.
- **Front** : Astro ou Next.js en génération statique pour les ~400 pages ville
  (le SEO est un objectif du module) avec un îlot MapLibre. Choix à arbitrer.
- **uv** pour les dépendances, **ruff** + **mypy strict** + **pytest/respx** en CI.

## Conséquences

- Les scores sont précalculés par un job d'ingestion et stockés : l'API ne fait pas
  d'appels aux sources en temps réel, hormis les endpoints de démonstration.
- La pondération utilisateur est appliquée à la volée sur les notes par axe déjà
  calculées (opération légère, possible côté front).
