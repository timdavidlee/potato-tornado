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

import polars as pl

from potato_tornado.collections.streaming.constants import (
    CELEBRITIES,
    GENRE_TEMPLATES,
    GENRES,
    OUTER_POSSESSIVE,
    OUTER_TEMPLATES,
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
    return pl.DataFrame(
        {
            "title_id": [f"TTL-{i:05d}" for i in range(1, n + 1)],
            "name": names,
            "lead_actor": actors,
            "genre": genres,
            "kind": kinds,
            "release_date": release,
            # Eligible for a one-off premium rental (new/day-and-date releases).
            "is_premium": ctx.dist.bernoulli(n, 0.25),
        }
    )
