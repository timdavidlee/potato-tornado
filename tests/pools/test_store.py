"""Tests for potato_tornado.pools.store."""

from __future__ import annotations

from pathlib import Path

import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.pools.store import EntityPool, build_pool


@pytest.fixture(scope="module")
def pool() -> EntityPool:
    return build_pool(GenerationConfig(seed=7), size=50)


def test_build_pool_people_emails_are_unique(pool: EntityPool) -> None:
    assert pool.people["email"].n_unique() == pool.people.height


def test_build_pool_is_deterministic() -> None:
    first = build_pool(GenerationConfig(seed=7), size=20)
    second = build_pool(GenerationConfig(seed=7), size=20)
    assert first.people.equals(second.people)


def test_build_pool_rejects_nonpositive_size() -> None:
    with pytest.raises(ValueError, match="size must be positive"):
        build_pool(GenerationConfig(seed=7), size=0)


def test_save_load_round_trips(pool: EntityPool, tmp_path: Path) -> None:
    pool.save(tmp_path / "p")
    assert EntityPool.load(tmp_path / "p").companies.equals(pool.companies)
