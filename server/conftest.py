import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_cache():
    # Rate-limit counters live in the cache; don't let one test throttle the next.
    cache.clear()
    yield
    cache.clear()
