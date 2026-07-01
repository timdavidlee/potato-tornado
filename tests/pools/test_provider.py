"""Tests for potato_tornado.pools.provider."""

from __future__ import annotations

import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.core.rng import Rng
from potato_tornado.pools.provider import PooledEntities, _uniquify
from potato_tornado.pools.store import EntityPool, build_pool


@pytest.fixture(scope="module")
def pool() -> EntityPool:
    return build_pool(GenerationConfig(seed=3), size=40)


def test_pooled_people_emails_are_unique_even_when_oversampled(pool: EntityPool) -> None:
    # n far exceeds the 40-row pool, so rows must repeat — emails must not.
    people = PooledEntities(pool, Rng(1)).people(500)
    assert people["email"].n_unique() == people.height


def test_pooled_names_are_drawn_from_the_pool(pool: EntityPool) -> None:
    names = PooledEntities(pool, Rng(1)).people(100)["full_name"].to_list()
    assert set(names) <= set(pool.people["full_name"].to_list())


def test_pooled_sampling_is_deterministic(pool: EntityPool) -> None:
    first = PooledEntities(pool, Rng(9)).companies(30)
    second = PooledEntities(pool, Rng(9)).companies(30)
    assert first == second


def test_uniquify_disambiguates_duplicate_emails() -> None:
    assert _uniquify(["a@x.io", "a@x.io", "a@x.io"]) == ["a@x.io", "a+2@x.io", "a+3@x.io"]
