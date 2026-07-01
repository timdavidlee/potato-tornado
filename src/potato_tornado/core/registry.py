"""A small registry mapping collection names to :class:`Collection` builders.

Collections register themselves at import time. :func:`iter_collections` triggers
discovery of the built-in collections so callers (CLI, tests) see them without
having to import each module by hand.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable, Iterator

from potato_tornado.core.collection import Collection

CollectionFactory = Callable[[], Collection]

_REGISTRY: dict[str, CollectionFactory] = {}

# Built-in collection modules. Each calls `register(...)` on import.
_BUILTIN_MODULES = (
    "potato_tornado.collections.labor",
    "potato_tornado.collections.hotel",
)
_discovered = False


def register(name: str, factory: CollectionFactory) -> None:
    """Register a collection factory under ``name`` (idempotent per name)."""
    _REGISTRY[name] = factory


def _discover() -> None:
    global _discovered
    if _discovered:
        return
    for module in _BUILTIN_MODULES:
        importlib.import_module(module)
    _discovered = True


def get_collection(name: str) -> Collection:
    """Return the built :class:`Collection` registered under ``name``."""
    _discover()
    try:
        factory = _REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(_REGISTRY)) or "(none)"
        raise KeyError(f"unknown collection {name!r}; available: {available}") from None
    return factory()


def iter_collections() -> Iterator[Collection]:
    """Yield every registered collection, sorted by name."""
    _discover()
    for name in sorted(_REGISTRY):
        yield _REGISTRY[name]()
