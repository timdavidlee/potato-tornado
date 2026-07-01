"""Sinks: where a generated collection gets written."""

from potato_tornado.sinks.base import Sink
from potato_tornado.sinks.duckdb_sink import DuckDBSink

__all__ = ["DuckDBSink", "Sink"]
