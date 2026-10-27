"""Chemins vers les métiers dont l'accès passe par un diplôme ou un examen après la licence.

Pour ces métiers (avocat, médecin, ingénieur...), le rattachement RNCP des formations
post-bac ne suffit pas : le diplôme qui ouvre le métier vient après (master, examen,
école). On décrit donc ici, à rebours, plusieurs voies possibles par métier, chacune en
étapes datées (Bac+1, Bac+3...). Les formations citées renvoient aux mentions de
`web/data/formations.json` :

- un libellé exact (« L1 - Droit ») ;
- un préfixe suivi de « * » (« CPGE - ECG* ») ;
- une famille de `parcours.FAMILLES` (« famille:las »).

Ce sont des repères généraux, établis d'après les règles nationales des diplômes et des
concours ; le calendrier de certaines réformes (concours de l'enseignement, maïeutique)
est rappelé dans le texte.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Etape:
    niveau: str
    """« Bac+1 à Bac+3 », « Bac+5 »..."""
    titre: str
    texte: str = ""
    formations: tuple[str, ...] = ()
    """Mentions proposées dans les villes du site, pour cette étape."""


@dataclass(frozen=True)
class Voie:
    titre: str
    etapes: tuple[Etape, ...]
    resume: str = ""


@dataclass(frozen=True)
class MetierCible:
    id: str
    titre: str
    lycee: str
    """Bac et spécialités conseillés."""
    voies: tuple[Voie, ...]
    mots: tuple[str, ...] = ()
    """Autres façons de chercher le métier."""
    romes: tuple[str, ...] = ()
    metier: str = ""
    """Ce qui se passe à l'arrivée : statut, premier poste, spécialisation."""
    sources: tuple[str, ...] = field(default=())
    depart: str = "Lycée"
    """Première étape du chemin : « Lycée », ou « Après la 3e » pour les CAP et bacs pro."""


# Étapes communes à plusieurs voies.
_MASTER_DROIT = Etape(
    "Bac+4 et Bac+5",
    "Master de droit des affaires",
    "Sélection sur dossier à l'entrée du M1. Un M2 de droit des affaires, fiscal, bancaire "
    "ou social spécialise et ouvre les premiers stages en cabinet.",
)
_CRFPA = Etape(
    "Bac+4 ou Bac+5",
    "Examen d'entrée à l'école des avocats",
    "Possible dès le M1 validé ; il se prépare le plus souvent dans l'institut d'études "
    "judiciaires (IEJ) de l'université. Trois tentatives au plus.",
)
_ECOLE_AVOCATS = Etape(
    "Bac+6 à Bac+7",
    "École des avocats (18 mois) et CAPA",
    "Cours, stage en cabinet et projet personnel, puis certificat d'aptitude à la profession "
    "d'avocat (CAPA) et prestation de serment.",
)
_PASS = Etape(
    "Bac+1",
    "PASS : parcours d'accès spécifique santé",
    "Une année de santé avec une mineure d'une autre discipline. L'entrée en 2e année se fait "
    "sur les notes puis des oraux ; deux candidatures au plus sur l'ensemble des études.",
    ("famille:pass",),
)
_LAS = Etape(
    "Bac+1 à Bac+3",
    "Licence avec option santé (L.AS)",
    "Une licence d'une autre discipline (droit, sciences, lettres…) avec une option santé. "
    "Candidature aux études de santé en fin de L1, L2 ou L3.",
    ("famille:las",),
)
_INGE_ECOLE = Etape(
    "Bac+3 à Bac+5",
    "Cycle ingénieur en école (3 ans)",
    "Stages en entreprise, semestre à l'étranger souvent obligatoire, spécialisation en "
    "dernière année. Diplôme d'ingénieur (grade master).",
)
_LICENCE_DISCIPLINE = (
    "L1 - Mathématiques",
    "L1 - Lettres",
    "L1 - Histoire",
    "L1 - Langues, littératures et civilisations étrangères et régionales",
    "L1 - Physique, chimie",
    "L1 - Sciences de la vie",
)
_REFORME_PROF = (
    "La réforme engagée en 2025 place le concours en fin de licence, suivi de deux années de "
    "formation rémunérée en master ; vérifiez le calendrier en vigueur l'année de votre "
    "candidature."
)

_METIERS_SUP: tuple[MetierCible, ...] = (
    MetierCible(
        id="avocat",
        titre="Avocat ou avocate",
        mots=("avocat d'affaires", "droit des affaires", "droit des entreprises", "barreau"),
        romes=("K1903",),
        lycee="Bac général. Aucune spécialité n'est exigée pour le droit, mais SES, HGGSP ou HLP, "
        "un bon niveau à l'écrit et en anglais sont des atouts.",
        metier="Inscription au barreau, le plus souvent comme collaborateur d'un cabinet avant "
        "de s'associer ou de s'installer. La spécialisation (droit des affaires, fiscal, "
        "social…) se construit par le master et les premières années d'exercice.",
        voies=(
            Voie(
                "Licence de droit, puis master",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence de droit",
                        "Non sélective. En L3, choisir les matières de droit des affaires "
                        "(sociétés, contrats, fiscalité) prépare l'entrée en master.",
                        ("L1 - Droit",),
                    ),
                    _MASTER_DROIT,
                    _CRFPA,
                    _ECOLE_AVOCATS,
                ),
                "La voie la plus courante.",
            ),
            Voie(
                "Double licence droit-économie ou droit-gestion",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Double licence ou licence sélective de droit",
                        "Sélective, plus exigeante, très appréciée des masters de droit des "
                        "affaires et des cabinets.",
                        (
                            "L1 - Droit, Economie",
                            "L1 - Droit, Sciences et Innovation",
                            "L1 - Droit français - Droit étranger",
                            "L1 - Droit, Informatique",
                        ),
                    ),
                    _MASTER_DROIT,
                    _CRFPA,
                    _ECOLE_AVOCATS,
                ),
            ),
            Voie(
                "Institut d'études politiques",
                (
                    Etape(
                        "Bac+1 à Bac+5",
                        "Institut d'études politiques",
                        "Concours ou dossier. En master, choisir une spécialité de droit "
                        "économique ou de droit des affaires, qui permet de se présenter à "
                        "l'examen des avocats.",
                        ("Sciences Po*",),
                    ),
                    _CRFPA,
                    _ECOLE_AVOCATS,
                ),
            ),
            Voie(
                "Passerelle : juriste d'entreprise, puis avocat",
                (
                    Etape(
                        "Bac+5",
                        "Master de droit, puis poste de juriste d'entreprise",
                        "Une des voies précédentes jusqu'au master, puis un poste en "
                        "direction juridique.",
                        ("L1 - Droit",),
                    ),
                    Etape(
                        "Après 8 ans d'exercice",
                        "Accès au barreau sans examen",
                        "Les juristes d'entreprise qui justifient de huit ans de pratique "
                        "professionnelle peuvent devenir avocats sans passer l'examen ni "
                        "l'école, après un examen de déontologie.",
                    ),
                ),
            ),
        ),
    ),
    MetierCible(
        id="magistrat",
        titre="Magistrat ou magistrate (juge, procureur)",
        mots=("juge", "procureur", "école nationale de la magistrature"),
        lycee="Bac général : SES, HGGSP, HLP. L'écrit et la culture générale comptent beaucoup.",
        metier="Premier poste de juge ou de substitut du procureur, choisi selon le rang de "
        "sortie de l'école.",
        voies=(
            Voie(
                "Droit à l'université, puis concours",
                (
                    Etape("Bac+1 à Bac+3", "Licence de droit", "Non sélective.", ("L1 - Droit",)),
                    Etape(
                        "Bac+4 à Bac+5",
                        "Master de droit et préparation du concours",
                        "Le premier concours de l'École nationale de la magistrature demande "
                        "au moins un bac+4. Il se prépare en IEJ ou en classe préparatoire.",
                    ),
                    Etape(
                        "Bac+5 à Bac+7",
                        "École nationale de la magistrature (31 mois)",
                        "Scolarité rémunérée à Bordeaux, puis stages en juridiction.",
                    ),
                ),
            ),
            Voie(
                "Institut d'études politiques, puis concours",
                (
                    Etape(
                        "Bac+1 à Bac+5",
                        "Institut d'études politiques",
                        "Concours ou dossier ; certains IEP ont une préparation au concours de "
                        "la magistrature.",
                        ("Sciences Po*",),
                    ),
                    Etape(
                        "Bac+5 à Bac+7",
                        "Concours, puis École nationale de la magistrature",
                        "31 mois de formation rémunérée.",
                    ),
                ),
            ),
        ),
    ),
    MetierCible(
        id="notaire",
        titre="Notaire",
        mots=("office notarial", "droit notarial"),
        lycee="Bac général : SES, HGGSP, mathématiques utiles pour la fiscalité.",
        metier="Notaire salarié dans un office, puis associé ou titulaire d'un office.",
        voies=(
            Voie(
                "Droit à l'université",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence de droit",
                        "Non sélective. Droit civil, droit de la famille et droit des biens "
                        "sont au cœur du métier.",
                        ("L1 - Droit",),
                    ),
                    Etape(
                        "Bac+4 à Bac+5",
                        "Master de droit notarial",
                        "Sélection à l'entrée du M1.",
                    ),
                    Etape(
                        "Bac+6 à Bac+7",
                        "Formation professionnelle en office (2 ans)",
                        "Alternance en office notarial pour obtenir le diplôme de notaire.",
                    ),
                ),
            ),
        ),
    ),
    MetierCible(
        id="expert-comptable",
        titre="Expert-comptable",
        mots=("comptable", "commissaire aux comptes", "audit"),
        romes=("M1202",),
        lycee="Bac STMG (gestion et finance) ou bac général avec mathématiques et SES.",
        metier="Expert-comptable inscrit à l'Ordre, en cabinet ou à son compte ; la même voie "
        "ouvre le commissariat aux comptes.",
        voies=(
            Voie(
                "Filière d'expertise comptable",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "DCG : diplôme de comptabilité et de gestion",
                        "En lycée, en école ou en alternance.",
                        ("famille:dcg",),
                    ),
                    Etape(
                        "Bac+4 à Bac+5",
                        "DSCG : diplôme supérieur de comptabilité et de gestion",
                        "",
                    ),
                    Etape(
                        "Bac+6 à Bac+8",
                        "Stage de 3 ans et diplôme d'expertise comptable (DEC)",
                        "Stage rémunéré en cabinet, puis épreuves du DEC.",
                    ),
                ),
            ),
            Voie(
                "BTS ou BUT de gestion, puis la filière",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "BTS Comptabilité et gestion ou BUT GEA",
                        "Ils donnent des dispenses d'épreuves du DCG.",
                        (
                            "BTS - Comptabilité et gestion",
                            "BUT - Gestion des entreprises et des administrations",
                        ),
                    ),
                    Etape("Bac+3", "DCG", "Passé en un an grâce aux dispenses, souvent."),
                    Etape("Bac+4 à Bac+8", "DSCG, stage de 3 ans et DEC", ""),
                ),
            ),
            Voie(
                "Université : master comptabilité, contrôle, audit",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence de gestion ou d'économie-gestion",
                        "",
                        ("L1 - Gestion", "L1 - Economie et gestion"),
                    ),
                    Etape(
                        "Bac+4 à Bac+5",
                        "Master CCA (comptabilité, contrôle, audit)",
                        "Il dispense d'une partie des épreuves du DSCG.",
                    ),
                    Etape("Bac+6 à Bac+8", "Stage de 3 ans et DEC", ""),
                ),
            ),
        ),
    ),
    MetierCible(
        id="medecin",
        titre="Médecin",
        mots=("docteur", "médecine", "généraliste", "chirurgien"),
        lycee="Bac général avec SVT et physique-chimie, ou SVT et mathématiques.",
        metier="Diplôme d'État de docteur en médecine après la thèse ; exercice en libéral, à "
        "l'hôpital ou en centre de santé selon la spécialité.",
        voies=(
            Voie(
                "PASS",
                (
                    _PASS,
                    Etape(
                        "Bac+2 à Bac+6",
                        "Études de médecine (1er et 2e cycles)",
                        "Stages hospitaliers dès la 4e année ; épreuves nationales en fin de "
                        "6e année qui fixent la spécialité et la ville d'internat.",
                    ),
                    Etape(
                        "Bac+7 à Bac+12",
                        "Internat (3e cycle) et thèse",
                        "De 4 ans en médecine générale à 6 ans selon la spécialité.",
                    ),
                ),
            ),
            Voie(
                "L.AS",
                (
                    _LAS,
                    Etape("Bac+2 à Bac+6", "Études de médecine (1er et 2e cycles)", ""),
                    Etape("Bac+7 à Bac+12", "Internat et thèse", ""),
                ),
            ),
            Voie(
                "Passerelle",
                (
                    Etape(
                        "Après un master, un doctorat ou une école",
                        "Admission directe en 2e ou 3e année",
                        "Sur dossier et entretien, pour quelques places : titulaires d'un "
                        "master, d'un doctorat, d'un diplôme d'ingénieur ou de certains "
                        "diplômes paramédicaux avec expérience.",
                    ),
                ),
            ),
        ),
    ),
    MetierCible(
        id="pharmacien",
        titre="Pharmacien ou pharmacienne",
        mots=("pharmacie", "officine"),
        romes=("J1307",),
        lycee="Bac général avec physique-chimie et SVT (la chimie compte beaucoup).",
        metier="Diplôme d'État de docteur en pharmacie : officine, industrie, biologie médicale "
        "ou hôpital (ces deux derniers après l'internat).",
        voies=(
            Voie(
                "PASS ou L.AS",
                (
                    Etape(
                        "Bac+1",
                        "PASS ou licence avec option santé",
                        "Admission en 2e année de pharmacie sur notes puis oraux.",
                        ("famille:pass", "famille:las"),
                    ),
                    Etape(
                        "Bac+2 à Bac+6",
                        "Études de pharmacie",
                        "Six ans pour l'officine et l'industrie, avec stages.",
                    ),
                    Etape(
                        "Bac+7 à Bac+9",
                        "Internat (option)",
                        "Pour la biologie médicale et la pharmacie hospitalière.",
                    ),
                ),
            ),
        ),
    ),
    MetierCible(
        id="sage-femme",
        titre="Sage-femme",
        mots=("maïeutique", "maieuticien"),
        lycee="Bac général avec SVT et physique-chimie.",
        metier="Exercice à l'hôpital, en clinique ou en libéral.",
        voies=(
            Voie(
                "PASS ou L.AS",
                (
                    Etape(
                        "Bac+1",
                        "PASS ou licence avec option santé",
                        "Admission en maïeutique sur notes puis oraux.",
                        ("famille:pass", "famille:las"),
                    ),
                    Etape(
                        "Bac+2 à Bac+6",
                        "École de maïeutique",
                        "La réforme de 2024 allonge la formation à six ans au total, avec un "
                        "diplôme d'État de docteur en maïeutique.",
                    ),
                ),
            ),
        ),
    ),
    MetierCible(
        id="kinesitherapeute",
        titre="Masseur-kinésithérapeute",
        mots=("kiné", "kinésithérapie"),
        lycee="Bac général avec SVT et physique-chimie ; une pratique sportive est un plus.",
        metier="Diplôme d'État (grade master) ; exercice surtout en libéral.",
        voies=(
            Voie(
                "PASS ou L.AS",
                (
                    Etape(
                        "Bac+1",
                        "PASS ou licence avec option santé",
                        "La plupart des instituts recrutent par cette année.",
                        ("famille:pass", "famille:las"),
                    ),
                    Etape("Bac+2 à Bac+5", "Institut de kinésithérapie (4 ans)", ""),
                ),
            ),
            Voie(
                "Licence STAPS ou de sciences",
                (
                    Etape(
                        "Bac+1",
                        "Première année de STAPS ou de sciences",
                        "Certains instituts réservent des places à ces licences : regardez "
                        "les modalités de l'institut visé.",
                        (
                            "L1 - Sciences et Techniques des Activités Physiques et Sportives",
                            "L1 - Sciences de la vie",
                        ),
                    ),
                    Etape("Bac+2 à Bac+5", "Institut de kinésithérapie (4 ans)", ""),
                ),
            ),
        ),
    ),
    MetierCible(
        id="infirmier",
        titre="Infirmier ou infirmière",
        mots=("IFSI", "soins infirmiers"),
        romes=("J1506",),
        lycee="Tous bacs : ST2S très représenté ; en bac général, SVT et physique-chimie ou SES.",
        metier="Exercice à l'hôpital, en clinique, à domicile ou en libéral ; spécialisations "
        "possibles ensuite (anesthésie, bloc opératoire, puériculture, pratique avancée).",
        voies=(
            Voie(
                "Institut de formation en soins infirmiers",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Diplôme d'État d'infirmier (3 ans)",
                        "Sélection sur dossier ; moitié cours, moitié stages. Grade licence.",
                        ("D.E Infirmier",),
                    ),
                ),
            ),
            Voie(
                "Reprise d'études",
                (
                    Etape(
                        "Après 3 ans d'exercice",
                        "Aide-soignant, puis infirmier",
                        "Les aides-soignants et auxiliaires de puériculture expérimentés ont "
                        "une voie d'accès réservée en institut.",
                    ),
                ),
            ),
        ),
    ),
    MetierCible(
        id="veterinaire",
        titre="Vétérinaire",
        mots=("véto", "vétérinaire"),
        lycee="Bac général avec SVT et physique-chimie ou mathématiques, ou bac STL ou STAV.",
        metier="Docteur vétérinaire : clinique des animaux de compagnie ou d'élevage, santé "
        "publique, recherche.",
        voies=(
            Voie(
                "Concours après le bac",
                (
                    Etape(
                        "Bac+1 à Bac+6",
                        "École nationale vétérinaire (6 ans)",
                        "Dossier puis oraux, commun aux quatre écoles.",
                        ("famille:veterinaire",),
                    ),
                ),
            ),
            Voie(
                "Prépa BCPST, puis concours",
                (
                    Etape(
                        "Bac+1 à Bac+2",
                        "Classe préparatoire BCPST",
                        "",
                        ("CPGE - BCPST",),
                    ),
                    Etape("Bac+3 à Bac+7", "École nationale vétérinaire (5 ans)", ""),
                ),
            ),
            Voie(
                "Licence, BTSA ou BUT, puis concours",
                (
                    Etape(
                        "Bac+2 à Bac+3",
                        "Licence de sciences de la vie, BTSA ou BUT de biologie",
                        "Des concours sont réservés aux étudiants de licence et aux "
                        "diplômés de BTSA, BTS ou BUT.",
                        (
                            "L1 - Sciences de la vie",
                            "BTSA - Analyses biologiques, biotechnologiques, agricoles et "
                            "environnementales",
                            "BUT - Génie biologique*",
                        ),
                    ),
                    Etape("Puis 5 ans", "École nationale vétérinaire", ""),
                ),
            ),
        ),
    ),
    MetierCible(
        id="ingenieur",
        titre="Ingénieur ou ingénieure",
        mots=("ingénieur", "école d'ingénieurs"),
        lycee="Bac général avec mathématiques et physique-chimie, ou mathématiques et SI ou "
        "NSI ; mathématiques expertes recommandées. STI2D ou STL ouvrent les prépas TSI, TPC "
        "et des BUT.",
        metier="Diplôme d'ingénieur (bac+5, grade master) : conception, production, conseil, "
        "recherche selon la spécialité de l'école.",
        voies=(
            Voie(
                "Prépa, puis concours",
                (
                    Etape(
                        "Bac+1 à Bac+2",
                        "Classe préparatoire scientifique",
                        "Concours en fin de 2e année.",
                        ("CPGE - MPSI", "CPGE - PCSI", "CPGE - PTSI", "CPGE - MP2I", "CPGE - TSI"),
                    ),
                    _INGE_ECOLE,
                ),
            ),
            Voie(
                "École d'ingénieurs après le bac",
                (
                    Etape(
                        "Bac+1 à Bac+5",
                        "Prépa intégrée, puis cycle ingénieur",
                        "Concours commun post-bac ou dossier ; cinq ans dans la même école ou "
                        "le même réseau.",
                        ("Formation d'ingénieur Bac + 5", "famille:cmi"),
                    ),
                ),
            ),
            Voie(
                "BUT, puis admission sur titre",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "BUT industriel ou informatique",
                        "Après la 2e ou la 3e année, admission sur dossier en cycle ingénieur.",
                        (
                            "BUT - Génie électrique et informatique industrielle",
                            "BUT - Génie mécanique et productique",
                            "BUT - Informatique",
                            "BUT - Mesures physiques",
                            "BUT - Génie civil - Construction durable",
                        ),
                    ),
                    _INGE_ECOLE,
                ),
            ),
            Voie(
                "Université : licence ou prépa intégrée",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence scientifique ou CUPGE",
                        "Admission sur titre en école après la L2 ou la L3.",
                        ("famille:cupge", "L1 - Mathématiques", "L1 - Physique, chimie"),
                    ),
                    _INGE_ECOLE,
                ),
            ),
            Voie(
                "BTS, puis prépa ATS",
                (
                    Etape(
                        "Bac+1 à Bac+2",
                        "BTS industriel",
                        "Puis une année de prépa ATS qui prépare au concours réservé.",
                        ("famille:bts",),
                    ),
                    _INGE_ECOLE,
                ),
            ),
        ),
    ),
    MetierCible(
        id="architecte",
        titre="Architecte",
        mots=("architecture",),
        romes=("F1101",),
        lycee="Bac général : mathématiques et physique-chimie, ou arts, HGGSP. STD2A et STI2D "
        "possibles. Le dossier artistique et la culture comptent.",
        metier="Pour signer des projets en son nom : habilitation (HMONP), puis inscription à "
        "l'Ordre. Sinon architecte salarié en agence ou en collectivité.",
        voies=(
            Voie(
                "École nationale supérieure d'architecture",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence d'architecture (DEEA)",
                        "Dossier et entretien.",
                        ("EA-BAC5 - Architecture", "EA-BAC5 - Bicursus Architecture Ingénieur"),
                    ),
                    Etape("Bac+4 à Bac+5", "Diplôme d'État d'architecte", ""),
                    Etape(
                        "Bac+6",
                        "HMONP : habilitation à exercer en son nom (1 an)",
                        "En agence, avec une formation à l'école.",
                    ),
                ),
            ),
            Voie(
                "BTS, BUT ou licence, puis école en cours de cursus",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "BTS du bâtiment, BUT génie civil ou licence",
                        "Admission en 2e ou 3e année d'école sur validation des études.",
                        ("BTS - Bâtiment", "BUT - Génie civil - Construction durable"),
                    ),
                    Etape("Puis 3 à 4 ans", "École d'architecture et HMONP", ""),
                ),
            ),
        ),
    ),
    MetierCible(
        id="professeur-des-ecoles",
        titre="Professeur ou professeure des écoles",
        mots=("instituteur", "professeur des écoles", "enseignant primaire", "CRPE"),
        romes=("K2106",),
        lycee="Bac général, toutes spécialités : le concours vérifie surtout le français et les "
        "mathématiques.",
        metier="Fonctionnaire de l'Éducation nationale, en maternelle et en élémentaire.",
        voies=(
            Voie(
                "Licence préparant au professorat",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence pluridisciplinaire « professorat des écoles »",
                        "Parcours conçu pour le concours, souvent en lien avec un lycée. "
                        + _REFORME_PROF,
                        ("L1 - Professorat des Ecoles",),
                    ),
                    Etape(
                        "Bac+4 à Bac+5",
                        "Concours, puis formation en master",
                        "Stages en classe, titularisation à l'issue.",
                    ),
                ),
            ),
            Voie(
                "Une autre licence",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence de sciences de l'éducation ou disciplinaire",
                        _REFORME_PROF,
                        ("L1 - Sciences de l'éducation et de la formation", *_LICENCE_DISCIPLINE),
                    ),
                    Etape("Bac+4 à Bac+5", "Concours, puis formation en master", ""),
                ),
            ),
        ),
    ),
    MetierCible(
        id="professeur",
        titre="Professeur ou professeure de collège ou de lycée",
        mots=("CAPES", "enseignant", "agrégation"),
        romes=("K2107",),
        lycee="Bac général avec les spécialités de la matière que l'on veut enseigner.",
        metier="Professeur certifié ; l'agrégation, plus sélective, se prépare ensuite.",
        voies=(
            Voie(
                "Licence de la matière enseignée",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence disciplinaire",
                        _REFORME_PROF,
                        _LICENCE_DISCIPLINE,
                    ),
                    Etape(
                        "Bac+4 à Bac+5",
                        "Concours (CAPES, CAPET, CAPLP…), puis formation en master",
                        "",
                    ),
                ),
            ),
        ),
    ),
    MetierCible(
        id="psychologue",
        titre="Psychologue",
        mots=("psychologie", "psy"),
        romes=("K1104",),
        lycee="Bac général : SES, SVT ou mathématiques (les statistiques sont au programme).",
        metier="Titre de psychologue après le master et un stage professionnel ; hôpital, "
        "éducation, entreprise ou libéral.",
        voies=(
            Voie(
                "Psychologie à l'université",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence de psychologie",
                        "Non sélective, mais très demandée.",
                        ("L1 - Psychologie", "L1 - Sciences cognitives"),
                    ),
                    Etape(
                        "Bac+4 à Bac+5",
                        "Master de psychologie",
                        "Sélection à l'entrée du M1 ; stage d'au moins 500 heures.",
                    ),
                ),
            ),
        ),
    ),
    MetierCible(
        id="journaliste",
        titre="Journaliste",
        mots=("journalisme", "reporter"),
        romes=("E1106",),
        lycee="Bac général : HGGSP, SES, HLP, langues. Lire, écrire et s'informer beaucoup.",
        metier="Rédactions de presse écrite, radio, télévision ou web, souvent en pige au début.",
        voies=(
            Voie(
                "Licence, puis école de journalisme reconnue",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "Licence d'histoire, science politique, lettres ou information",
                        "",
                        (
                            "L1 - Histoire",
                            "L1 - Science politique",
                            "L1 - Lettres",
                            "L1 - Information et communication",
                        ),
                    ),
                    Etape(
                        "Bac+4 à Bac+5",
                        "École ou master de journalisme reconnu par la profession",
                        "Concours très sélectif ; stages en rédaction.",
                    ),
                ),
            ),
            Voie(
                "BUT journalisme",
                (
                    Etape(
                        "Bac+1 à Bac+3",
                        "BUT information-communication, parcours journalisme",
                        "Certains sont reconnus par la profession.",
                        ("BUT - Information communication Parcours journalisme",),
                    ),
                ),
            ),
            Voie(
                "Institut d'études politiques",
                (
                    Etape(
                        "Bac+1 à Bac+5",
                        "IEP, puis école ou master de journalisme",
                        "",
                        ("Sciences Po*",),
                    ),
                ),
            ),
        ),
    ),
)


# Métiers de l'artisanat, du bâtiment, de la route et du soin : les diplômes d'accès (CAP,
# bac pro, brevet professionnel, titre professionnel) se préparent avant ou sans le bac et
# ne figurent pas dans les formations post-bac du site ; seuls les BTS de poursuite y sont.
_APRES_3E = (
    "Après la 3e, en lycée professionnel ou en apprentissage dans un CFA (contrat avec un "
    "employeur, formation rémunérée). Pas de spécialités à choisir : les stages en entreprise "
    "et la motivation comptent le plus. Avec un bac, un CAP se prépare aussi en un an."
)


def _cap(nom: str, texte: str = "") -> Etape:
    return Etape(
        "Après la 3e · 2 ans",
        f"CAP {nom}",
        texte
        or "En lycée professionnel ou en apprentissage. En un an pour qui a déjà un CAP, "
        "un bac ou plus.",
    )


def _bac_pro(nom: str, texte: str = "") -> Etape:
    return Etape(
        "Après la 3e · 3 ans",
        f"Bac pro {nom}",
        texte
        or "En lycée professionnel ou en apprentissage. Il mène à l'emploi ou à un BTS du "
        "même domaine.",
    )


def _bp(nom: str, texte: str = "") -> Etape:
    return Etape(
        "Après le CAP · 2 ans",
        f"Brevet professionnel (BP) {nom}",
        texte
        or "En apprentissage. Il approfondit le métier et prépare à encadrer une équipe ou "
        "à reprendre une entreprise.",
    )


def _bts(titre: str, formations: tuple[str, ...], texte: str = "") -> Etape:
    return Etape(
        "Après le bac · 2 ans",
        titre,
        texte
        or "Sur dossier, souvent en apprentissage ; des places sont réservées aux bacs pro. "
        "Il ouvre les postes de technicien, de chef d'équipe ou de chef de chantier.",
        formations,
    )


def _titre_pro(nom: str, texte: str = "") -> Etape:
    return Etape(
        "Dès 18 ans · 6 à 12 mois",
        f"Titre professionnel {nom}",
        texte
        or "Délivré par le ministère du Travail, en formation continue ou en alternance : "
        "la voie la plus courante pour se reconvertir.",
    )


def _metier_pro(
    id: str,
    titre: str,
    romes: tuple[str, ...],
    mots: tuple[str, ...],
    metier: str,
    voies: tuple[Voie, ...],
    lycee: str = _APRES_3E,
    depart: str = "Après la 3e",
) -> MetierCible:
    return MetierCible(
        id=id,
        titre=titre,
        lycee=lycee,
        voies=voies,
        mots=mots,
        romes=romes,
        metier=metier,
        depart=depart,
    )


_REPRISE = "La voie de la reconversion."

_METIERS_PRO: tuple[MetierCible, ...] = (
    _metier_pro(
        "plombier",
        "Plombier ou plombière chauffagiste",
        ("F1603",),
        ("plombier", "chauffagiste", "sanitaire", "chauffage", "climatisation", "pompe à chaleur"),
        "Salarié d'une entreprise du bâtiment, puis souvent artisan à son compte. Les énergies "
        "renouvelables (pompes à chaleur, solaire) recrutent beaucoup.",
        (
            Voie(
                "CAP, puis brevet professionnel",
                (
                    _cap(
                        "Monteur en installations sanitaires",
                        "Ou CAP Monteur en installations thermiques pour le chauffage. En lycée "
                        "professionnel ou en apprentissage.",
                    ),
                    _bp("Monteur en installations du génie climatique et sanitaire"),
                ),
                "La voie la plus courante, souvent en apprentissage.",
            ),
            Voie(
                "Bac pro, puis BTS",
                (
                    _bac_pro("Installateur en chauffage, climatisation et énergies renouvelables"),
                    _bts(
                        "BTS Fluides, énergies, domotique",
                        ("BTS - Fluide, énergie, domotique*",),
                    ),
                ),
            ),
            Voie(
                "Titre professionnel",
                (_titre_pro("Installateur en thermique et sanitaire"),),
                _REPRISE,
            ),
        ),
    ),
    _metier_pro(
        "electricien",
        "Électricien ou électricienne",
        ("F1602",),
        ("electricien", "électricité", "domotique", "câblage"),
        "Salarié d'une entreprise du bâtiment ou de l'industrie, puis chef d'équipe ou artisan. "
        "Une habilitation électrique est exigée sur les chantiers.",
        (
            Voie(
                "CAP, puis brevet professionnel",
                (_cap("Électricien"), _bp("Électricien")),
                "La voie la plus courante, souvent en apprentissage.",
            ),
            Voie(
                "Bac pro, puis BTS",
                (
                    _bac_pro("Métiers de l'électricité et de ses environnements connectés"),
                    _bts("BTS Électrotechnique", ("BTS - Electrotechnique",)),
                ),
            ),
            Voie(
                "Titre professionnel",
                (_titre_pro("Électricien d'équipement du bâtiment"),),
                _REPRISE,
            ),
        ),
    ),
    _metier_pro(
        "macon",
        "Maçon ou maçonne",
        ("F1703",),
        ("maçon", "maconnerie", "gros œuvre", "gros oeuvre", "btp"),
        "Ouvrier qualifié, puis chef d'équipe ou chef de chantier ; beaucoup s'installent à leur "
        "compte.",
        (
            Voie("CAP, puis brevet professionnel", (_cap("Maçon"), _bp("Maçon"))),
            Voie(
                "Bac pro, puis BTS",
                (
                    _bac_pro("Technicien du bâtiment : organisation et réalisation du gros œuvre"),
                    _bts("BTS Bâtiment", ("BTS - Bâtiment",)),
                ),
            ),
            Voie("Titre professionnel", (_titre_pro("Maçon"),), _REPRISE),
        ),
    ),
    _metier_pro(
        "peintre-batiment",
        "Peintre en bâtiment",
        ("F1606",),
        ("peintre", "peinture", "décoration", "plaquiste", "finitions"),
        "Salarié d'une entreprise de finitions, puis chef d'équipe ou artisan.",
        (
            Voie(
                "CAP, puis brevet professionnel",
                (
                    _cap("Peintre applicateur de revêtements"),
                    _bp("Peintre applicateur de revêtements"),
                ),
            ),
            Voie(
                "Bac pro, puis BTS",
                (
                    _bac_pro("Aménagement et finitions du bâtiment"),
                    _bts(
                        "BTS Finitions, aménagement des bâtiments",
                        ("BTS - Finitions, aménagement des bâtiments*",),
                    ),
                ),
            ),
            Voie("Titre professionnel", (_titre_pro("Peintre en bâtiment"),), _REPRISE),
        ),
    ),
    _metier_pro(
        "couvreur",
        "Couvreur ou couvreuse",
        ("F1610",),
        ("couvreur", "toiture", "zingueur", "charpente"),
        "Salarié d'une entreprise de couverture, puis chef d'équipe ou artisan ; métier très "
        "demandé.",
        (
            Voie("CAP, puis brevet professionnel", (_cap("Couvreur"), _bp("Couvreur"))),
            Voie(
                "Bac pro, puis BTS",
                (
                    _bac_pro("Interventions sur le patrimoine bâti, option couverture"),
                    _bts(
                        "BTS Enveloppe des bâtiments",
                        ("BTS - Enveloppe des bâtiments*",),
                    ),
                ),
            ),
        ),
    ),
    _metier_pro(
        "menuisier",
        "Menuisier ou menuisière",
        ("H2206",),
        ("menuisier", "ébéniste", "bois", "agenceur", "charpentier"),
        "En atelier ou sur chantier, puis chef d'atelier ou artisan.",
        (
            Voie(
                "CAP, puis brevet professionnel",
                (
                    _cap(
                        "Menuisier fabricant",
                        "Ou CAP Menuisier installateur pour la pose sur chantier. En lycée "
                        "professionnel ou en apprentissage.",
                    ),
                    _bp("Menuisier"),
                ),
            ),
            Voie(
                "Bac pro, puis BTS",
                (
                    _bac_pro("Technicien menuisier agenceur"),
                    _bts(
                        "BTS Systèmes constructifs bois et habitat, ou Étude et réalisation "
                        "d'agencement",
                        (
                            "BTS - Systèmes constructifs bois et habitat",
                            "BTS - Etude et réalisation d'agencement",
                        ),
                    ),
                ),
            ),
        ),
    ),
    _metier_pro(
        "soudeur",
        "Soudeur ou soudeuse",
        ("H2913",),
        ("soudeur", "soudure", "chaudronnier", "chaudronnerie", "métallerie"),
        "Dans l'industrie, la construction navale ou le nucléaire ; des certifications de "
        "soudage s'ajoutent au diplôme selon les procédés.",
        (
            Voie(
                "CAP ou bac pro, puis BTS",
                (
                    _cap("Réalisations industrielles en chaudronnerie ou soudage"),
                    _bac_pro("Technicien en chaudronnerie industrielle"),
                    _bts(
                        "BTS Conception et réalisation en chaudronnerie industrielle",
                        ("BTS - Conception et réalisation en chaudronnerie industrielle",),
                    ),
                ),
            ),
            Voie("Titre professionnel", (_titre_pro("Soudeur assembleur industriel"),), _REPRISE),
        ),
    ),
    _metier_pro(
        "mecanicien-auto",
        "Mécanicien ou mécanicienne automobile",
        ("I1604",),
        ("mécanicien", "garagiste", "mécanique auto", "automobile", "moto"),
        "En garage, en concession ou dans un réseau d'entretien rapide ; puis chef d'atelier, "
        "réceptionnaire ou garagiste à son compte.",
        (
            Voie(
                "CAP, puis bac pro",
                (
                    _cap("Maintenance des véhicules, option voitures particulières"),
                    _bac_pro(
                        "Maintenance des véhicules",
                        "En 2 ans après le CAP, ou 3 ans après la 3e. Options voitures, "
                        "véhicules de transport routier ou motocycles.",
                    ),
                ),
            ),
            Voie(
                "Bac pro, puis BTS",
                (
                    _bac_pro("Maintenance des véhicules"),
                    _bts("BTS Maintenance des véhicules", ("BTS - Maintenance des véhicules*",)),
                ),
            ),
            Voie("Titre professionnel", (_titre_pro("Mécanicien automobile"),), _REPRISE),
        ),
    ),
    _metier_pro(
        "boulanger",
        "Boulanger ou boulangère",
        ("D1102",),
        ("boulanger", "boulangerie", "pain", "viennoiserie"),
        "Ouvrier boulanger, puis chef de fabrication ou artisan à son compte ; le BP est le "
        "diplôme de référence pour reprendre une boulangerie.",
        (
            Voie(
                "CAP, puis brevet professionnel",
                (
                    _cap("Boulanger"),
                    Etape(
                        "Après le CAP · 1 an",
                        "Spécialisation boulangerie spécialisée (facultative)",
                        "Ancienne mention complémentaire, devenue certificat de spécialisation.",
                    ),
                    _bp("Boulanger"),
                ),
                "La voie la plus courante, presque toujours en apprentissage.",
            ),
            Voie("Bac pro", (_bac_pro("Boulanger-pâtissier"),)),
            Voie(
                "CAP en un an, en reconversion",
                (
                    Etape(
                        "Adulte · 1 an",
                        "CAP Boulanger en formation pour adultes",
                        "Dans un centre de formation ou en candidat libre, avec un stage en "
                        "boulangerie.",
                    ),
                ),
                _REPRISE,
            ),
        ),
    ),
    _metier_pro(
        "patissier",
        "Pâtissier ou pâtissière",
        ("D1104",),
        ("pâtissier", "patisserie", "chocolatier", "glacier", "confiseur"),
        "En pâtisserie artisanale, en restaurant ou en hôtel, puis chef pâtissier ou artisan.",
        (
            Voie(
                "CAP, puis brevet technique des métiers",
                (
                    _cap("Pâtissier"),
                    Etape(
                        "Après le CAP · 2 ans",
                        "Brevet technique des métiers (BTM) Pâtissier confiseur glacier traiteur",
                        "Préparé en apprentissage dans les chambres de métiers.",
                    ),
                ),
            ),
            Voie("Bac pro", (_bac_pro("Boulanger-pâtissier"),)),
        ),
    ),
    _metier_pro(
        "boucher",
        "Boucher ou bouchère",
        ("D1101",),
        ("boucher", "boucherie", "charcutier", "traiteur"),
        "En boucherie artisanale ou en grande surface, puis chef de rayon ou artisan ; métier "
        "qui recrute beaucoup.",
        (
            Voie("CAP, puis brevet professionnel", (_cap("Boucher"), _bp("Boucher"))),
            Voie("Bac pro", (_bac_pro("Boucher charcutier traiteur"),)),
        ),
    ),
    _metier_pro(
        "cuisinier",
        "Cuisinier ou cuisinière",
        ("G1602",),
        ("cuisinier", "cuisine", "chef", "restauration", "commis"),
        "Commis, puis chef de partie, second et chef de cuisine ; ou à son compte.",
        (
            Voie("CAP, puis brevet professionnel", (_cap("Cuisine"), _bp("Arts de la cuisine"))),
            Voie(
                "Bac pro, puis BTS",
                (
                    _bac_pro("Cuisine"),
                    _bts(
                        "BTS Management en hôtellerie-restauration",
                        ("BTS - Management en hôtellerie restauration",),
                        "Sur dossier ; il ouvre aussi la gestion de restaurant et l'hôtellerie.",
                    ),
                ),
            ),
            Voie("Titre professionnel", (_titre_pro("Cuisinier"),), _REPRISE),
        ),
    ),
    _metier_pro(
        "coiffeur",
        "Coiffeur ou coiffeuse",
        ("D1202",),
        ("coiffeur", "coiffure", "barbier"),
        "En salon, puis manager ou gérant ; le BP (ou le brevet de maîtrise) est exigé pour "
        "ouvrir ou gérer un salon.",
        (
            Voie(
                "CAP, puis brevet professionnel",
                (_cap("Métiers de la coiffure"), _bp("Coiffure")),
                "La voie la plus courante, souvent en apprentissage.",
            ),
            Voie(
                "Après le bac : BTS",
                (
                    _bts(
                        "BTS Métiers de la coiffure",
                        ("BTS - Métiers de la coiffure",),
                        "Pour les titulaires du CAP ou du BP avec un bac ; il mène au "
                        "management, à la formation ou aux marques.",
                    ),
                ),
            ),
        ),
    ),
    _metier_pro(
        "estheticien",
        "Esthéticien ou esthéticienne",
        ("D1208",),
        ("esthéticienne", "esthétique", "beauté", "spa", "prothésiste ongulaire"),
        "En institut, spa ou parfumerie, puis responsable d'institut ou à son compte.",
        (
            Voie(
                "CAP, puis brevet professionnel",
                (
                    _cap("Esthétique, cosmétique, parfumerie"),
                    _bp("Esthétique, cosmétique, parfumerie"),
                ),
            ),
            Voie(
                "Bac pro, puis BTS",
                (
                    _bac_pro("Esthétique, cosmétique, parfumerie"),
                    _bts(
                        "BTS Métiers de l'esthétique-cosmétique-parfumerie",
                        ("BTS - Métiers de l'esthétique-cosmétique-parfumerie",),
                    ),
                ),
            ),
        ),
    ),
    _metier_pro(
        "fleuriste",
        "Fleuriste",
        ("D1209",),
        ("fleuriste", "fleurs", "art floral"),
        "En boutique ou en grande surface, puis responsable de magasin ou artisan.",
        (
            Voie(
                "CAP, puis brevet professionnel",
                (
                    _cap("Fleuriste"),
                    _bp(
                        "Fleuriste",
                        "Ou brevet technique des métiers (BTM) Fleuriste, en chambre de métiers.",
                    ),
                ),
            ),
        ),
    ),
    _metier_pro(
        "paysagiste",
        "Jardinier ou jardinière paysagiste",
        ("A1203",),
        ("paysagiste", "jardinier", "espaces verts", "élagueur"),
        "En entreprise du paysage ou au service des espaces verts d'une commune, puis chef "
        "d'équipe ou à son compte.",
        (
            Voie(
                "CAP agricole, puis bac pro",
                (
                    _cap(
                        "agricole Jardinier paysagiste",
                        "En lycée agricole ou en apprentissage.",
                    ),
                    _bac_pro("Aménagements paysagers", "En lycée agricole ou en apprentissage."),
                ),
            ),
            Voie(
                "Bac pro, puis BTSA",
                (
                    _bac_pro("Aménagements paysagers", "En lycée agricole ou en apprentissage."),
                    _bts(
                        "BTSA Aménagements paysagers",
                        ("BTSA - Aménagements paysagers", "CSA - Constructions paysagères"),
                    ),
                ),
            ),
        ),
    ),
    _metier_pro(
        "agriculteur",
        "Agriculteur ou agricultrice",
        ("A1416", "A1417", "A1414"),
        ("agriculteur", "éleveur", "exploitant agricole", "maraîcher", "viticulteur", "ferme"),
        "Salarié agricole ou installation à son compte. Les aides à l'installation des moins de "
        "40 ans demandent un diplôme agricole au moins de niveau bac (bac pro, BPREA ou BTSA).",
        (
            Voie(
                "Bac pro, puis BTSA",
                (
                    _bac_pro(
                        "Conduite et gestion de l'entreprise agricole",
                        "En lycée agricole ou en apprentissage, avec stages en exploitation.",
                    ),
                    _bts(
                        "BTSA Analyse, conduite et stratégie de l'entreprise agricole",
                        ("BTSA - Analyse, conduite et stratégie de l'entreprise agricole*",),
                        "Sur dossier ; des certificats de spécialisation (élevage, maraîchage) "
                        "complètent sur un an.",
                    ),
                ),
            ),
            Voie(
                "BPREA, en reconversion",
                (
                    Etape(
                        "Adulte · 1 an",
                        "Brevet professionnel responsable d'entreprise agricole (BPREA)",
                        "En centre de formation pour adultes (CFPPA), avec stages ; il donne la "
                        "capacité agricole pour les aides à l'installation.",
                    ),
                ),
                _REPRISE,
            ),
        ),
    ),
    _metier_pro(
        "chauffeur-routier",
        "Chauffeur ou chauffeuse routier",
        ("N4101",),
        ("chauffeur", "routier", "camion", "poids lourd", "livreur", "conducteur"),
        "Transport régional ou international, livraison, citerne… Le permis C (porteur) ou CE "
        "(semi-remorque) et la formation obligatoire FIMO sont indispensables.",
        (
            Voie(
                "CAP ou bac pro en lycée",
                (
                    _cap("Conducteur livreur de marchandises"),
                    _bac_pro(
                        "Conducteur transport routier marchandises",
                        "Il inclut les permis poids lourd et la FIMO, passés pendant la formation.",
                    ),
                ),
            ),
            Voie(
                "Titre professionnel",
                (
                    _titre_pro(
                        "Conducteur du transport routier de marchandises",
                        "Sur porteur (permis C) ou sur tous véhicules (permis CE) ; permis et "
                        "FIMO compris, souvent financés par France Travail ou un employeur.",
                    ),
                ),
                _REPRISE,
            ),
        ),
        lycee="Après la 3e en lycée professionnel, ou plus tard en formation pour adultes. "
        "Le permis B est utile ; les permis poids lourd se passent pendant la formation.",
    ),
    _metier_pro(
        "conducteur-bus",
        "Conducteur ou conductrice de bus et de car",
        ("N4103",),
        ("chauffeur de bus", "conducteur de bus", "car", "autocar", "transport en commun"),
        "Lignes urbaines, scolaires ou interurbaines, tourisme. Permis D et formation "
        "obligatoire FIMO voyageurs.",
        (
            Voie(
                "Titre professionnel",
                (
                    _titre_pro(
                        "Conducteur du transport en commun sur route",
                        "Permis D et FIMO compris ; les réseaux de transport financent souvent la "
                        "formation à l'embauche. Le permis D s'obtient en général à partir de "
                        "21 ans.",
                    ),
                ),
                "La voie la plus courante.",
            ),
            Voie(
                "CAP en lycée",
                (_cap("Agent d'accueil et de conduite routière, transport de voyageurs"),),
            ),
        ),
        lycee="Pas de diplôme exigé au départ : on entre le plus souvent en formation adulte. "
        "Le permis B est requis.",
        depart="Au départ",
    ),
    _metier_pro(
        "taxi-vtc",
        "Chauffeur ou chauffeuse de taxi ou de VTC",
        ("N4102",),
        ("taxi", "vtc", "chauffeur privé", "uber"),
        "Salarié, locataire ou indépendant. Un taxi doit aussi disposer d'une autorisation de "
        "stationnement (licence) ou travailler pour quelqu'un qui en a une.",
        (
            Voie(
                "Examen taxi ou VTC",
                (
                    Etape(
                        "Dès 3 ans de permis B",
                        "Examen taxi ou VTC",
                        "Organisé par les chambres de métiers et de l'artisanat ; il se prépare "
                        "dans une école agréée ou seul. Permis B depuis 3 ans (2 ans après la "
                        "conduite accompagnée).",
                    ),
                    Etape(
                        "Après l'examen",
                        "Carte professionnelle",
                        "Délivrée par la préfecture, après vérification du casier judiciaire et "
                        "visite médicale.",
                    ),
                ),
            ),
        ),
        lycee="Aucun diplôme exigé : l'accès passe par le permis et un examen professionnel.",
        depart="Au départ",
    ),
    _metier_pro(
        "aide-soignant",
        "Aide-soignant ou aide-soignante",
        ("J1501",),
        ("aide soignant", "aide-soignante", "soins", "ehpad", "hôpital"),
        "À l'hôpital, en Ehpad ou à domicile. Beaucoup d'aides-soignants deviennent ensuite "
        "infirmiers, avec un accès réservé en institut.",
        (
            Voie(
                "Bac pro, puis diplôme d'État",
                (
                    _bac_pro(
                        "Accompagnement, soins et services à la personne",
                        "En lycée professionnel ; il allège la formation d'aide-soignant.",
                    ),
                    Etape(
                        "Après le bac pro · environ 1 an",
                        "Diplôme d'État d'aide-soignant (DEAS)",
                        "En institut de formation d'aides-soignants (IFAS), sur dossier et "
                        "entretien ; formation allégée pour ce bac pro.",
                    ),
                ),
            ),
            Voie(
                "Directement en institut",
                (
                    Etape(
                        "Dès 17 ans · environ 1 an",
                        "Diplôme d'État d'aide-soignant (DEAS)",
                        "Sans diplôme exigé, sur dossier et entretien ; aussi en apprentissage "
                        "ou en reconversion.",
                    ),
                ),
            ),
        ),
    ),
    _metier_pro(
        "auxiliaire-puericulture",
        "Auxiliaire de puériculture",
        ("J1304",),
        ("auxiliaire de puériculture", "crèche", "petite enfance", "maternité"),
        "En crèche, en maternité ou en service de pédiatrie.",
        (
            Voie(
                "Bac pro, puis diplôme d'État",
                (
                    _bac_pro(
                        "Accompagnement, soins et services à la personne",
                        "En lycée professionnel ; il allège la formation.",
                    ),
                    Etape(
                        "Après le bac pro · environ 1 an",
                        "Diplôme d'État d'auxiliaire de puériculture (DEAP)",
                        "En institut de formation, sur dossier et entretien.",
                    ),
                ),
            ),
            Voie(
                "Directement en institut",
                (
                    Etape(
                        "Dès 17 ans · environ 1 an",
                        "Diplôme d'État d'auxiliaire de puériculture (DEAP)",
                        "Sans diplôme exigé, sur dossier et entretien ; un CAP Accompagnant "
                        "éducatif petite enfance allège la formation.",
                    ),
                ),
            ),
        ),
    ),
)

METIERS: tuple[MetierCible, ...] = _METIERS_SUP + _METIERS_PRO


def resoudre(motif: str, libelles: list[str], familles: dict[str, str]) -> list[int]:
    """Indices des mentions désignées par un motif (exact, préfixe* ou famille:id)."""
    if motif.startswith("famille:"):
        cible = motif.removeprefix("famille:")
        return [i for i, lib in enumerate(libelles) if familles.get(lib) == cible]
    if motif.endswith("*"):
        prefixe = motif[:-1]
        return [i for i, lib in enumerate(libelles) if lib.startswith(prefixe)]
    return [i for i, lib in enumerate(libelles) if lib == motif]
