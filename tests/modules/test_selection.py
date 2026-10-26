from pathlib import Path

from explora.core.models import Commune, Departement, EffectifCommune
from explora.modules.etudiant.selection import (
    Regle,
    VilleRetenue,
    ecrire_csv,
    resume,
    selectionner,
)

DEP = "33"


def commune(code: str, population: int = 50_000, dep: str = DEP) -> Commune:
    return Commune(
        code_insee=code, nom=f"Ville {code}", code_departement=dep, population=population
    )


def eff(
    code: str, effectif: int, uu: str | None = None, dep: str = DEP, regroupement: str = "TOTAL"
) -> EffectifCommune:
    return EffectifCommune(
        code_insee=code,
        nom=f"Ville {code}",
        code_departement=dep,
        unite_urbaine=uu or f"UU{code}",
        regroupement=regroupement,
        effectif=effectif,
    )


def departement(chef_lieu: str = "33001", code: str = DEP) -> Departement:
    return Departement(code=code, nom=f"Dép. {code}", chef_lieu=chef_lieu)


REGLE = Regle(cible=0)


def codes(villes: list[VilleRetenue]) -> list[str]:
    return [v.code_insee for v in villes]


def test_quatre_plus_gros_effectifs() -> None:
    effectifs = [eff(f"3300{i}", 1000 * i) for i in range(1, 7)]
    communes = [commune(f"3300{i}") for i in range(1, 7)]
    villes = selectionner(effectifs, communes, [departement("99999")], REGLE)
    assert codes(villes) == ["33006", "33005", "33004", "33003"]
    assert [v.rang_departement for v in villes] == [1, 2, 3, 4]
    assert {v.motif for v in villes} == {"effectif"}


def test_prefecture_remplace_la_quatrieme() -> None:
    effectifs = [eff(f"3300{i}", 1000 * i) for i in range(1, 7)]
    communes = [commune(f"3300{i}") for i in range(1, 7)]
    villes = selectionner(effectifs, communes, [departement("33001")], REGLE)
    assert codes(villes) == ["33006", "33005", "33004", "33001"]
    assert villes[-1].motif == "prefecture" and villes[-1].prefecture


def test_seuils_effectif_et_population() -> None:
    effectifs = [
        eff("33001", 99),  # trop peu d'étudiants
        eff("33002", 150),  # village avec une section de BTS
        eff("33003", 600),  # village avec un campus
        eff("33004", 150),
    ]
    communes = [commune("33001"), commune("33002", 800), commune("33003", 800), commune("33004")]
    villes = selectionner(effectifs, communes, [departement()], REGLE)
    assert codes(villes) == ["33003", "33004"]


def test_plafond_par_unite_urbaine() -> None:
    effectifs = [eff(f"3300{i}", 10_000 - i, uu="UU33701") for i in range(1, 5)]
    effectifs.append(eff("33009", 500))
    communes = [commune(f"3300{i}") for i in (1, 2, 3, 4, 9)]
    villes = selectionner(effectifs, communes, [departement("99999")], REGLE)
    assert codes(villes) == ["33001", "33002", "33003", "33009"]


def test_pas_de_plafond_en_ile_de_france() -> None:
    effectifs = [eff(f"9200{i}", 10_000 - i, uu="UU00851", dep="92") for i in range(1, 5)]
    communes = [commune(f"9200{i}", dep="92") for i in range(1, 5)]
    villes = selectionner(effectifs, communes, [departement("92050", "92")], REGLE)
    assert len(villes) == 4


def test_arrondissements_regroupes() -> None:
    effectifs = [
        eff("75105", 60_000, uu="UU00851", dep="75"),
        eff("75106", 70_000, uu="UU00851", dep="75"),
        eff("75105", 5_000, uu="UU00851", dep="75", regroupement="CPGE"),
        eff("75106", 50_000, uu="UU00851", dep="75", regroupement="UNIV"),
    ]
    villes = selectionner(
        effectifs, [commune("75056", dep="75")], [departement("75056", "75")], REGLE
    )
    assert len(villes) == 1
    paris = villes[0]
    assert (paris.code_insee, paris.effectif_etudiants) == ("75056", 130_000)
    assert paris.formations == ("CPGE", "UNIV")
    assert paris.prefecture and paris.motif == "effectif"


def test_complement_vers_les_plus_gros_effectifs() -> None:
    # Département 33 : 6 villes éligibles ; département 15 : une seule.
    effectifs = [eff(f"3300{i}", 1000 * i) for i in range(1, 7)]
    effectifs += [eff("15014", 1200, dep="15"), eff("15100", 40, dep="15")]
    communes = [commune(f"3300{i}") for i in range(1, 7)]
    communes += [commune("15014", dep="15"), commune("15100", dep="15")]
    deps = [departement("99999"), departement("15014", "15")]
    villes = selectionner(effectifs, communes, deps, Regle(cible=6))
    assert codes(villes) == ["15014", "33006", "33005", "33004", "33003", "33002"]
    assert villes[-1].motif == "complement"
    assert "Moins de 3 villes : 15" in resume(villes)


def test_complement_limite_par_departement() -> None:
    effectifs = [eff(f"3300{i}", 1000 * i) for i in range(1, 10)]
    communes = [commune(f"3300{i}") for i in range(1, 10)]
    villes = selectionner(effectifs, communes, [departement("99999")], Regle(cible=50))
    assert len(villes) == 6


def test_ecrire_csv(tmp_path: Path) -> None:
    villes = selectionner([eff("33001", 1000)], [commune("33001")], [departement()], REGLE)
    chemin = tmp_path / "villes.csv"
    ecrire_csv(villes, chemin, "2025")
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    assert lignes[0].startswith("code_insee,nom,code_departement")
    assert lignes[1] == "33001,Ville 33001,33,Dép. 33,50000,1000,1,oui,effectif,UU33001,,2025"


def test_complement_sans_plafond_par_unite_urbaine() -> None:
    effectifs = [eff(f"3300{i}", 10_000 - i, uu="UU33701") for i in range(1, 6)]
    communes = [commune(f"3300{i}") for i in range(1, 6)]
    villes = selectionner(effectifs, communes, [departement("99999")], Regle(cible=5))
    assert codes(villes) == ["33001", "33002", "33003", "33004", "33005"]
    assert [v.motif for v in villes][-2:] == ["complement", "complement"]
