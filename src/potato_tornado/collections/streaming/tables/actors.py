"""The ``actors`` table: the public-figure reference catalogue.

The globally-famous figures a title can headline, each tagged with the
``home_genre`` they are actually famous for. `titles.lead_actor` points here, so
joining the two lets an analyst check the off-genre signal — a figure never
headlines a title in their home genre (see ``scenarios/``).
"""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.streaming.constants import CELEBRITIES
from potato_tornado.core.collection import GenContext


def build_actors(ctx: GenContext) -> pl.DataFrame:
    # A fixed reference catalogue (same source of truth `titles` draws from) —
    # not scaled by row count.
    return pl.DataFrame(
        {
            "actor": [name for name, _home in CELEBRITIES],
            "home_genre": [home for _name, home in CELEBRITIES],
        }
    )
