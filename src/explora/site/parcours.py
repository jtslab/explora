"""Niveaux d'entrée et de sortie des formations, et parcours type pour y arriver.

Chaque mention de `web/data/formations.json` est rangée dans une famille (BTS, licence,
prépa, école d'ingénieurs...) qui fixe son niveau de sortie et son parcours type :
bac et spécialités conseillés au lycée, voie d'accès, poursuites et passerelles.
Ces repères sont rédigés ici, à partir des règles nationales des diplômes.

Deux jeux ouverts du ministère de l'Enseignement supérieur les complètent avec ce qui
s'est réellement passé lors de la dernière session de la plateforme nationale
d'admission :

- vœux et admissions par formation : sélectivité, taux d'accès, concours communs,
  part des admis venant d'un bac général, technologique ou professionnel ;
- admissions des bacheliers généraux par doublette d'enseignements de spécialité.

    uv run python -m explora.site.parcours --sortie web/data/parcours.json
"""

import argparse
import asyncio
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from explora.core.config import get_settings
from explora.core.http import RetryPolicy, SourceClient
from explora.site import formations as fm
from explora.site import metiers as mt

VOEUX = "/catalog/datasets/fr-esr-parcoursup/exports/json"
VOEUX_CHAMPS = (
    "session,cod_aff_form,select_form,acc_neobac,acc_bg,acc_bt,acc_bp,taux_acces_ens,detail_forma2"
)
SPECIALITES = (
    "/catalog/datasets/fr-esr-parcoursup-enseignements-de-specialite-bacheliers-generaux-3"
    "/exports/json"
)
MIN_ADMIS = 20
"""En dessous, la répartition des admis par bac n'est pas publiée (trop instable)."""
MIN_SPECIALITES = 30


@dataclass(frozen=True)
class Famille:
    titre: str
    sortie: str
    """Niveau atteint, en clair : « Bac+2 (niveau 5) »."""
    acces: str
    """Comment on entre en première année."""
    lycee: str
    """Bac et enseignements conseillés."""
    apres: str
    passerelles: str
    """Admissions parallèles, réorientations, autres façons d'y arriver."""
    entrees: tuple[int, ...] = ()
    """Niveaux (bac+N) auxquels une admission parallèle est courante."""
    concours: bool = False
    """L'entrée passe d'ordinaire par un concours ou des épreuves."""


FAMILLES: dict[str, Famille] = {
    "bts": Famille(
        titre="BTS, BTSA et BTSM",
        sortie="Bac+2 (niveau 5), en 2 ans",
        acces="Sélection sur dossier (notes de première et de terminale, appréciations, "
        "projet motivé), parfois un entretien. Souvent possible en apprentissage.",
        lycee="Ouvert à tous les bacs. Des places sont réservées aux bacs professionnels et "
        "les bacs technologiques y sont nombreux : STMG pour les BTS du tertiaire, STI2D pour "
        "l'industrie, STL ou ST2S pour la santé et le laboratoire, STAV pour les BTSA. En bac "
        "général, les spécialités en lien avec le domaine (mathématiques, physique-chimie, "
        "SES…) rassurent les jurys.",
        apres="Entrée directe dans la vie active, ou poursuite : licence professionnelle (bac+3), "
        "bachelor, 3e année de licence ou de BUT sur dossier, écoles d'ingénieurs ou de "
        "commerce par les admissions parallèles (souvent après une prépa ATS d'un an pour "
        "l'ingénieur).",
        passerelles="Une réorientation après un semestre de licence est possible dans certains "
        "BTS qui ouvrent une rentrée décalée en janvier. Les BTS ne recrutent presque "
        "jamais en 2e année.",
    ),
    "but": Famille(
        titre="BUT (bachelor universitaire de technologie)",
        sortie="Bac+3 (grade licence), en 3 ans dans un IUT",
        acces="Sélection sur dossier, parfois un entretien. Environ la moitié des places "
        "sont réservées aux bacheliers technologiques. Alternance fréquente en 2e et 3e année.",
        lycee="Bac technologique de la spécialité (STI2D, STMG, STL, ST2S…) ou bac général. "
        "Pour les BUT industriels et l'informatique, les mathématiques sont très attendues ; "
        "pour les BUT du tertiaire, mathématiques ou SES.",
        apres="Emploi de technicien supérieur ou cadre intermédiaire, ou poursuite en master "
        "(bac+5), en école d'ingénieurs (admission sur titre) ou en école de commerce.",
        passerelles="Entrée possible en 2e année après une première année d'études supérieures "
        "dans le même domaine (L1, PASS, BTS), sur dossier. Sortie possible après la "
        "2e année avec un DUT (bac+2).",
        entrees=(1, 2),
    ),
    "deust": Famille(
        titre="DEUST",
        sortie="Bac+2 (niveau 5), en 2 ans à l'université",
        acces="Sélection sur dossier, souvent un entretien. Petites promotions.",
        lycee="Ouvert aux bacs généraux, technologiques et professionnels selon la spécialité.",
        apres="Insertion professionnelle directe, ou licence professionnelle (bac+3), "
        "voire 3e année de licence générale sur dossier.",
        passerelles="Accessible aussi en reprise d'études, par la formation continue.",
    ),
    "licence": Famille(
        titre="Licence à l'université",
        sortie="Bac+3 (licence), en 3 ans",
        acces="Formation non sélective : tout bachelier peut y être admis dans la limite des "
        "places. L'université peut répondre « oui si », avec un parcours de remise à niveau.",
        lycee="Bac général le plus souvent. Les spécialités en lien avec la licence comptent : "
        "mathématiques pour l'économie et les sciences, SES ou HGGSP pour le droit, langues "
        "(LLCER) pour les langues… Les chiffres des admis ci-dessous montrent les doublettes "
        "les plus fréquentes.",
        apres="Master (bac+5, sélection à l'entrée du M1), licence professionnelle après la "
        "L2, concours de la fonction publique, écoles de commerce ou d'ingénieurs en "
        "admission parallèle, master MEEF pour devenir professeur.",
        passerelles="Changement de licence possible en fin de L1. Entrée directe en L2 ou L3 "
        "sur dossier après un BTS, un BUT, une prépa ou une autre licence (validation "
        "d'études).",
        entrees=(1, 2),
    ),
    "licence-renforcee": Famille(
        titre="Licences sélectives, doubles licences et CPES",
        sortie="Bac+3 (licence ou grade de licence), en 3 ans",
        acces="Sélection sur dossier, parfois un entretien. Effectifs réduits, rythme soutenu, "
        "souvent deux disciplines à la fois ou un tronc commun lycée-université (CPES).",
        lycee="Bac général avec de très bons résultats dans les deux disciplines visées : "
        "mathématiques pour les doubles cursus scientifiques et économiques, HGGSP, SES ou "
        "HLP pour droit, sciences politiques et humanités.",
        apres="Masters sélectifs, grandes écoles en admission parallèle, instituts d'études "
        "politiques en 4e année.",
        passerelles="En cas de difficulté, retour possible dans la licence simple de l'une des "
        "deux disciplines, sans perdre l'année.",
    ),
    "cupge": Famille(
        titre="Prépas intégrées à l'université (CUPGE)",
        sortie="Bac+3 (licence), avec préparation aux concours des grandes écoles",
        acces="Sélection sur dossier. Licence renforcée qui prépare aux concours des écoles "
        "d'ingénieurs, de commerce ou agro-véto, tout en validant les années de licence.",
        lycee="Bac général. Pour les CUPGE scientifiques : mathématiques et physique-chimie "
        "(ou SI, NSI), mathématiques expertes recommandées. Pour les CUPGE commerce : "
        "mathématiques et SES.",
        apres="Concours des grandes écoles (bac+5) ou poursuite en L3 puis master.",
        passerelles="La licence est validée année après année : pas de « 5/2 » perdu en cas "
        "d'échec au concours.",
        concours=True,
    ),
    "cpge": Famille(
        titre="Classes préparatoires aux grandes écoles (CPGE)",
        sortie="Prépa en 2 ans, puis concours des grandes écoles (bac+5)",
        acces="Sélection sur dossier, très attentive aux notes et appréciations de première et "
        "terminale. Internat possible.",
        lycee="Scientifiques (MPSI, MP2I, PCSI, PTSI) : mathématiques et physique-chimie ou SI, "
        "mathématiques expertes en terminale. BCPST : SVT et mathématiques ou physique-chimie. "
        "ECG : mathématiques (spécialité ou complémentaires) avec SES ou HGGSP. Littéraires "
        "(lettres, B/L) : HLP, HGGSP, LLCER, et mathématiques pour la B/L. Prépas "
        "technologiques : TSI pour STI2D, TB et TPC pour STL, ECT pour STMG.",
        apres="Concours en fin de 2e année (ou de 3e en redoublant) : écoles d'ingénieurs, de "
        "commerce, écoles normales supérieures, écoles vétérinaires, Saint-Cyr, Chartes.",
        passerelles="Les crédits validés en prépa permettent d'entrer en L2 ou L3 à "
        "l'université. Admission en 1re année d'école aussi possible après une licence ou "
        "un BUT, par les admissions sur titre.",
        concours=True,
    ),
    "ingenieur": Famille(
        titre="Écoles d'ingénieurs après le bac",
        sortie="Diplôme d'ingénieur bac+5 (grade master) ; aussi des bachelors bac+3",
        acces="Cycle préparatoire intégré de 2 ans, puis cycle ingénieur de 3 ans. Admission sur "
        "dossier, souvent par un concours commun post-bac (Geipi Polytech, Avenir, Puissance "
        "Alpha, Advance, INSA…) avec parfois des épreuves écrites ou un entretien.",
        lycee="Bac général avec mathématiques et physique-chimie, ou mathématiques et SI ou "
        "NSI ; mathématiques expertes appréciées. Quelques écoles recrutent en STI2D ou STL.",
        apres="Ingénieur dès la sortie, doctorat possible.",
        passerelles="Beaucoup d'élèves ingénieurs n'y entrent pas après le bac : concours après "
        "une prépa (bac+2), admission sur titre après un BUT, une licence ou une prépa ATS "
        "après un BTS (bac+2 ou bac+3).",
        entrees=(2, 3),
        concours=True,
    ),
    "cmi": Famille(
        titre="Cursus master en ingénierie (CMI)",
        sortie="Bac+5 (licence puis master renforcés), en 5 ans à l'université",
        acces="Sélection sur dossier. Le CMI se suit en parallèle d'une licence puis d'un "
        "master, avec des enseignements et des stages en plus.",
        lycee="Bac général avec les spécialités de la discipline : mathématiques, "
        "physique-chimie, SVT, NSI ou SI pour les CMI scientifiques.",
        apres="Ingénieur-expert ou doctorat.",
        passerelles="On peut quitter le CMI en gardant la licence ou le master de la même "
        "discipline.",
    ),
    "commerce": Famille(
        titre="Écoles de commerce et de management après le bac",
        sortie="Bachelor bac+3, ou programme grande école bac+5 (grade master)",
        acces="Sélection sur dossier, souvent par un concours commun post-bac (SESAME, "
        "ACCES, Ecricome Bachelor…) avec épreuves écrites et entretien. Frais de scolarité "
        "élevés dans le privé.",
        lycee="Tous bacs généraux, mathématiques ou SES appréciées ; STMG pour certains "
        "bachelors. Les langues vivantes comptent beaucoup.",
        apres="Emploi en entreprise, ou master après un bachelor.",
        passerelles="Voie principale des grandes écoles : prépa ECG ou ECT (concours bac+2). "
        "Admissions parallèles en 1re ou 2e année du programme grande école après un bac+2 "
        "ou un bac+3 (concours Passerelle, Tremplin, Ecricome Tremplin).",
        entrees=(2, 3),
        concours=True,
    ),
    "iep": Famille(
        titre="Instituts d'études politiques",
        sortie="Diplôme bac+5 (grade master), parfois un bachelor bac+3",
        acces="Concours commun du réseau des IEP ou admission propre (dossier, épreuves "
        "écrites, oral selon l'institut).",
        lycee="Bac général : HGGSP, SES, HLP ou LLCER. Très bon niveau écrit et en langues.",
        apres="Fonction publique, journalisme, entreprises, organisations internationales.",
        passerelles="Entrée possible en master (4e année) après une licence (bac+3), par "
        "concours ou sur dossier.",
        entrees=(3,),
        concours=True,
    ),
    "pass": Famille(
        titre="PASS (parcours d'accès spécifique santé)",
        sortie="Médecine (bac+9 à bac+12), pharmacie, odontologie (bac+6 et plus), "
        "maïeutique (bac+5)",
        acces="Formation de licence ouverte sur dossier, mais l'accès en 2e année de santé "
        "est très sélectif : notes de l'année puis oraux. Deux candidatures au plus sur "
        "l'ensemble des études.",
        lycee="Bac général avec SVT et physique-chimie, ou SVT et mathématiques. La "
        "physique-chimie aide beaucoup en première année.",
        apres="Études de médecine, pharmacie, odontologie, maïeutique ou kinésithérapie.",
        passerelles="En cas d'échec, poursuite en 2e année de licence (L.AS) grâce à la "
        "mineure suivie en PASS. Des passerelles existent aussi pour les titulaires d'un "
        "master ou de certains diplômes paramédicaux.",
        entrees=(3,),
        concours=True,
    ),
    "las": Famille(
        titre="Licence avec option santé (L.AS)",
        sortie="Bac+3 (licence), avec une chance d'accès aux études de santé",
        acces="Inscription en licence (droit, sciences, lettres…) avec une option santé. "
        "Les meilleurs candidats peuvent entrer en 2e année de médecine, pharmacie, "
        "odontologie ou maïeutique.",
        lycee="Les spécialités de la licence choisie ; SVT ou physique-chimie aident pour "
        "l'option santé.",
        apres="Études de santé si admis, sinon poursuite de la licence puis master.",
        passerelles="Candidature possible aux études de santé en fin de L1, L2 ou L3.",
        concours=True,
    ),
    "paramedical": Famille(
        titre="Diplômes paramédicaux",
        sortie="Bac+3 (grade licence) le plus souvent, bac+5 pour l'orthophonie",
        acces="Sélection sur dossier, parfois avec un entretien ou des épreuves (orthophonie, "
        "orthoptie). Les instituts sont rattachés à une université.",
        lycee="Bac général avec SVT et physique-chimie ou mathématiques, ou bac ST2S "
        "(très représenté en soins infirmiers) ou STL.",
        apres="Exercice en hôpital, en clinique ou en libéral. Spécialisations après "
        "quelques années (infirmier anesthésiste, de bloc, puériculture), masters.",
        passerelles="Accès possible en reprise d'études : les aides-soignants et auxiliaires de "
        "puériculture ont une voie d'accès réservée en soins infirmiers.",
    ),
    "social": Famille(
        titre="Diplômes d'État du travail social",
        sortie="Bac+3 (grade licence), en 3 ans",
        acces="Sélection sur dossier et oral de motivation.",
        lycee="Tous bacs : ST2S, SES, HGGSP ou HLP sont de bons appuis. Une expérience "
        "bénévole ou un stage auprès d'un public compte.",
        apres="Éducateur, assistant de service social, éducateur de jeunes enfants. Master ou "
        "encadrement (CAFERUIS) ensuite.",
        passerelles="Allègements pour les titulaires d'un autre diplôme du social. Accès "
        "possible par l'apprentissage ou la validation des acquis de l'expérience.",
    ),
    "art": Famille(
        titre="Art, design et spectacle vivant",
        sortie="Bac+3 (DN MADE, DNA, diplômes d'artiste) ; bac+5 dans les écoles supérieures d'art",
        acces="Dossier artistique ou portfolio, entretien, parfois épreuves pratiques ou audition.",
        lycee="Spécialité arts (arts plastiques, cinéma, musique, théâtre, danse…) ou bac STD2A "
        "pour le design. Pratique personnelle régulière indispensable.",
        apres="DNSEP ou DSAA (bac+5), master, ou exercice professionnel.",
        passerelles="Classes préparatoires publiques aux écoles d'art. Entrée en cours de "
        "cursus sur commission d'équivalence dans les écoles supérieures d'art.",
        entrees=(2, 3),
        concours=True,
    ),
    "architecture": Famille(
        titre="Architecture et paysage",
        sortie="Bac+3 (licence) puis bac+5 (diplôme d'État)",
        acces="Sélection sur dossier et entretien dans les écoles nationales supérieures "
        "d'architecture et de paysage.",
        lycee="Bac général : mathématiques et physique-chimie, ou arts, HGGSP. Bac STD2A ou "
        "STI2D possible.",
        apres="Habilitation à exercer en nom propre (HMONP) après le diplôme d'État, "
        "urbanisme, paysage.",
        passerelles="Entrée en cours de cursus après un BTS, un BUT ou une licence, sur "
        "validation des études.",
        entrees=(2, 3),
    ),
    "dcg": Famille(
        titre="DCG (diplôme de comptabilité et de gestion)",
        sortie="Bac+3 (grade licence), en 3 ans",
        acces="Sélection sur dossier, en lycée ou en école.",
        lycee="Bac STMG (gestion et finance) ou bac général avec mathématiques et SES.",
        apres="DSCG (bac+5) puis diplôme d'expertise comptable (bac+8).",
        passerelles="Dispenses d'épreuves après un BTS ou un BUT de gestion.",
        entrees=(2,),
    ),
    "veterinaire": Famille(
        titre="Écoles vétérinaires",
        sortie="Docteur vétérinaire, bac+6",
        acces="Concours post-bac commun aux quatre écoles nationales : dossier puis oraux.",
        lycee="Bac général avec SVT et physique-chimie ou mathématiques, ou bac STL ou STAV.",
        apres="Exercice vétérinaire, recherche, santé publique.",
        passerelles="La plupart des places restent ouvertes par concours après une prépa "
        "BCPST (bac+2), un BTSA ou un BUT (bac+2), ou une licence (bac+3).",
        entrees=(2, 3),
        concours=True,
    ),
    "sport": Famille(
        titre="Diplômes professionnels du sport et de l'animation",
        sortie="BPJEPS : niveau bac ; DEJEPS : bac+2",
        acces="Tests d'exigences préalables (sportifs ou techniques) puis entretien. "
        "Formation souvent en alternance.",
        lycee="Tous bacs. Une pratique sportive ou d'animation encadrée (BAFA, club) est "
        "souvent exigée.",
        apres="Éducateur sportif ou animateur, puis DEJEPS et DESJEPS pour encadrer.",
        passerelles="La licence STAPS mène aux mêmes métiers par l'université.",
    ),
    "annee-prepa": Famille(
        titre="Années préparatoires et de mise à niveau",
        sortie="Une année de transition, sans diplôme de niveau supérieur",
        acces="Sélection sur dossier. Les classes préparatoires aux études supérieures "
        "s'adressent surtout aux bacheliers boursiers ; la mise à niveau en hôtellerie aux "
        "bacheliers venus d'une autre filière.",
        lycee="Tous bacs selon la classe.",
        apres="Entrée en licence, en prépa, en BTS ou en école l'année suivante.",
        passerelles="Utile pour changer de voie ou consolider ses bases avant une formation "
        "sélective.",
    ),
    "specialisation": Famille(
        titre="Certificats de spécialisation et FCIL",
        sortie="Une année de spécialisation après un premier diplôme",
        acces="Sur dossier, souvent après un bac professionnel ou un BTS du même domaine ; "
        "beaucoup se font en apprentissage.",
        lycee="Bac professionnel ou technologique du domaine.",
        apres="Insertion directe sur un métier précis.",
        passerelles="Complément d'un bac pro ou d'un BTS plutôt que porte d'entrée.",
    ),
    "lp": Famille(
        titre="Licence professionnelle",
        sortie="Bac+3, très professionnalisant",
        acces="La plupart des licences professionnelles se préparent en un an après un bac+2. "
        "Celles listées ici s'ouvrent dès le bac, sur dossier.",
        lycee="Bac technologique ou général selon le domaine.",
        apres="Insertion professionnelle ; la poursuite en master est rare.",
        passerelles="Entrée habituelle en 3e année après un BTS, un BUT (2e année) ou une L2.",
        entrees=(2,),
    ),
    "ecole-pro": Famille(
        titre="Écoles spécialisées et titres professionnels",
        sortie="Selon la formation, souvent bac+2 ou bac+3 (titre inscrit au RNCP)",
        acces="Sélection sur dossier, tests ou entretien selon l'école. Établissements "
        "souvent privés, payants, avec de l'alternance.",
        lycee="Tous bacs selon le domaine.",
        apres="Insertion directe ; vérifier sur la fiche que le titre est bien inscrit au "
        "répertoire national (RNCP) et à quel niveau.",
        passerelles="Beaucoup de ces écoles recrutent aussi en 2e ou 3e année après un bac+1 "
        "ou un bac+2.",
        entrees=(1, 2),
    ),
}

SUITES: dict[str, tuple[str, ...]] = {
    "bts": ("lp", "licence", "but", "ingenieur", "commerce"),
    "but": ("ingenieur", "commerce", "iep"),
    "deust": ("lp", "licence"),
    "licence": ("iep", "commerce", "ingenieur", "veterinaire"),
    "licence-renforcee": ("iep", "commerce", "ingenieur"),
    "cupge": ("ingenieur", "commerce", "veterinaire"),
    "cpge": ("ingenieur", "commerce", "veterinaire", "licence"),
    "pass": ("las", "licence"),
    "las": ("pass",),
    "annee-prepa": ("licence", "cpge", "bts"),
    "dcg": ("commerce",),
    "lp": ("commerce",),
}
"""Familles où mènent une poursuite d'études ou une admission parallèle, pour l'arbre."""

NIVEAUX_SORTIE = {
    1: "Bac+1 ou moins",
    2: "Bac+2",
    3: "Bac+3",
    4: "Bac+4",
    5: "Bac+5 et plus",
}
NIVEAUX_ENTREE = {
    1: "un bac+1",
    2: "un bac+2",
    3: "un bac+3",
}
ACCES = {
    "libre": "Non sélective",
    "dossier": "Sélective sur dossier",
    "concours": "Concours ou épreuves",
}

_BAC_PLUS = re.compile(r"bac\s*\+\s*(\d)", re.I)


def _bac_plus(libelle: str) -> int | None:
    m = _BAC_PLUS.search(libelle)
    return int(m.group(1)) if m else None


def classer(type_: str, libelle: str) -> tuple[str, int | None]:
    """Famille et niveau de sortie (bac+N, None si inconnu) d'une mention."""
    lib = libelle.strip()
    n = _bac_plus(lib)
    prefixes: list[tuple[str, str, int | None]] = [
        ("BTS", "bts", 2),
        ("BUT", "but", 3),
        ("DEUST", "deust", 2),
        ("DTS", "paramedical", 3),
        ("C.M.I", "cmi", 5),
        ("CPGE", "cpge", 5),
        ("CUPGE", "cupge", 3),
        ("DN MADE", "art", 3),
        ("Diplôme National d'Art", "art", 3),
        ("Diplôme national supérieur professionnel", "art", 3),
        ("D.E Professeur", "art", 3),
        ("Formation des écoles supérieures d'art", "art", n or 3),
        ("Certificat de capacité d'Orthophoniste", "paramedical", 5),
        ("Certificat de capacité", "paramedical", 3),
        ("EA-BAC5", "architecture", 5),
        ("EA-BAC3", "architecture", 3),
        ("D-Etab - Paysagiste", "architecture", 5),
        ("BPJEPS", "sport", 1),
        ("DEJEPS", "sport", 2),
        ("CS - Encadrement secteur sportif", "sport", 1),
        ("L1 - Parcours d'Accès Spécifique Santé", "pass", 5),
        ("Classe préparatoire aux études supérieures", "annee-prepa", 1),
        ("Année préparatoire", "annee-prepa", 1),
        ("MAN ", "annee-prepa", 1),
        ("DU - Diplôme d'Université - PAREO", "annee-prepa", 1),
        ("CSA", "specialisation", 1),
        ("CS ", "specialisation", 1),
        ("FCIL", "specialisation", 1),
        ("DCG", "dcg", 3),
        ("Véto", "veterinaire", 6),
        ("LP-", "lp", 3),
        ("Cycle pluridisciplinaire", "licence-renforcee", 3),
        ("Sciences Po", "iep", 3 if "Grade Licence" in lib else 5),
    ]
    for prefixe, famille, sortie in prefixes:
        if lib.startswith(prefixe):
            return famille, sortie
    if lib.startswith("D.E"):
        return ("social" if "social" in type_ else "paramedical"), 3
    if type_ == "Etudes de santé" and lib.startswith("L1"):
        return "las", 3
    if type_ == "Licence sélective":
        return "licence-renforcee", 3
    if type_ == "Licence" or lib.startswith("L1"):
        return "licence", 3
    if "ingénieurs" in type_:
        return "ingenieur", n or 5
    if "commerce" in type_:
        return "commerce", n or 5
    # Titres d'écoles, diplômes d'établissement, formations de l'hôtellerie.
    if lib.startswith(("DSP", "DU ")):
        return "ecole-pro", n or 1
    return "ecole-pro", n


class ProfilAdmis(BaseModel):
    admis: int
    """Néo-bacheliers admis lors de la dernière session."""
    bacs: tuple[int, int, int]
    """Part d'admis issus d'un bac général, technologique, professionnel, en %."""


class Specialites(BaseModel):
    admis: int
    """Bacheliers généraux admis dont les spécialités sont connues."""
    doublettes: list[tuple[str, int]] = Field(default_factory=list)
    """Les doublettes les plus fréquentes chez ces admis, avec leur part en %."""


class MentionParcours(BaseModel):
    famille: str
    sortie: int | None = None
    acces: str = "dossier"
    """Clé de `ACCES`, d'après la sélectivité réelle des formations."""
    profil: ProfilAdmis | None = None
    specialites: Specialites | None = None


class OffreAcces(BaseModel):
    taux: int | None = None
    """Taux d'accès : part des candidats qui ont pu recevoir une proposition, en %."""
    selective: bool = True
    concours: str | None = None
    """Concours commun ou banque d'épreuves, s'il y en a un."""


class IndexParcours(BaseModel):
    genere_le: datetime
    session: str
    mentions: dict[str, MentionParcours] = Field(default_factory=dict)
    """Par libellé de mention (celui de l'index des formations)."""
    familles: dict[str, ProfilAdmis] = Field(default_factory=dict)
    """Profil des admis agrégé par famille, pour la page des parcours."""
    specialites_familles: dict[str, Specialites] = Field(default_factory=dict)
    doublettes_familles: dict[str, dict[str, int]] = Field(default_factory=dict)
    """Bacheliers généraux admis par doublette de spécialités, pour l'arbre des parcours."""
    offres: dict[str, OffreAcces] = Field(default_factory=dict)
    """Par code de formation."""


SPECIALITES_COURTES = {
    "Mathématiques Spécialité": "Maths",
    "Physique-Chimie Spécialité": "Physique-chimie",
    "Sciences de la vie et de la Terre Spécialité": "SVT",
    "Sciences Economiques et Sociales Spécialité": "SES",
    "Histoire-Géographie, Géopolitique et Sciences politiques": "HGGSP",
    "Humanités, Littérature et Philosophie": "HLP",
    "Langues, littératures et cultures étrangères et régionales": "LLCER",
    "Numérique et Sciences Informatiques": "NSI",
    "Sciences de l'ingénieur et sciences physiques": "SI",
    "Éducation physique, pratiques et culture sportives": "EPPCS",
    "Littérature et langues et cultures de l'Antiquité": "LLCA",
    "Biologie/Ecologie": "Biologie-écologie",
    "Art": "Arts",
}


def doublette(specialites: Iterable[str]) -> str:
    return " + ".join(SPECIALITES_COURTES.get(s, s) for s in specialites)


# Groupes du jeu « spécialités » où chercher chaque famille.
GROUPES_SPECIALITES = {
    "bts": ("BTS prod", "BTS serv", "BTS agri", "BTS mar"),
    "but": ("BUT prod", "BUT serv"),
    "deust": ("DEUST",),
    "cpge": ("CPGE S", "CPGE ECG", "CPGE L"),
    "cupge": ("CUPGE",),
    "licence-renforcee": ("CyPES",),
    "annee-prepa": ("ClPES",),
    "ingenieur": ("Ingé",),
    "commerce": ("Comm",),
    "art": ("Art",),
    "paramedical": ("DE san",),
    "social": ("DE soc",),
    "iep": ("ScPo",),
    "veterinaire": ("Vétérinaire",),
    "dcg": ("DCG",),
    "pass": ("PASS",),
    "las": ("Licence L.AS",),
    "cmi": ("Autres",),
    "architecture": ("Autres",),
    "sport": ("Autres", "DEUST", "Licence STAPS"),
}

# Licences dont l'intitulé diffère trop du regroupement du jeu « spécialités ».
LICENCES = {
    "Droit": "Licence Sciences juridiques",
    "Economie et gestion": "Licence Pluri Sciences économiques - Gestion",
    "Langues, littératures et civilisations étrangères et régionales": (
        "Licence Langues et littératures étrangères"
    ),
    "Langues étrangères appliquées": "Licence LEA",
    "Lettres, langues": "Licence Pluri Lettres - Langues - Sciences humaines",
    "Psychologie": "Licence Psychlogie, Sciences cognitives",
    "Administration économique et sociale": "Licence AES",
    "Information et communication": "Licence Sciences de l information et de la communication",
    "Sciences et Techniques des Activités Physiques et Sportives": "Licence STAPS",
    "Sciences de l'éducation et de la formation": "Licence Sciences de l'éducation",
    "Histoire de l'art": "Licence Arts",
    "Humanités": "Licence Pluri Lettres - Langues - Sciences humaines",
    "Lettres": "Licence Langues et littératures françaises",
    "Physique, chimie": "Licence Physique et chimie",
    "Informatique, Mathématiques": "Licence Mathématiques et informatique",
    "Mathématiques et informatique appliquées aux sciences humaines et sociales": ("Licence MASS"),
    "Sciences de la vie et de la terre": (
        "Licence Pluri Sciences de la vie, de la santé, de la terre et de l univers"
    ),
}


@dataclass
class _Cumul:
    acceptations: Counter[tuple[str, ...]]

    @property
    def total(self) -> int:
        return sum(self.acceptations.values())

    def resultat(self) -> Specialites | None:
        total = self.total
        if total < MIN_SPECIALITES:
            return None
        return Specialites(
            admis=total,
            doublettes=[
                (doublette(d), round(100 * n / total)) for d, n in self.acceptations.most_common(3)
            ],
        )


def _cumuls_specialites(lignes: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], _Cumul]:
    """(regroupement abrégé, formation) → acceptations par doublette."""
    cumuls: dict[tuple[str, str], _Cumul] = defaultdict(lambda: _Cumul(Counter()))
    for r in lignes:
        niveau = str(r.get("niveau_d_agregation"))
        groupe = str(r.get("regroupement_de_formations_abrege") or "").replace("\xa0", " ")
        formation = str(r.get("formation") or "").replace("\xa0", " ")
        if niveau == "1":
            formation = groupe  # le regroupement entier, pour les licences
        elif niveau != "2" or formation == groupe:
            continue  # une licence répète au niveau 2 la ligne de son regroupement
        cumuls[(groupe, formation)].acceptations[tuple(r.get("doublette") or ())] += int(
            r.get("acceptations") or 0
        )
    return cumuls


def _reste(libelle: str) -> str:
    for prefixe in (
        "CPGE - ",
        "BTS - ",
        "BTSA - ",
        "BTSM - ",
        "BUT - ",
        "DEUST - ",
        "CUPGE - ",
        "L1 - ",
    ):
        if libelle.startswith(prefixe):
            return libelle.removeprefix(prefixe)
    for prefixe in (
        "Classe préparatoire aux études supérieures - ",
        "Cycle pluridisciplinaire d'Études Supérieures - ",
    ):
        if libelle.startswith(prefixe):
            return libelle.removeprefix(prefixe)
    return libelle


def formation_specialites(
    famille: str, libelle: str, cles: Iterable[tuple[str, str]]
) -> tuple[str, str] | None:
    """Ligne du jeu « spécialités » qui correspond à la mention, None si rien de sûr."""
    cles = list(cles)
    reste = _reste(libelle)
    if famille in ("licence", "sport") and libelle.startswith("L1 - "):
        cible = LICENCES.get(reste) or LICENCES.get(reste.split(" : ")[0])
        groupe = cible or f"Licence {reste}"
        if (groupe, groupe) in cles:
            return (groupe, groupe)
        mots = mt._mots(reste)
        # Tous les mots de la mention dans le regroupement, le plus proche d'abord.
        candidats = [
            (len(mots & autres) / len(mots), len(mots & autres) / len(mots | autres), g)
            for g, f in cles
            if g == f and g.startswith("Licence ") and (autres := mt._mots(g[8:]))
        ]
        contenu, _, groupe = max(candidats, default=(0.0, 0.0, ""))
        return (groupe, groupe) if mots and contenu == 1 else None
    if famille in ("pass", "las", "dcg", "veterinaire"):
        groupe = GROUPES_SPECIALITES[famille][0]
        return (groupe, groupe) if (groupe, groupe) in cles else None
    groupes = GROUPES_SPECIALITES.get(famille, ())
    cible = fm.normaliser(reste)
    meilleur: tuple[int, tuple[str, str]] | None = None
    for g, f in cles:
        if g not in groupes or g == f:
            continue
        nom = fm.normaliser(f.removeprefix("ECG - ").strip('"'))
        if not nom:
            continue
        # « Innovations textiles » couvre « Innovations textiles - Option A : Structures ».
        couvre = cible == nom or cible.startswith(nom + " ") or nom == fm.normaliser(libelle)
        if couvre and (meilleur is None or len(nom) > meilleur[0]):
            meilleur = (len(nom), (g, f))
    if meilleur is None and famille in ("cmi", "sport", "architecture"):
        prefixe = {"cmi": "c m i", "sport": "bpjeps", "architecture": "architecture"}[famille]
        if fm.normaliser(libelle).startswith(prefixe):
            return next(
                ((g, f) for g, f in cles if g == "Autres" and fm.normaliser(f).startswith(prefixe)),
                None,
            )
    return meilleur[1] if meilleur else None


def _profil(cumul: Counter[str]) -> ProfilAdmis | None:
    admis = cumul["bg"] + cumul["bt"] + cumul["bp"]
    if admis < MIN_ADMIS:
        return None
    parts = [round(100 * cumul[k] / admis) for k in ("bg", "bt", "bp")]
    return ProfilAdmis(admis=admis, bacs=(parts[0], parts[1], parts[2]))


def _entier(valeur: Any) -> int:
    try:
        return int(float(valeur))
    except (TypeError, ValueError):
        return 0


def construire(
    index: fm.IndexFormations,
    voeux: Iterable[Mapping[str, Any]],
    specialites: Iterable[Mapping[str, Any]],
    session: str = "",
) -> IndexParcours:
    par_code = {str(r.get("cod_aff_form")): r for r in voeux}
    cumuls_spe = _cumuls_specialites(specialites)

    offres: dict[str, OffreAcces] = {}
    bacs_mention: dict[int, Counter[str]] = defaultdict(Counter)
    selectives: dict[int, Counter[bool]] = defaultdict(Counter)
    concours: dict[int, int] = defaultdict(int)
    for liste in index.offres.values():
        for o in liste:
            r = par_code.get(o.code)
            if r is None or o.code in offres:
                continue
            taux = r.get("taux_acces_ens")
            selective = r.get("select_form") != "formation non sélective"
            offres[o.code] = OffreAcces(
                taux=None if taux is None else round(float(taux)),
                selective=selective,
                concours=r.get("detail_forma2") or None,
            )
            for k in ("bg", "bt", "bp"):
                bacs_mention[o.mention][k] += _entier(r.get(f"acc_{k}"))
            selectives[o.mention][selective] += 1
            if r.get("detail_forma2"):
                concours[o.mention] += 1

    mentions: dict[str, MentionParcours] = {}
    bacs_famille: dict[str, Counter[str]] = defaultdict(Counter)
    spe_famille: dict[str, _Cumul] = defaultdict(lambda: _Cumul(Counter()))
    deja: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for i, m in enumerate(index.mentions):
        famille, sortie = classer(index.types[m.type], m.libelle)
        f = FAMILLES[famille]
        sel = selectives.get(i)
        if concours.get(i) or (f.concours and famille not in ("cpge", "cupge", "las")):
            acces = "concours"
        elif (sel and sel[False] > sel[True]) or (sel is None and famille in ("licence", "las")):
            acces = "libre"
        else:
            acces = "dossier"
        cle = formation_specialites(famille, m.libelle, cumuls_spe)
        spe = cumuls_spe[cle].resultat() if cle else None
        if cle and cle not in deja[famille]:
            deja[famille].add(cle)
            spe_famille[famille].acceptations.update(cumuls_spe[cle].acceptations)
        bacs_famille[famille].update(bacs_mention.get(i, Counter()))
        mentions[m.libelle] = MentionParcours(
            famille=famille,
            sortie=sortie,
            acces=acces,
            profil=_profil(bacs_mention.get(i, Counter())),
            specialites=spe,
        )
    return IndexParcours(
        genere_le=datetime.now(UTC).replace(microsecond=0),
        session=session,
        mentions=mentions,
        familles={k: p for k, c in sorted(bacs_famille.items()) if (p := _profil(c))},
        specialites_familles={k: s for k, c in sorted(spe_famille.items()) if (s := c.resultat())},
        doublettes_familles={
            k: {doublette(d): n for d, n in c.acceptations.most_common() if n > 0}
            for k, c in sorted(spe_famille.items())
            if c.total >= MIN_SPECIALITES
        },
        offres=dict(sorted(offres.items())),
    )


def charger(chemin: Path) -> IndexParcours:
    return IndexParcours.model_validate_json(chemin.read_text(encoding="utf-8"))


def _client(source: str, base_url: str) -> SourceClient:
    # Les deux portails coupent souvent la connexion : beaucoup de tentatives.
    return SourceClient(
        source,
        base_url,
        retry=RetryPolicy(max_attempts=25),
        timeout_s=300,
        user_agent=get_settings().http_user_agent,
    )


async def _telecharger() -> tuple[list[Any], list[Any]]:
    async with _client("voeux-formations", "https://data.education.gouv.fr/api/explore/v2.1") as c:
        voeux = await c.get_json(VOEUX, {"select": VOEUX_CHAMPS})
    async with _client(
        "specialites", "https://data.enseignementsup-recherche.gouv.fr/api/explore/v2.1"
    ) as c:
        specialites = await c.get_json(SPECIALITES)
    return voeux, specialites


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--formations", type=Path, default=Path("web/data/formations.json"))
    parser.add_argument("--sortie", type=Path, default=Path("web/data/parcours.json"))
    parser.add_argument(
        "--depuis", type=Path, help="dossier avec voeux.json et specialites.json déjà téléchargés"
    )
    args = parser.parse_args()
    if args.depuis:
        voeux = json.loads((args.depuis / "voeux.json").read_text(encoding="utf-8"))
        specialites = json.loads((args.depuis / "specialites.json").read_text(encoding="utf-8"))
    else:
        voeux, specialites = asyncio.run(_telecharger())
    session = next((str(r["session"]) for r in voeux if r.get("session")), "")
    index = fm.charger(args.formations)
    resultat = construire(index, voeux, specialites, session)
    args.sortie.write_text(resultat.model_dump_json(exclude_defaults=True), encoding="utf-8")
    avec_spe = sum(1 for m in resultat.mentions.values() if m.specialites)
    avec_profil = sum(1 for m in resultat.mentions.values() if m.profil)
    print(
        f"{len(resultat.mentions)} formations classées ; {avec_profil} avec le profil des admis, "
        f"{avec_spe} avec leurs spécialités ; {len(resultat.offres)} offres avec taux d'accès"
    )


if __name__ == "__main__":
    main()
