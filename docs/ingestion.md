# Job d'ingestion : indicateurs et scores des villes étudiantes

Le job `explora.modules.etudiant.ingestion` lit les 400 villes de
`data/villes_etudiantes.csv`, interroge les sources publiques, calcule les indicateurs
clés et le score sur 4 axes, puis écrit `data/export/villes_etudiantes.geojson`.

```bash
uv run python -m explora.modules.etudiant.ingestion              # les 400 villes
uv run python -m explora.modules.etudiant.ingestion --codes 38185 # mise au point
```

Les réponses des sources sont mises en cache sur disque (`data/cache/ingestion`, 7 jours,
ignoré par git) : un job interrompu repart de là où il s'était arrêté. Une source en panne
n'arrête pas le job : les indicateurs concernés restent à `null` et les erreurs sont
comptées dans `metadata.erreurs_par_source`.

Le workflow [`ingestion.yml`](../.github/workflows/ingestion.yml) relance le job le 2 de
chaque mois (et à la demande) et publie le GeoJSON en artefact. Le fichier du dépôt n'est
remplacé que par pull request, après relecture.

## Collecte

| Donnée | Source | Appels | Rattachement à la ville |
| --- | --- | --- | --- |
| Centre de la commune | API Découpage administratif | 1 (toutes les communes) | code INSEE |
| Loyer d'annonce T1-T2 | Carte des loyers 2025 (ANIL) | 1 CSV | code INSEE (Paris, Lyon, Marseille : moyenne des arrondissements) |
| Prix au m² | Indicateurs DV3F du Cerema | 1 par ville | code INSEE |
| Risques | Géorisques (GASPAR) | 1 par ville | code INSEE |
| Logements loués meublés | INSEE Melodi, recensement | 1 par ville | code INSEE |
| Équipements | INSEE Melodi, BPE 2025 | 1 par ville | code INSEE |
| Résidences universitaires | Flux CNOUS | 26 flux | adresse (« 38400 Saint-Martin-d'Hères ») comparée aux noms des communes, sinon coordonnées (API Géo) |
| Formations post-bac | Open data Parcoursup 2025 | ~10 pages par département | libellé de la ville dans le département (la source n'a pas de code INSEE) |

## Indicateurs

| Indicateur | Calcul | Axe |
| --- | --- | --- |
| `effectifs_etudiants` | inscrits 2025 (atlas MESR, déjà dans le CSV) | Études |
| `nb_etablissements` | établissements (UAI) distincts proposant une formation sur la plateforme | Études |
| `nb_filieres` | types de formation distincts (BTS, BUT, licence, CPGE, IFSI...) | Études |
| `loyer_m2` | loyer d'annonce T1-T2 en €/m²/mois, charges comprises, non meublé | Budget |
| `prix_m2` | prix médian des ventes de studios de la dernière année, sinon de tous les appartements | Budget |
| `tension_locative` | voir ci-dessous | Budget |
| `commerces_pour_1000` | commerces BPE (domaine B) + restaurants (A504), pour 1 000 habitants | Vie |
| `equipements_culture_sport_pour_1000` | équipements sport, loisirs, culture BPE (domaine F), pour 1 000 habitants | Vie |
| `nb_risques` | familles de risques recensées par Géorisques | Mobilité & cadre |
| `rendement_brut` | loyer annuel ÷ prix d'achat, à surface égale (fraction : 0,05 = 5 %) | affiché, hors score |

Le score suit `scoring.py` : chaque indicateur est ramené sur 0-100 par rang centile parmi
les 400 villes, un axe est la moyenne de ses indicateurs disponibles, le score global la
moyenne pondérée des axes disponibles. Le front (ou `GET /etudiant/villes?budget=2...`)
peut rejouer le score global avec la pondération de l'utilisateur à partir des axes.

### Tension locative

Le jeu CNOUS n'a pas de nombre de places : il est extrait du texte des descriptions et
manque pour environ 40 % des résidences. Conformément à la proposition de
[sources.md](sources.md) :

- **affiché** : étudiants ÷ places en résidence quand toutes les résidences de la ville ont
  une capacité connue (`details.tension_methode = "places_residences"`), sinon étudiants ÷
  logements loués meublés (`"locataires_meubles"`), méthode à signaler sur la page ;
- **score** : toujours étudiants ÷ logements loués meublés, la seule mesure disponible
  partout. Mélanger les deux ratios, d'ordres de grandeur différents, fausserait le
  classement. La valeur utilisée est exportée dans `details.etudiants_par_meuble`.

## Ce qui manque encore

Ces indicateurs du score restent à `null` (liste dans `metadata.indicateurs_manquants`) ;
l'axe Mobilité & cadre ne repose pour l'instant que sur les risques.

- `vitalite_commerciale` : l'API Recherche d'entreprises ne filtre pas par date de
  création ou de fermeture ; prévoir le stock SIRENE (fichier).
- `arrets_transport_pour_1000`, `stations_velo` : transport.data.gouv.fr (GTFS, GBFS),
  adaptateur à écrire.
- `indice_qualite_air` : Atmo France exige un compte.

## Premier passage (26/10/2026)

Sur 400 villes : loyer 396 (pas de loyer à Mayotte), prix au m² 343 (studios 225,
tous appartements 118 ; 57 villes sous le secret statistique ou sans vente d'appartement),
formations 377, tension locative 396 (91 calculées sur les places en résidence),
équipements et risques 400. Manquent les formations :

- des Alpes-Maritimes (Nice, Antibes, Cannes...), dont les pages sont refusées par la
  passerelle réseau de l'environnement de développement à chaque tentative alors que les
  autres départements passent ; à vérifier au premier passage du workflow ;
- des communes sans formation sur la plateforme (Jouy-en-Josas, La Tronche, Sevenans...),
  dont les étudiants sont en master, en école ou en santé.

Le rendement brut médian est de 7,3 % (2,9 % à 31 %) : les valeurs extrêmes viennent de
petites villes où le prix médian porte sur peu de ventes (voir `details.prix_m2_nb_ventes`).

## Stockage

Étape intermédiaire : le résultat est un GeoJSON versionné dans le dépôt, servi tel quel
par l'API (`GET /etudiant/villes`) et lisible directement par le front. Il pèse moins
d'1 Mo pour 400 villes. Le chargement dans PostGIS (une table `villes_etudiantes` avec
la géométrie, les axes et les indicateurs en colonnes) viendra avec les contours communaux
et le rattachement spatial des formations, qui en ont réellement besoin.

## Format de l'export

`FeatureCollection` avec `metadata` (`genere_le`, `demo`, `version`, `sources`,
`avertissements`, `indicateurs_manquants`, `erreurs_par_source`) et, par ville, un
`Point` au centre de la commune et les propriétés `code_insee`, `nom`, `code_departement`,
`departement`, `population`, `effectif_etudiants`, `formations`, `score`, `axes`,
`couverture`, `indicateurs`, `risques`, `indicateurs_demo` (toujours vide ici) et
`details` (méthode de tension, fiabilité du loyer, typologie et année du prix...).
