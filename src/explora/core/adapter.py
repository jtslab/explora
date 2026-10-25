"""Contrat commun des adaptateurs de sources."""

from abc import ABC
from dataclasses import dataclass
from typing import ClassVar

from explora.core.http import SourceClient


@dataclass(frozen=True)
class SourceInfo:
    """Métadonnées affichées dans l'interface et la page « Sources »."""

    id: str
    name: str
    producer: str
    licence: str
    url: str
    attribution: str
    caveats: str = ""


class SourceAdapter(ABC):
    """Un adaptateur par source.

    L'adaptateur traduit les réponses brutes de la source en modèles normalisés
    (`explora.core.models`). Le transport (cache, rate-limit, retry) est délégué
    au `SourceClient` injecté, ce qui rend chaque adaptateur testable avec un
    transport HTTP simulé.
    """

    info: ClassVar[SourceInfo]

    def __init__(self, client: SourceClient) -> None:
        self.client = client
