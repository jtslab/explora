import pytest

from explora.core.ratelimit import RateLimiter
from tests.conftest import FakeClock


async def test_rafale_puis_attente(clock: FakeClock) -> None:
    limiter = RateLimiter(rate=2, burst=2, clock=clock, sleep=clock.sleep)
    await limiter.acquire()
    await limiter.acquire()
    assert clock.sleeps == []
    await limiter.acquire()
    assert clock.sleeps == [pytest.approx(0.5)]


async def test_recharge_avec_le_temps(clock: FakeClock) -> None:
    limiter = RateLimiter(rate=1, burst=1, clock=clock, sleep=clock.sleep)
    await limiter.acquire()
    clock.now += 1
    await limiter.acquire()
    assert clock.sleeps == []


@pytest.mark.parametrize(("rate", "burst"), [(0, 1), (1, 0)])
def test_parametres_invalides(rate: float, burst: int) -> None:
    with pytest.raises(ValueError):
        RateLimiter(rate=rate, burst=burst)
