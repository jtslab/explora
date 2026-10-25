# Réponses réelles enregistrées

Extraits de réponses des API publiques, enregistrés le 25/10/2026 avec les mêmes
paramètres que les adaptateurs. Les tests unitaires s'appuient dessus pour que les mocks
restent fidèles au format réel. Pour les régénérer, relancer les appels de
`tests/live/test_live.py` et remplacer les fichiers.

| Fichier | Requête |
| --- | --- |
| `geo_api_commune_35238.json` | `geo.api.gouv.fr/communes/35238?fields=…` |
| `geocodage_search_rennes.json` | `data.geopf.fr/geocodage/search?q=rennes&limit=1&type=municipality` |
| `georisques_risques_35238.json` | `georisques.gouv.fr/api/v1/gaspar/risques?code_insee=35238` |
| `loyers_app12_extrait.csv` | 5 lignes du CSV « appartement 1-2 pièces » 2025, octets d'origine (Windows-1252, CRLF) |
