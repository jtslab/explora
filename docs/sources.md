# Sources de données

État au 26/10/2026, après des appels réels depuis l'environnement cloud (`uv run pytest -m live`
pour les sources qui ont un adaptateur). « OK » = appel réel réussi et format vérifié.

| Axe | Source | Accès | Clé | Appel réel | Adaptateur |
| --- | --- | --- | --- | --- | --- |
| Socle | API Découpage administratif | `https://geo.api.gouv.fr/communes/{code}`, `/departements/{code}/communes`, `/communes` (toutes, ~35 000) | non | OK | `geo_api` (test live) |
| Socle | Géocodage Géoplateforme IGN | `https://data.geopf.fr/geocodage/search` | non | OK | `geocodage` (test live) |
| Études | Effectifs d'étudiants inscrits (atlas régional, MESR) | API Opendatasoft `data.enseignementsup-recherche.gouv.fr/api/explore/v2.1/catalog/datasets/fr-esr-atlas_regional-effectifs-d-etudiants-inscrits/exports/json` avec `group_by` (agrégation côté serveur, ~40 s) | non | OK : rentrée 2025, 1 609 communes avec étudiants, BTS inclus ; Paris, Lyon, Marseille par arrondissement | `effectifs_etudiants` (test live), sélection des villes |
| Socle | Code officiel géographique 2025 (INSEE) | CSV `www.insee.fr/fr/statistiques/fichier/8377162/v_departement_2025.csv` (chef-lieu de chaque département) | non | OK | `cog` (test live) |
| Études | Principaux établissements (MESR) | même API, jeu `fr-esr-principaux-etablissements-enseignement-superieur` | non | OK, mais seulement 245 grands établissements (pas les lycées à BTS) | à faire |
| Études | Cartographie des formations Parcoursup | même API, jeu `fr-esr-cartographie_formations_parcoursup` (157 497 lignes, commune + type de formation) | non | OK | à faire |
| Études | Vœux Parcoursup 2025 | API Opendatasoft `data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-esr-parcoursup/records` (14 252 formations, session 2025) | non | OK : capacité, vœux, admis, filière, coordonnées ; **pas de code INSEE** | `voeux_formations` (test live) |
| Études | InserSup | même API MESR, jeu `fr-esr-insersup` | non | OK | à faire |
| Budget | Carte des loyers 2025 (ANIL) | 4 CSV sur [data.gouv.fr](https://www.data.gouv.fr/datasets/693aa2feed1bf4da603faa49/) : appartement, T1-T2, T3+, maison | non | OK (voir encodage et Paris/Lyon/Marseille) | `loyers` (test live) |
| Budget | DVF (Cerema, API Données foncières) | `apidf-preprod.cerema.fr/dvf_opendata/mutations/?code_insee=&codtypbien=121&anneemut_min=` | non | OK (lent, ~1,3 s) | à faire |
| Budget | Logements étudiants (CNOUS) | [data.gouv.fr](https://www.data.gouv.fr/datasets/logements-etudiants/) : 26 flux XML `http://webservices-v2.crous-mobile.fr/feed/{flux}/{flux}-logement.xml` | non | OK en HTTP seulement : 828 résidences géolocalisées ; nombre de places **estimé** pour 496 (60 %) | `residences_etudiantes` (test live) |
| Vie | BPE 2025 (INSEE) | API Melodi `api.insee.fr/melodi/data/DS_BPE?GEO=COM-{code}` (ou ZIP national `www.insee.fr/fr/statistiques/fichier/8217527/DS_BPE_CSV_FR.zip`, 150 Mo décompressé) | non | OK : ~200 types d'équipements par commune en un appel | `insee_melodi` (test live) |
| Vie | API Recherche d'entreprises / SIRENE | `recherche-entreprises.api.gouv.fr/search?activite_principale=&code_commune=&etat_administratif=A\|C` | non | OK | à faire |
| Budget | Recensement : logements par statut d'occupation (INSEE) | API Melodi `api.insee.fr/melodi/data/DS_RP_LOGEMENT_PRINC` | non | OK : résidences principales, locataires, locataires en meublé (RP 2012, 2017, 2023) | `insee_melodi` (test live) |
| Vie | API Sirene (INSEE) | `api.insee.fr/api-sirene/3.11` | **oui** (compte portail-api.insee.fr) | HTTP 401 sans clé, comme prévu ; l'API Recherche d'entreprises suffit pour l'instant | non prévu |
| Mobilité | transport.data.gouv.fr (GTFS, GBFS) | `transport.data.gouv.fr/api/datasets` (808 jeux, sans pagination) | non | OK | à faire |
| Cadre | Géorisques | `https://georisques.gouv.fr/api/v1/gaspar/risques?code_insee=` | non | OK (1 000 req/min/IP) | `georisques` (test live) |
| Cadre | Indice ATMO (Atmo France) | `https://admindata.atmofrance.org/api/data/112/...` filtré par `code_zone` (INSEE) | **oui** : compte validé + jeton d'1 h | **bloqué** : la passerelle répond 502 au CONNECT (domaine autorisé, hôte injoignable depuis l'environnement) | à faire |
| Carte | Fonds IGN (Géoplateforme) | tuiles vectorielles `data.geopf.fr/tms/1.0.0/PLAN.IGN/{z}/{x}/{y}.pbf`, style `data.geopf.fr/annexes/ressources/vectorTiles/styles/PLAN.IGN/standard.json`, WMTS | non | OK | front |

## Écarts constatés entre la documentation et les vraies réponses

- **Réseau** : depuis l'environnement cloud, environ un appel sur quatre est coupé pendant la
  négociation TLS (data.gouv.fr, MESR, recherche-entreprises, geo.api.gouv.fr). Le retry du
  `SourceClient` absorbe ces coupures ; les tests live utilisent 6 tentatives.
- **Carte des loyers** : le CSV 2025 est encodé en **Windows-1252** alors que le serveur annonce
  `charset=utf-8` ; sans correction, les noms accentués sont illisibles. Le client décode
  désormais en UTF-8 et se rabat sur Windows-1252. Les champs sont entre guillemets et les
  lignes en CRLF (géré par `csv`).
- **Paris, Lyon, Marseille** : la carte des loyers ne publie que les arrondissements (75101…,
  69381…, 13201…), jamais 75056 / 69123 / 13055 utilisés par l'API Géo. L'adaptateur ajoute une
  ligne communale = moyenne des arrondissements pondérée par le nombre d'annonces.
- **Géorisques** : GASPAR mélange familles de risques (code à 2 chiffres : `11` Inondation) et
  sous-risques (3 chiffres : `112` crue lente). Les compter ensemble gonflait `nb_risques`
  (12 au lieu de 7 à Grenoble) ; l'adaptateur les sépare (`risques` / `sous_risques`).
- **API Géo, géocodage** : conformes à la documentation (le géocodeur renvoie des champs en plus :
  `population`, `depcode`, `banId`…).
- **DVF Cerema** : `valeurfonc` et `sbati` sont des chaînes ; le lien `next` de pagination est en
  `http://` (à réécrire en https). Le domaine est une préproduction : prévoir le repli sur les
  fichiers DVF géolocalisés.
- **Recherche d'entreprises** : `etat_administratif` accepte `A` (actif) ou `C` (cessé), pas `F`.
  L'API ne filtre pas par période de création ou de fermeture ; la vitalité commerciale sur 3 ans
  sera plus simple à calculer depuis le stock SIRENE (fichier) que via cette API.
- **transport.data.gouv.fr** : la zone couverte est donnée par EPCI (`covered_area.insee` = SIREN
  de l'EPCI) ; on fera la jointure avec `codeEpci` de l'API Géo.
- **Vœux Parcoursup** : pas de code commune, seulement `ville_etab` (libellé), `dep` et
  `g_olocalisation_des_formations`. Paris est publié par arrondissement avec des espaces doublés
  (« Paris  5e  Arrondissement ») : l'adaptateur normalise les espaces ; le rattachement à la
  commune se fera par les coordonnées (point dans polygone, PostGIS). `count()` refuse le champ
  géographique. Le domaine coupe encore plus de négociations TLS que les autres : les tests live
  passent à 10 tentatives.
- **Flux CNOUS** : data.gouv.fr annonce `http://…:8080/feed/…` pour 24 flux sur 26, mais le
  port 8080 ne répond pas et HTTPS renvoie 404 ; seul `http://webservices-v2.crous-mobile.fr/feed/…`
  (port 80) fonctionne, pour les 26 flux. Le XML (`<residence id title short_desc lat lon zone>`
  + `infos` en HTML échappé, `address`…) ne contient pas de nombre de places.
- **API INSEE** : Melodi (statistiques locales) fonctionne **sans clé** ; les autres dimensions
  d'un jeu doivent être fixées à `_T` pour obtenir une seule série, et un paramètre répété
  (`TSH=200&TSH=_T`) renvoie plusieurs modalités en un appel. Le code géographique revient
  préfixé du millésime (`2026-COM-38185`). Sirene exige une clé (401).
- **Atmo** : toujours injoignable, et une clé reste de toute façon nécessaire. À retenter une fois
  le compte obtenu ; repli possible sur les fichiers des AASQA régionales.

## Points d'attention relevés

- **Géocodage** : l'API Adresse (`api-adresse.data.gouv.fr`) a été transférée à l'IGN ;
  l'ancien domaine ne fait plus que rediriger et n'était annoncé que jusqu'à janvier 2026.
  On utilise directement `data.geopf.fr/geocodage`.
- **Loyers** : indicateurs expérimentaux, charges comprises, non meublé, à la commune.
  Les communes sans annonces reçoivent la valeur d'une maille de communes voisines
  (`TYPPRED = maille`). L'ANIL recommande la prudence si R² < 0,5 ou moins de 30
  observations : c'est la propriété `LoyerCommune.fiable`. Mention obligatoire :
  « Estimations ANIL, à partir des données du Groupe SeLoger et de leboncoin ».
- **Places en résidence étudiante** : le jeu CNOUS n'a **pas de champ structuré** pour le
  nombre de places. `residences_etudiantes` l'extrait du texte (« 171 logements », « 1074 lits »,
  « 798 chambres ») : 496 résidences sur 828, environ 95 000 places au total. La couverture est
  très inégale : quasi complète à Lyon, Grenoble, Nantes, Versailles, Aix-Marseille, mais
  3 résidences sur 87 à Paris, 3 sur 48 à Lille, 0 sur 23 à Poitiers. Quand la description
  détaille plusieurs types, seul le premier effectif est retenu (minorant).
  Proposition pour la tension locative : afficher `étudiants ÷ places estimées` seulement si
  toutes les résidences de la ville ont une estimation, sinon basculer sur
  `étudiants ÷ locataires en meublé` (recensement, via Melodi), en le signalant.
- **Qualité de l'air** : seule source nécessitant un compte ; à prévoir dans les secrets
  de la CI de déploiement, jamais dans le dépôt.
- **Nommage** : ne pas reprendre « CROUS » ni « Parcoursup » dans les noms de produit ;
  les citer uniquement comme sources.
