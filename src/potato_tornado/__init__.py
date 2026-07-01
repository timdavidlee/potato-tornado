"""potato-tornado: synthetic dataset generators for teaching.

Generate realistic-looking synthetic datasets and load them into a DuckDB or
Postgres database that an agent (or a student) can query.
"""

from potato_tornado.core.collection import Collection, GenContext, TableSpec
from potato_tornado.core.config import GenerationConfig
from potato_tornado.core.registry import get_collection, iter_collections, register

__all__ = [
    "Collection",
    "GenContext",
    "GenerationConfig",
    "TableSpec",
    "get_collection",
    "iter_collections",
    "register",
]

__version__ = "0.1.0"
