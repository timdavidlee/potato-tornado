"""The ``titles`` table: the content catalogue.

Each title pairs a globally-famous public figure with a plausible show name in a
genre they are *not* known for — the comedy is the mismatch. Examples:
"Tom Cruise in Big Mama's Family" (comedy), "Bobby Flay's Nightmare in the Jungle
Episode 3" (horror). Series titles get an "Episode/Season N" suffix; films don't.
Names are fictional parody; the figures are public. The figure and the off-genre
are also exposed as ``lead_actor`` / ``genre`` columns so the pairing is queryable.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import polars as pl

from potato_tornado.collections.streaming.constants import (
    CELEBRITIES,
    GENRE_TEMPLATES,
    GENRES,
    MATURITY_RATING_WEIGHTS,
    MATURITY_RATINGS,
    OUTER_POSSESSIVE,
    OUTER_TEMPLATES,
    RUNTIME_MINUTES_BY_KIND,
    TITLE_ADJECTIVES,
    TITLE_FAMILIARS,
    TITLE_KIND_WEIGHTS,
    TITLE_KINDS,
    TITLE_NOUNS,
    TITLE_PLACES,
)
from potato_tornado.core.collection import GenContext

# A wide co-prime modulus for the "pick one of a short list" rolls, so the choice
# spreads evenly however long each list is.
_ROLL_MAX = 9973

# Quality score (1-10). Premium-eligible titles skew higher than the back
# catalogue. See scenarios/premium-titles-score-higher.md.
_AVG_RATING_BASE_MEAN = 6.3
_AVG_RATING_PREMIUM_MEAN = 7.5
_AVG_RATING_SD = 1.2


def _off_genres(home_genre: str) -> list[str]:
    """Show genres for a figure — everything but the genre they are famous for."""
    return [g for g in GENRES if g != home_genre]


def _compose_titles(
    ctx: GenContext, n: int, kinds: list[str]
) -> tuple[list[str], list[str], list[str]]:
    """Build ``n`` titles, returning ``(name, lead_actor, genre)`` per row.

    ``name`` is the "<figure> in/'s <off-genre show>" string (series get an
    ``Episode/Season N`` suffix); ``lead_actor`` is the figure and ``genre`` the
    off-genre it was dropped into — surfaced as columns so the parody is queryable.
    """
    celeb_idx = ctx.dist.integers(n, 0, len(CELEBRITIES) - 1)
    genre_roll = ctx.dist.integers(n, 0, _ROLL_MAX)
    tmpl_roll = ctx.dist.integers(n, 0, _ROLL_MAX)
    outer_roll = ctx.dist.integers(n, 0, _ROLL_MAX)
    adj_idx = ctx.dist.integers(n, 0, len(TITLE_ADJECTIVES) - 1)
    noun_idx = ctx.dist.integers(n, 0, len(TITLE_NOUNS) - 1)
    place_idx = ctx.dist.integers(n, 0, len(TITLE_PLACES) - 1)
    fam_idx = ctx.dist.integers(n, 0, len(TITLE_FAMILIARS) - 1)
    unit_roll = ctx.dist.integers(n, 0, _ROLL_MAX)
    ep_num = ctx.dist.integers(n, 1, 12)

    names: list[str] = []
    actors: list[str] = []
    genres: list[str] = []
    for i in range(n):
        celeb, home = CELEBRITIES[int(celeb_idx[i])]
        candidates = _off_genres(home)
        genre = candidates[int(genre_roll[i]) % len(candidates)]
        templates = GENRE_TEMPLATES[genre]
        show = templates[int(tmpl_roll[i]) % len(templates)].format(
            a=TITLE_ADJECTIVES[int(adj_idx[i])],
            n=TITLE_NOUNS[int(noun_idx[i])],
            p=TITLE_PLACES[int(place_idx[i])],
            fam=TITLE_FAMILIARS[int(fam_idx[i])],
        )
        outer = OUTER_TEMPLATES[int(outer_roll[i]) % len(OUTER_TEMPLATES)]
        if outer == OUTER_POSSESSIVE and show.startswith(("The ", "A ")):
            show = show.split(" ", 1)[1]
        title = outer.format(celeb=celeb, show=show)
        if kinds[i] == "series":
            unit = "Season" if int(unit_roll[i]) % 3 == 0 else "Episode"
            title = f"{title} {unit} {int(ep_num[i])}"
        names.append(title)
        actors.append(celeb)
        genres.append(genre)
    return names, actors, genres


def build_titles(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(300)
    kinds = [str(k) for k in ctx.dist.choice(n, TITLE_KINDS, TITLE_KIND_WEIGHTS)]
    names, actors, genres = _compose_titles(ctx, n, kinds)
    release = ctx.dist.dates_between(
        n, ctx.config.start_date - timedelta(days=5 * 365), ctx.config.end_date
    )
    # Runtime (minutes) is feature-length for films, one episode for series — a
    # clamped-normal keyed on `kind`, floored so no title goes implausibly short.
    # Maturity rating is an independent catalogue draw. Both use dedicated child
    # streams so they don't shift the composed-name / release / premium draws.
    runtime_means = np.array([RUNTIME_MINUTES_BY_KIND[k][0] for k in kinds])
    runtime_sds = np.array([RUNTIME_MINUTES_BY_KIND[k][1] for k in kinds])
    runtime = (
        np.maximum(ctx.rng.child("runtime").numpy.normal(runtime_means, runtime_sds), 5.0)
        .round()
        .astype(int)
    )
    maturity = ctx.rng.child("maturity").numpy.choice(
        np.asarray(MATURITY_RATINGS, dtype=object), size=n, p=MATURITY_RATING_WEIGHTS
    )
    # Eligible for a one-off premium rental (new/day-and-date releases). Kept the
    # last main-stream draw so its values are unchanged; avg_rating then keys off it
    # via a child stream — premium titles score higher.
    is_premium = ctx.dist.bernoulli(n, 0.25)
    rating_mean = np.where(is_premium, _AVG_RATING_PREMIUM_MEAN, _AVG_RATING_BASE_MEAN)
    avg_rating = np.clip(
        ctx.rng.child("avg_rating").numpy.normal(rating_mean, _AVG_RATING_SD), 1.0, 10.0
    ).round(1)
    return pl.DataFrame(
        {
            "title_id": [f"TTL-{i:05d}" for i in range(1, n + 1)],
            "name": names,
            "lead_actor": actors,
            "genre": genres,
            "kind": kinds,
            "runtime_minutes": runtime,
            "maturity_rating": maturity,
            "release_date": release,
            "is_premium": is_premium,
            "avg_rating": avg_rating,
        }
    )
