"""Tests for the Postgres sink helpers that don't need a live server."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.sinks.postgres_sink import (
    PostgresSink,
    _normalize_dsn,
    _validate_identifier,
)


@pytest.mark.parametrize(
    ("dsn", "expected"),
    [
        ("postgresql://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql+psycopg://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql+asyncpg://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
    ],
)
def test_normalize_dsn_routes_bare_scheme_to_psycopg(dsn: str, expected: str) -> None:
    assert _normalize_dsn(dsn) == expected


def test_init_normalizes_dsn() -> None:
    assert PostgresSink("postgresql://u:p@host/db").dsn == "postgresql+psycopg://u:p@host/db"


def test_write_before_context_raises() -> None:
    with pytest.raises(RuntimeError):
        PostgresSink("postgresql://u:p@host/db").write("t", pl.DataFrame({"a": [1]}))


@pytest.mark.parametrize("bad", ["", "a b", "drop;table", "a-b"])
def test_validate_identifier_rejects_unsafe_names(bad: str) -> None:
    with pytest.raises(ValueError, match="unsafe table name"):
        _validate_identifier(bad)
