"""DuckDB sink — writes tables into a DuckDB database file (or ``:memory:``)."""

from __future__ import annotations

from pathlib import Path

import duckdb
import polars as pl


class DuckDBSink:
    """Write generated tables into a DuckDB database.

    Args:
        path: Database file path, or ``":memory:"`` for an ephemeral database.
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self._con: duckdb.DuckDBPyConnection | None = None

    def __enter__(self) -> DuckDBSink:
        self._con = duckdb.connect(self.path)
        return self

    def __exit__(self, *exc: object) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            raise RuntimeError("DuckDBSink must be used as a context manager")
        return self._con

    def write(self, name: str, df: pl.DataFrame) -> None:
        _validate_identifier(name)
        con = self.connection
        # `df` is referenced by name in the local scope for DuckDB replacement scan.
        con.register("_incoming", df)
        try:
            con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM _incoming')
        finally:
            con.unregister("_incoming")

    def write_all(self, tables: dict[str, pl.DataFrame]) -> None:
        for name, df in tables.items():
            self.write(name, df)


def _validate_identifier(name: str) -> None:
    if not name or not all(c.isalnum() or c == "_" for c in name):
        raise ValueError(f"unsafe table name: {name!r}")
