"""Tests for potato_tornado.sinks.duckdb_sink."""

from __future__ import annotations

import polars as pl
import pytest

from potato_tornado.sinks.duckdb_sink import DuckDBSink


def test_write_round_trips_row_count() -> None:
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    with DuckDBSink(":memory:") as sink:
        sink.write("widgets", df)
        rows = sink.connection.execute("SELECT count(*) FROM widgets").fetchone()
    assert rows is not None and rows[0] == 3


def test_write_replaces_an_existing_table() -> None:
    with DuckDBSink(":memory:") as sink:
        sink.write("t", pl.DataFrame({"a": [1, 2, 3]}))
        sink.write("t", pl.DataFrame({"a": [1]}))
        rows = sink.connection.execute("SELECT count(*) FROM t").fetchone()
    assert rows is not None and rows[0] == 1


def test_rejects_unsafe_table_name() -> None:
    with DuckDBSink(":memory:") as sink, pytest.raises(ValueError, match="unsafe table name"):
        sink.write("drop; --", pl.DataFrame({"a": [1]}))


def test_connection_requires_context_manager() -> None:
    sink = DuckDBSink(":memory:")
    with pytest.raises(RuntimeError, match="context manager"):
        _ = sink.connection
