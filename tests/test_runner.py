"""Tests for potato_tornado.runner (end-to-end generation and loading)."""

from __future__ import annotations

import duckdb
import pytest

from potato_tornado.core.config import GenerationConfig
from potato_tornado.core.registry import iter_collections
from potato_tornado.pools.store import build_pool
from potato_tornado.runner import generate, generate_to_sink
from potato_tornado.sinks.duckdb_sink import DuckDBSink

ALL_COLLECTIONS = [c.name for c in iter_collections()]


@pytest.mark.parametrize("name", ALL_COLLECTIONS)
def test_generation_is_deterministic(name: str) -> None:
    cfg = GenerationConfig(seed=99, scale=0.2)
    first = generate(name, cfg)
    second = generate(name, cfg)
    assert all(first[t].equals(second[t]) for t in first)


@pytest.mark.parametrize("name", ALL_COLLECTIONS)
def test_every_table_is_non_empty(name: str) -> None:
    tables = generate(name, GenerationConfig(scale=0.3))
    assert all(df.height > 0 for df in tables.values())


def test_pool_mode_draws_employee_names_from_the_pool(tmp_path) -> None:
    pool_dir = tmp_path / "pool"
    build_pool(GenerationConfig(seed=2), size=100).save(pool_dir)
    cfg = GenerationConfig(seed=5, scale=0.2, pool_dir=pool_dir)
    employees = generate("labor", cfg)["employees"]
    pool_names = set(build_pool(GenerationConfig(seed=2), size=100).people["full_name"].to_list())
    assert set(employees["full_name"].to_list()) <= pool_names


def test_generate_to_sink_persists_every_table(tmp_path) -> None:
    db_path = tmp_path / "labor.duckdb"
    with DuckDBSink(db_path) as sink:
        tables = generate_to_sink("labor", sink, GenerationConfig(scale=0.2))

    con = duckdb.connect(str(db_path))
    try:
        present = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    assert present == set(tables)
