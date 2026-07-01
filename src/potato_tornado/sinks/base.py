"""The :class:`Sink` protocol implemented by every storage backend."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import polars as pl


@runtime_checkable
class Sink(Protocol):
    """A destination that a collection's tables are written into.

    Implementations are used as context managers so they can open and cleanly
    close their underlying connection::

        with DuckDBSink("out.duckdb") as sink:
            sink.write_all(tables)
    """

    def write(self, name: str, df: pl.DataFrame) -> None:
        """Create (replacing if present) a table ``name`` from ``df``."""
        ...

    def write_all(self, tables: dict[str, pl.DataFrame]) -> None:
        """Write every ``name -> df`` pair."""
        ...

    def __enter__(self) -> Sink: ...

    def __exit__(self, *exc: object) -> None: ...
