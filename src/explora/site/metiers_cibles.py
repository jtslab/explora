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

METIERS: tuple[MetierCible, ...] = (
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


def resoudre(motif: str, libelles: list[str], familles: dict[str, str]) -> list[int]:
    """Indices des mentions désignées par un motif (exact, préfixe* ou famille:id)."""
    if motif.startswith("famille:"):
        cible = motif.removeprefix("famille:")
        return [i for i, lib in enumerate(libelles) if familles.get(lib) == cible]
    if motif.endswith("*"):
        prefixe = motif[:-1]
        return [i for i, lib in enumerate(libelles) if lib.startswith(prefixe)]
    return [i for i, lib in enumerate(libelles) if lib == motif]
