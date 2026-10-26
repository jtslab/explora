# Sélection des ~400 villes (proposition, à valider)

Objectif : 3 à 4 villes par département ayant au moins une formation post-bac
(BTS, IUT, université, école), soit environ 101 × 4 ≈ 400 villes.

## Méthode proposée

1. **Source** : atlas régional des effectifs d'étudiants inscrits (MESR), qui agrège
   par commune les effectifs de toutes les filières, BTS et CPGE compris.
   Dernière année disponible.
2. **Éligibilité** : commune avec au moins une formation post-bac et un effectif ≥ 100
   étudiants (seuil à régler pour éviter les lycées avec une seule section de BTS).
3. **Classement par département** : par effectif décroissant.
4. **Retenir** les 4 premières ; s'il y en a moins de 4 éligibles, toutes les
   éligibles (certains départements ruraux n'en auront que 2 ou 3).
5. **Toujours inclure la préfecture** si elle est éligible, même hors top 4
   (elle remplace alors la 4ᵉ).
6. **Paris, Lyon, Marseille** : une ville chacune (pas d'arrondissements) ; on complète
   le département avec les communes suivantes (ex. Hauts-de-Seine).
7. **Outre-mer** : mêmes règles pour les DROM (hors Mayotte pour les loyers, absente de
   la carte des loyers).

La liste sera produite par un script reproductible (`explora.modules.etudiant.selection`,
à venir) et versionnée en CSV, pour que chaque ajout ou retrait soit visible en PR.
