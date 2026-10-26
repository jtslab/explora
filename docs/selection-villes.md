# Sélection des ~400 villes

Objectif : 3 à 4 villes par département ayant au moins une formation post-bac
(BTS, IUT, université, école), environ 400 villes au total.

La liste est produite par un script reproductible et versionnée dans
[`data/villes_etudiantes.csv`](../data/villes_etudiantes.csv), pour que chaque ajout ou
retrait soit visible en PR :

```bash
uv run python -m explora.modules.etudiant.selection --sortie data/villes_etudiantes.csv
# options : --rentree 2025 (millésime de l'atlas), --cible 400 (0 = sans complément)
```

## Sources

| Donnée | Source | Appel |
| --- | --- | --- |
| Étudiants inscrits par commune et type de formation | Atlas régional des effectifs d'étudiants (MESR-SIES), rentrée 2025 | 1 export Opendatasoft agrégé côté serveur (~4 800 lignes) |
| Population, département | API Découpage administratif (`geo.api.gouv.fr/communes`) | 1 appel (~35 000 communes) |
| Préfecture de chaque département | Code officiel géographique 2025 (INSEE) | 1 fichier CSV |

L'atlas compte les inscrits de **toutes** les filières, BTS et CPGE des lycées compris,
et rattache chaque formation à sa commune par code INSEE. Il est plus complet que
l'open data Parcoursup (qui n'a ni code INSEE ni effectifs inscrits, seulement les vœux et
les admis de l'année), qui sert plutôt à décrire l'offre de formation de chaque ville.

## Règle

1. **Éligibilité** : au moins **100 étudiants inscrits** dans la commune, et une
   **population ≥ 3 000 habitants**, sauf si la commune accueille au moins **500 étudiants**
   (vrai campus en commune périphérique : Sevenans/UTBM, Dury/Amiens, Saint-Contest/Caen,
   Neuville-sur-Oise/CY Cergy...). Le seuil de population écarte les villages qui n'ont
   qu'une section de BTS, souvent agricole (Le Subdray, Lasbordes, Avize...) : une page
   « logement étudiant » n'y aurait pas de sens.
2. **Classement** par effectif décroissant dans le département ; on retient les
   **4 premières** éligibles.
3. **Au plus 3 communes par unité urbaine** (INSEE), pour garder une diversité
   géographique : le 4ᵉ choix va à une autre ville du département (Libourne plutôt qu'une
   4ᵉ commune de l'agglomération bordelaise). Ce plafond ne s'applique pas en
   Île-de-France, où presque tout est dans l'unité urbaine de Paris.
4. **Préfecture toujours incluse** si elle est éligible (elle remplace alors la 4ᵉ).
   En pratique, un seul cas : Basse-Terre (Guadeloupe, 482 étudiants), qui prend la place
   de Saint-Claude (1 046) ; celle-ci revient ensuite par le complément.
5. **Complément jusqu'à 400** : les départements ruraux et Paris laissent des places
   libres (346 villes avec les règles 1 à 4). Elles vont aux plus gros effectifs non retenus,
   toutes régions confondues, à raison de **2 villes de plus par département au maximum**
   et sans plafond par unité urbaine (ce sont surtout des communes-campus : Loos, Écully,
   Cachan, Gradignan...). Ces lignes sont marquées `motif=complement` dans le CSV : on peut
   les retirer d'un filtre, ou relancer avec `--cible 0`.

## Résultat (rentrée 2025)

- **400 villes** dans les **101 départements**, qui regroupent **2,86 millions d'étudiants
  sur 3,06** (93 %).
- Répartition : 346 retenues par effectif, 1 préfecture ajoutée, 53 en complément.
- Par département : 4 villes dans 41 départements, 5 ou 6 dans 29 (complément), 3 dans 12,
  1 ou 2 dans 19.
- La plus petite ville retenue : Rethel (Ardennes), 103 étudiants en BTS.

## Cas particuliers

- **Paris, Lyon, Marseille** : l'atlas publie les effectifs par arrondissement ; ils sont
  additionnés pour donner une seule ville (75056, 69123, 13055), comme le fait l'adaptateur
  des loyers. Paris est un département d'une seule commune : il n'a qu'une ville, et ses
  3 places vont au complément.
- **Banlieues-campus** : l'atlas rattache chaque formation à la commune où elle est
  enseignée. Pessac et Talence comptent ainsi plus d'étudiants que beaucoup de
  préfectures, et Saint-Martin-d'Hères (34 965) plus que Grenoble (16 561). C'est voulu :
  c'est là que vivent les étudiants. À l'inverse, Bordeaux (43 975) apparaît moins
  « étudiante » que Montpellier (85 582), dont le campus est dans la commune.
- **Petits départements** : 19 départements ont moins de 3 villes éligibles, faute
  d'une 2ᵉ ou 3ᵉ commune avec 100 étudiants : Alpes-de-Haute-Provence (04), Hautes-Alpes (05),
  Ariège (09), Cantal (15), Creuse (23), Corse-du-Sud (2A), Gers (32), Loir-et-Cher (41),
  Lot (46), Haute-Marne (52), Meuse (55), Nièvre (58), Hautes-Pyrénées (65), Haute-Saône (70),
  Paris (75), Tarn (81), Tarn-et-Garonne (82), Yonne (89), Territoire de Belfort (90).
  Le Cantal, la Corse-du-Sud et le Tarn-et-Garonne n'en ont qu'une (Aurillac, Ajaccio,
  Montauban). On ne descend pas sous le seuil : Saint-Flour (43 étudiants) n'a pas
  l'offre d'une ville étudiante.
- **Corse** : 2A et 2B sont traités comme deux départements. Corte (université, 4 169)
  passe devant Bastia (préfecture, 827).
- **Outre-mer** : les 5 DROM (971 Guadeloupe, 972 Martinique, 973 Guyane, 974 La Réunion,
  976 Mayotte) suivent les mêmes règles. À Mayotte, Dembeni (université) passe devant
  Mamoudzou. Mayotte n'est pas couverte par la carte des loyers : son axe « Budget » sera
  incomplet. Les collectivités d'outre-mer (Saint-Pierre-et-Miquelon, Polynésie,
  Nouvelle-Calédonie...) sont hors périmètre, comme les effectifs à l'étranger (codes 99xxx).
- **Communes nouvelles** : les codes sont ceux de l'API Géo à la date du calcul ; un code
  de l'atlas absent du référentiel courant est ignoré (aucun cas en 2025 hors étranger).

## Mettre la liste à jour

Chaque année, à la sortie de l'atlas (rentrée N disponible au printemps N+1) : relancer
le script avec `--rentree N`, et mettre à jour le chemin du fichier COG millésimé
(`explora.adapters.cog.DEPARTEMENTS_2025`) si le découpage a changé. La PR montre les
villes entrées et sorties.
