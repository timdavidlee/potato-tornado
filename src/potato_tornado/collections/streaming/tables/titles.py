"""The ``titles`` table: the content catalogue (placeholder names).

The title *names* are stand-ins built from the placeholder word lists in
``constants.py`` — they will be replaced by a curated fake-show catalogue per the
naming guidance to come. Everything else (kind, release date, premium-rental
eligibility) is real and drives the rest of the collection.
"""

from __future__ import annotations

from datetime import timedelta

import polars as pl

from potato_tornado.collections.streaming.constants import (
    TITLE_ADJECTIVES,
    TITLE_KIND_WEIGHTS,
    TITLE_KINDS,
    TITLE_NOUNS,
)
from potato_tornado.core.collection import GenContext


def _placeholder_titles(n: int) -> list[str]:
    """Deterministic stand-in titles: cycle "<Adjective> <Noun>" combinations.

    Example: ``["Crimson Harbor", "Silent Harbor", ...]``; once every combination
    is used it wraps with a numeric suffix ("Crimson Harbor 2") so names stay
    unique. Placeholder only — see ``constants.py``.
    """
    a, b = len(TITLE_ADJECTIVES), len(TITLE_NOUNS)
    out: list[str] = []
    for i in range(n):
        name = f"{TITLE_ADJECTIVES[i % a]} {TITLE_NOUNS[(i // a) % b]}"
        cycle = i // (a * b)
        out.append(name if cycle == 0 else f"{name} {cycle + 1}")
    return out


def build_titles(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(300)
    release = ctx.dist.dates_between(
        n, ctx.config.start_date - timedelta(days=5 * 365), ctx.config.end_date
    )
    return pl.DataFrame(
        {
            "title_id": [f"TTL-{i:05d}" for i in range(1, n + 1)],
            "name": _placeholder_titles(n),
            "kind": ctx.dist.choice(n, TITLE_KINDS, TITLE_KIND_WEIGHTS),
            "release_date": release,
            # Eligible for a one-off premium rental (new/day-and-date releases).
            "is_premium": ctx.dist.bernoulli(n, 0.25),
        }
    )
