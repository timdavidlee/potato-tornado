"""Tests for potato_tornado.cli."""

from __future__ import annotations

import duckdb
import polars as pl
import pytest
from typer.testing import CliRunner

from potato_tornado.cli import app

runner = CliRunner()


def test_list_shows_builtin_collections() -> None:
    result = runner.invoke(app, ["list"])
    assert "labor" in result.stdout and "hotel" in result.stdout


def test_describe_shows_tables() -> None:
    result = runner.invoke(app, ["describe", "hotel"])
    assert "demand_forecast" in result.stdout


def test_generate_dry_run_reports_counts() -> None:
    result = runner.invoke(app, ["generate", "labor", "--scale", "0.2"])
    assert result.exit_code == 0


def test_generate_writes_duckdb_file(tmp_path) -> None:
    db_path = tmp_path / "out.duckdb"
    runner.invoke(app, ["generate", "labor", "--scale", "0.2", "--out", str(db_path)])
    con = duckdb.connect(str(db_path))
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    finally:
        con.close()
    assert "employees" in tables


def test_seed_uses_one_schema_per_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    schemas: list[str] = []

    class _FakeSink:
        def __init__(self, dsn: str, schema: str = "public") -> None:
            schemas.append(schema)

        def __enter__(self) -> _FakeSink:
            return self

        def __exit__(self, *exc: object) -> None:
            pass

        def write_all(self, tables: dict[str, pl.DataFrame]) -> None:
            pass

    monkeypatch.setattr("potato_tornado.sinks.postgres_sink.PostgresSink", _FakeSink)
    runner.invoke(app, ["seed", "postgresql://u:p@h/db", "-c", "hotel", "--scale", "0.1"])
    assert schemas == ["hotel"]
