from collections.abc import Callable

import pytest

from explora.core.http import RetryPolicy, SourceClient


class FakeClock:
    """Horloge et sommeil simulés : `sleep` avance l'horloge sans attendre."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_client(clock: FakeClock) -> Callable[..., SourceClient]:
    def factory(base_url: str = "https://api.test", **kwargs: object) -> SourceClient:
        kwargs.setdefault("retry", RetryPolicy(max_attempts=3, backoff_base_s=0.1))
        return SourceClient("test", base_url, sleep=clock.sleep, **kwargs)  # type: ignore[arg-type]

    return factory
