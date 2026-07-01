"""Common, cross-collection generation helpers."""

from __future__ import annotations

import polars as pl
from faker import Faker


def sequential_ids(n: int, *, prefix: str = "", width: int = 5, start: int = 1) -> pl.Series:
    """A Polars string Series of stable, zero-padded ids, e.g. ``EMP-00001``.

    When ``prefix`` is empty the ids are plain integers instead.
    """
    if prefix:
        values = [f"{prefix}{i:0{width}d}" for i in range(start, start + n)]
        return pl.Series("id", values, dtype=pl.Utf8)
    return pl.Series("id", range(start, start + n), dtype=pl.Int64)


def people_frame(faker: Faker, n: int) -> pl.DataFrame:
    """A small people table (name, email) drawn from Faker.

    Faker is expected to have been seeded by the caller for reproducibility.
    """
    names = [faker.name() for _ in range(n)]
    emails = [faker.unique.email() for _ in range(n)]
    return pl.DataFrame({"full_name": names, "email": emails})
