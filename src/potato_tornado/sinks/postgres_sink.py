"""Postgres sink — optional, requires the ``postgres`` extra.

Install with ``uv sync --extra postgres`` (or ``pip install 'potato-tornado[postgres]'``).
Writes each table via Polars' ``write_database``.
"""

from __future__ import annotations

import polars as pl


class PostgresSink:
    """Write generated tables into a Postgres schema.

    Args:
        dsn: SQLAlchemy-style connection URI, e.g.
            ``postgresql://user:pass@localhost:5432/teaching``. A bare
            ``postgresql://`` / ``postgres://`` scheme is routed to the psycopg 3
            driver shipped by the ``postgres`` extra (see :func:`_normalize_dsn`).
        schema: Target schema; created if missing.
    """

    def __init__(self, dsn: str, schema: str = "public") -> None:
        self.dsn = _normalize_dsn(dsn)
        self.schema = schema
        self._engine: object | None = None

    def __enter__(self) -> PostgresSink:
        try:
            from sqlalchemy import create_engine, text
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on extra
            raise ModuleNotFoundError(
                "PostgresSink requires the 'postgres' extra: uv sync --extra postgres"
            ) from exc
        engine = create_engine(self.dsn)
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"'))
        self._engine = engine
        return self

    def __exit__(self, *exc: object) -> None:
        if self._engine is not None:
            self._engine.dispose()  # type: ignore[attr-defined]
            self._engine = None

    def write(self, name: str, df: pl.DataFrame) -> None:
        if self._engine is None:
            raise RuntimeError("PostgresSink must be used as a context manager")
        _validate_identifier(name)
        df.write_database(
            table_name=f"{self.schema}.{name}",
            connection=self._engine,  # type: ignore[arg-type]
            if_table_exists="replace",
        )

    def write_all(self, tables: dict[str, pl.DataFrame]) -> None:
        for name, df in tables.items():
            self.write(name, df)


def _validate_identifier(name: str) -> None:
    if not name or not all(c.isalnum() or c == "_" for c in name):
        raise ValueError(f"unsafe table name: {name!r}")


def _normalize_dsn(dsn: str) -> str:
    """Route a bare ``postgresql://`` / ``postgres://`` DSN to the installed psycopg 3 driver.

    SQLAlchemy maps the bare ``postgresql://`` scheme to the *psycopg2* dialect, which this
    package deliberately does not depend on — the ``postgres`` extra ships psycopg **3**. Rewrite
    such DSNs to the explicit ``postgresql+psycopg://`` form so the installed driver is selected;
    a DSN that already names a driver (``postgresql+psycopg://``, ``postgresql+asyncpg://``, …) is
    returned unchanged.
    """
    for prefix in ("postgresql://", "postgres://"):
        if dsn.startswith(prefix):
            return "postgresql+psycopg://" + dsn[len(prefix) :]
    return dsn
