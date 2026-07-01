"""Tests for potato_tornado.cli."""

from __future__ import annotations

import duckdb
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
