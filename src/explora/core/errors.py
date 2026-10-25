"""Erreurs communes à tous les adaptateurs."""


class SourceError(Exception):
    """Erreur définitive renvoyée par une source (4xx hors 429, réponse illisible...)."""

    def __init__(self, source: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(f"[{source}] {message}")
        self.source = source
        self.status_code = status_code


class SourceUnavailableError(SourceError):
    """La source n'a pas répondu correctement après épuisement des tentatives."""
