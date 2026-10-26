# Sources de données

État au 25/10/2026. « Doc vérifiée » signifie que l'endpoint a été vérifié dans la
documentation officielle ; les appels réels restent à valider (`pytest -m live`, à venir),
car l'environnement de développement initial n'avait pas accès à ces domaines.

| Axe | Source | Accès | Clé | État | Adaptateur |
| --- | --- | --- | --- | --- | --- |
| Socle | API Découpage administratif | `https://geo.api.gouv.fr/communes/{code}`, `/departements/{code}/communes` | non | doc vérifiée | `geo_api` |
| Socle | Géocodage Géoplateforme IGN | `https://data.geopf.fr/geocodage/search` | non | doc vérifiée | `geocodage` |
| Études | Effectifs d'étudiants inscrits (atlas régional, MESR) | API Opendatasoft `data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/fr-esr-atlas_regional-effectifs-d-etudiants-inscrits_agregeables/records` | non | jeu identifié | à faire |
| Études | Principaux établissements d'enseignement supérieur (MESR) | même API, jeu `fr-esr-principaux-etablissements-enseignement-superieur` | non | à vérifier | à faire |
| Études | Parcoursup open data, InserSup | même portail MESR | non | à vérifier | à faire |
| Budget | Carte des loyers 2025 (ANIL) | 4 CSV sur [data.gouv.fr](https://www.data.gouv.fr/datasets/693aa2feed1bf4da603faa49/) : appartement, T1-T2, T3+, maison | non | doc vérifiée | `loyers` |
| Budget | DVF / DVF+ (Cerema) | API Données foncières `apidf-preprod.cerema.fr` ou fichiers DVF géolocalisés | non | à vérifier | à faire |
| Budget | Logements étudiants (CNOUS) | [data.gouv.fr](https://www.data.gouv.fr/datasets/logements-etudiants/) | non | doc vérifiée, voir limite | à faire |
| Vie | BPE (INSEE) | fichiers par commune sur insee.fr | non | à vérifier | à faire |
| Vie | API Recherche d'entreprises / SIRENE | `recherche-entreprises.api.gouv.fr/search` | non | à vérifier | à faire |
| Mobilité | transport.data.gouv.fr (GTFS, GBFS) | `transport.data.gouv.fr/api/datasets` | non | à vérifier | à faire |
| Cadre | Géorisques | `https://georisques.gouv.fr/api/v1/gaspar/risques?code_insee=` | non | doc vérifiée (1 000 req/min/IP) | `georisques` |
| Cadre | Indice ATMO (Atmo France) | `https://admindata.atmofrance.org/api/data/112/...` filtré par `code_zone` (INSEE) | **oui** : compte validé + jeton d'1 h | doc vérifiée | à faire |
| Carte | Fonds IGN (Géoplateforme) | WMTS / tuiles vectorielles `data.geopf.fr` | non | à vérifier | front |

## Points d'attention relevés

- **Géocodage** : l'API Adresse (`api-adresse.data.gouv.fr`) a été transférée à l'IGN ;
  l'ancien domaine ne fait plus que rediriger et n'était annoncé que jusqu'à janvier 2026.
  On utilise directement `data.geopf.fr/geocodage`.
- **Loyers** : indicateurs expérimentaux, charges comprises, non meublé, à la commune.
  Les communes sans annonces reçoivent la valeur d'une maille de communes voisines
  (`TYPPRED = maille`). L'ANIL recommande la prudence si R² < 0,5 ou moins de 30
  observations : c'est la propriété `LoyerCommune.fiable`. Mention obligatoire :
  « Estimations ANIL, à partir des données du Groupe SeLoger et de leboncoin ».
- **Places en résidence étudiante** : le jeu CNOUS liste les résidences avec leur
  géolocalisation et leurs loyers, mais **pas de champ structuré pour le nombre de places**.
  La tension locative telle que définie (étudiants ÷ places) demande donc soit une
  extraction depuis les descriptions, soit un indicateur de repli (étudiants ÷ nombre de
  résidences, ou étudiants ÷ logements locatifs du recensement INSEE).
- **Qualité de l'air** : seule source nécessitant un compte ; à prévoir dans les secrets
  de la CI de déploiement, jamais dans le dépôt.
- **Nommage** : ne pas reprendre « CROUS » ni « Parcoursup » dans les noms de produit ;
  les citer uniquement comme sources.
