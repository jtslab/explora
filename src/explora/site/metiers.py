"""Métiers et secteurs visés par chaque formation, d'après le RNCP.

Le Répertoire national des certifications professionnelles (France Compétences)
donne pour chaque diplôme ses codes métiers ROME. On rattache les mentions de
`web/data/formations.json` (« BTS - Tourisme », « L1 - Droit »...) à leur fiche RNCP
par le type de diplôme et l'intitulé, puis on regroupe les métiers par grand
domaine du ROME, qui sert de secteur d'activité.

    uv run python -m explora.site.metiers --rncp export-fiches-rncp-v4-1-AAAA-MM-JJ.zip

L'export se télécharge sur data.gouv.fr, jeu « Répertoire national des
certifications professionnelles et répertoire spécifique ».
"""

import argparse
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO
from xml.etree import ElementTree as ET

from pydantic import BaseModel, Field

from explora.site import formations as fm

# Grands domaines du ROME (première lettre du code métier).
DOMAINES_ROME = {
    "A": "Agriculture, pêche, espaces verts, soins aux animaux",
    "B": "Arts et façonnage d'ouvrages d'art",
    "C": "Banque, assurance, immobilier",
    "D": "Commerce, vente et grande distribution",
    "E": "Communication, média et multimédia",
    "F": "Construction, bâtiment et travaux publics",
    "G": "Hôtellerie-restauration, tourisme, loisirs et animation",
    "H": "Industrie",
    "I": "Installation et maintenance",
    "J": "Santé",
    "K": "Services à la personne et à la collectivité",
    "L": "Spectacle",
    "M": "Support à l'entreprise",
    "N": "Transport et logistique",
}

# Préfixe de la mention → abrégés RNCP du même diplôme.
PREFIXES = {
    "BTS": {"BTS"},
    "BTSA": {"BTSA"},
    "BTSM": {"BTSMarit", "BTS"},
    "BUT": {"BUT"},
    "L1": {"LICENCE", "Grade_Licence"},
    "DEUST": {"DEUST"},
    "CS": {"CS"},
    "CSA": {"CS"},
    "BPJEPS": {"BPJEPS"},
    "DN MADE": {"DNMADE"},
    "DSP": {"DSP"},
    "D.E": {"DE", ""},
}
MOTS_VIDES = {
    "de", "du", "des", "la", "le", "les", "et", "en", "d", "l", "a", "au", "aux",
    "option", "options", "opt", "parcours", "specialite", "mention",
}  # fmt: skip
SEUIL = 0.75


@dataclass
class FicheRncp:
    numero: str
    intitule: str
    abrege: str
    actif: bool
    romes: list[tuple[str, str]] = field(default_factory=list)


class Correspondance(BaseModel):
    rncp: str
    """Numéro de la fiche RNCP retenue, ex. « RNCP37890 »."""
    romes: list[str]


class IndexMetiers(BaseModel):
    genere_le: datetime
    source: str
    domaines: dict[str, str] = Field(default_factory=dict)
    metiers: dict[str, str] = Field(default_factory=dict)
    """Libellé de chaque code ROME utilisé."""
    mentions: dict[str, Correspondance] = Field(default_factory=dict)
    """Par libellé de mention (celui de l'index des formations)."""


def lire_fiches(flux: IO[bytes]) -> Iterator[FicheRncp]:
    """Fiches de l'export XML (≈ 500 Mo), lues au fil de l'eau."""
    for _, el in ET.iterparse(flux, events=("end",)):
        if el.tag != "FICHE":
            continue
        romes = [
            (r.findtext("CODE") or "", r.findtext("LIBELLE") or "")
            for r in el.findall("CODES_ROME/ROME")
        ]
        yield FicheRncp(
            numero=(el.findtext("NUMERO_FICHE") or "").strip(),
            intitule=(el.findtext("INTITULE") or "").strip(),
            abrege=(el.findtext("ABREGE/CODE") or "").strip(),
            actif=(el.findtext("ACTIF") or "").strip() == "Oui",
            romes=[(c.strip(), lib.strip()) for c, lib in romes if c],
        )
        el.clear()


def _mots_ordonnes(texte: str) -> list[str]:
    """Mots significatifs, au singulier grossier (« fluides » → « fluide »)."""
    return [
        m[:-1] if len(m) > 3 and m[-1] in "sx" else m
        for m in fm.normaliser(texte).split()
        if m not in MOTS_VIDES
    ]


def _mots(texte: str) -> set[str]:
    return set(_mots_ordonnes(texte))


def _variantes(reste: str) -> list[str]:
    """Le libellé complet, puis sans l'option ni la précision entre parenthèses."""
    court = re.split(r"\s+-\s+option|\s+opt\b|\s+option\b|\s+-\s+1[èe]re|\s*\(", reste, flags=re.I)
    return [reste] + ([court[0]] if court[0] != reste else [])


def _tete(intitule: str) -> str:
    """« Informatique : Réalisation d'applications » → mots collés de « Informatique »."""
    return "".join(_mots_ordonnes(intitule.split(" : ")[0]))


def correspondre(mention: str, fiches: dict[str, list[FicheRncp]]) -> list[FicheRncp]:
    """Fiches RNCP de la mention (plusieurs pour les parcours d'un BUT), [] si rien de sûr."""
    if mention.startswith("D.E "):
        prefixe, reste = "D.E", mention[4:]
    elif " - " in mention:
        prefixe, reste = mention.split(" - ", 1)
    else:
        return []
    if prefixe not in PREFIXES:
        return []
    candidates = [f for abrege in PREFIXES[prefixe] for f in fiches.get(abrege, [])]
    for variante in _variantes(reste):
        cherches = _mots(variante)
        if not cherches:
            continue
        # Mots collés : « audio-visuel » et « audiovisuel » doivent se retrouver.
        colle = "".join(_mots_ordonnes(variante))
        meilleure: tuple[float, float, FicheRncp] | None = None
        for f in candidates:
            intitule = f.intitule.replace("(fiche nationale)", "")
            mots = _mots(intitule)
            if not mots:
                continue
            communs = len(cherches & mots)
            jaccard = communs / len(cherches | mots)
            note = jaccard
            if communs == len(cherches) or colle in "".join(_mots_ordonnes(intitule)):
                note = max(note, 0.9)  # tout ce qui est cherché y est
            note += 0.05 if f.actif else 0
            # À note égale, l'intitulé qui commence par la mention l'emporte : le BUT
            # « Informatique » plutôt que « Génie électrique et informatique industrielle ».
            note += 0.02 if _tete(intitule) == colle else 0
            if meilleure is None or (note, jaccard) > meilleure[:2]:
                meilleure = (note, jaccard, f)
        if meilleure and meilleure[0] >= SEUIL:
            choisie = meilleure[2]
            tete = _tete(choisie.intitule)
            # Les parcours du même diplôme (« Informatique : … ») partagent la mention.
            parcours = [
                f
                for f in candidates
                if f is not choisie
                and f.actif == choisie.actif
                and f.abrege == choisie.abrege
                and " : " in f.intitule
                and _tete(f.intitule) == tete
            ]
            return [choisie, *parcours]
    return []


def construire(mentions: Iterable[str], fiches: Iterable[FicheRncp], source: str) -> IndexMetiers:
    par_abrege: dict[str, list[FicheRncp]] = defaultdict(list)
    for f in fiches:
        if f.romes:
            par_abrege[f.abrege].append(f)
    libelles: dict[str, Counter[str]] = defaultdict(Counter)
    correspondances = {}
    for mention in mentions:
        trouvees = correspondre(mention, par_abrege)
        if not trouvees:
            continue
        romes = [r for f in trouvees for r in f.romes]
        correspondances[mention] = Correspondance(
            rncp=trouvees[0].numero, romes=sorted({c for c, _ in romes})
        )
        for code, libelle in romes:
            libelles[code][libelle] += 1
    return IndexMetiers(
        genere_le=datetime.now(UTC).replace(microsecond=0),
        source=source,
        domaines={k: v for k, v in DOMAINES_ROME.items() if any(c.startswith(k) for c in libelles)},
        metiers={code: c.most_common(1)[0][0] for code, c in sorted(libelles.items())},
        mentions=dict(sorted(correspondances.items())),
    )


def charger(chemin: Path) -> IndexMetiers:
    return IndexMetiers.model_validate_json(chemin.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rncp", type=Path, required=True, help="export RNCP (.zip ou .xml)")
    parser.add_argument("--formations", type=Path, default=Path("web/data/formations.json"))
    parser.add_argument("--sortie", type=Path, default=Path("web/data/metiers.json"))
    args = parser.parse_args()
    mentions = [m.libelle for m in fm.charger(args.formations).mentions]
    if args.rncp.suffix == ".zip":
        with zipfile.ZipFile(args.rncp) as z:
            nom = next(n for n in z.namelist() if n.endswith(".xml"))
            with z.open(nom) as flux:
                index = construire(mentions, lire_fiches(flux), args.rncp.name)
    else:
        with args.rncp.open("rb") as flux:
            index = construire(mentions, lire_fiches(flux), args.rncp.name)
    args.sortie.write_text(index.model_dump_json(), encoding="utf-8")
    print(
        f"{len(index.mentions)}/{len(mentions)} mentions rattachées, "
        f"{len(index.metiers)} métiers, {len(index.domaines)} secteurs"
    )


if __name__ == "__main__":
    main()
