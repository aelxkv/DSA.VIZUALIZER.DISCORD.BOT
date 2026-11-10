import random

import pytest

import algos  # noqa: F401  (registers algorithms)


@pytest.fixture
def rng() -> random.Random:
    return random.Random(12345)
