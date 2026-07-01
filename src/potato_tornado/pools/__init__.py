"""Entity pools: generate synthetic people / companies / cities from scratch, or
sample them from a pool built offline and persisted to disk.

See :mod:`potato_tornado.pools.store` for the persisted pool and its offline
builder, and :mod:`potato_tornado.pools.provider` for the two interchangeable
entity sources a collection draws from.
"""

from potato_tornado.pools.provider import (
    EntityProvider,
    GeneratedEntities,
    PooledEntities,
)
from potato_tornado.pools.store import EntityPool, build_pool

__all__ = [
    "EntityPool",
    "EntityProvider",
    "GeneratedEntities",
    "PooledEntities",
    "build_pool",
]
