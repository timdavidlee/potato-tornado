"""Table builders for the streaming collection.

One module per table; each exposes a ``build_<table>(ctx) -> pl.DataFrame``
function that the collection wires into a ``TableSpec``. Re-exported here so the
collection's ``__init__`` can import them from one place.
"""

from __future__ import annotations

from potato_tornado.collections.streaming.tables.actors import build_actors
from potato_tornado.collections.streaming.tables.plans import build_plans
from potato_tornado.collections.streaming.tables.regions import build_regions
from potato_tornado.collections.streaming.tables.rentals import build_rentals
from potato_tornado.collections.streaming.tables.subscribers import build_subscribers
from potato_tornado.collections.streaming.tables.subscriptions import build_subscriptions
from potato_tornado.collections.streaming.tables.title_availability import build_title_availability
from potato_tornado.collections.streaming.tables.titles import build_titles

__all__ = [
    "build_actors",
    "build_plans",
    "build_regions",
    "build_rentals",
    "build_subscribers",
    "build_subscriptions",
    "build_title_availability",
    "build_titles",
]
