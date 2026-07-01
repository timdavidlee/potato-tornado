"""High-level orchestration: generate a collection and optionally write it to a sink."""

from __future__ import annotations

import polars as pl
from faker import Faker

from potato_tornado.core.config import GenerationConfig
from potato_tornado.core.registry import get_collection
from potato_tornado.pools.store import EntityPool
from potato_tornado.sinks.base import Sink


def generate(name: str, config: GenerationConfig | None = None) -> dict[str, pl.DataFrame]:
    """Generate every table of collection ``name`` into in-memory DataFrames.

    If ``config.pool_dir`` is set, entity fields are sampled from that persisted
    pool; otherwise they are generated from scratch.
    """
    config = config or GenerationConfig()
    collection = get_collection(name)
    faker = Faker()
    pool = EntityPool.load(config.pool_dir) if config.pool_dir is not None else None
    return collection.generate(config, faker, pool)


def generate_to_sink(
    name: str, sink: Sink, config: GenerationConfig | None = None
) -> dict[str, pl.DataFrame]:
    """Generate collection ``name`` and write every table into ``sink``.

    ``sink`` must already be open (used as a context manager by the caller).
    Returns the generated tables so callers can inspect row counts.
    """
    tables = generate(name, config)
    sink.write_all(tables)
    return tables
