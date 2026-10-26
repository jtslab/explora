# Réponses réelles enregistrées

Extraits de réponses des API publiques, enregistrés les 25 et 26/10/2026 avec les mêmes
paramètres que les adaptateurs. Les tests unitaires s'appuient dessus pour que les mocks
restent fidèles au format réel. Pour les régénérer, relancer les appels de
`tests/live/test_live.py` et remplacer les fichiers.

| Fichier | Requête |
| --- | --- |
| `geo_api_commune_35238.json` | `geo.api.gouv.fr/communes/35238?fields=…` |
| `geocodage_search_rennes.json` | `data.geopf.fr/geocodage/search?q=rennes&limit=1&type=municipality` |
| `georisques_risques_35238.json` | `georisques.gouv.fr/api/v1/gaspar/risques?code_insee=35238` |
| `loyers_app12_extrait.csv` | 5 lignes du CSV « appartement 1-2 pièces » 2025, octets d'origine (Windows-1252, CRLF) |
| `parcoursup_voeux_38_extrait.json` | `data.education.gouv.fr/…/fr-esr-parcoursup/records?select=…&where=dep="38"&limit=3` |
| `residences_grenoble_extrait.xml` | 4 résidences du flux `http://webservices-v2.crous-mobile.fr/feed/grenoble/grenoble-logement.xml` |
| `melodi_rp_logement_38185.json` | `api.insee.fr/melodi/data/DS_RP_LOGEMENT_PRINC?GEO=COM-38185&TSH=200&TSH=_T&TSH=212_222&…` |
| `melodi_bpe_38185_extrait.json` | 8 observations de `api.insee.fr/melodi/data/DS_BPE?GEO=COM-38185&BPE_MEASURE=FACILITIES&TIME_PERIOD=2025` |
| `atlas_effectifs_extrait.json` | `data.enseignementsup-recherche.gouv.fr/…/fr-esr-atlas_regional-effectifs-d-etudiants-inscrits/exports/json?where=rentree='2025' and niveau_geo='COMMUNE' and geo_id in (…)&group_by=…` (Paris 5e et 6e, Sevenans, Ajaccio) |
| `offre_formations_extrait.json` | 6 lignes de `data.education.gouv.fr/…/fr-esr-cartographie_formations_parcoursup/exports/json?where=annee="2026"` (Rennes, Saint-Denis de La Réunion, Paris) |
| `cog_departements_extrait.csv` | 4 lignes de `insee.fr/fr/statistiques/fichier/8377162/v_departement_2025.csv` |
