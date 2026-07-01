"""Tests for potato_tornado.core.distributions."""

from __future__ import annotations

from datetime import date

import pytest

from potato_tornado.core.distributions import Distributions
from potato_tornado.core.rng import Rng


def test_choice_rejects_mismatched_weights() -> None:
    dist = Distributions(Rng(1))
    with pytest.raises(ValueError, match="weights"):
        dist.choice(10, ["a", "b"], [1.0])


def test_dates_between_stay_within_range() -> None:
    dist = Distributions(Rng(7))
    start, end = date(2024, 1, 1), date(2024, 2, 1)
    days = dist.dates_between(50, start, end)
    assert all(start <= d < end for d in days)


def test_bernoulli_probability_one_is_all_true() -> None:
    dist = Distributions(Rng(3))
    assert dist.bernoulli(20, 1.0).all()
