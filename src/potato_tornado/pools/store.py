"""Persisted entity pools: generate a set of synthetic entities offline, save it
to disk, and reload it later to sample from.

A pool is three Polars frames (people, companies, cities) written as Parquet, one
file per category::

    pool_dir/
      people.parquet      # columns: full_name, email
      companies.parquet   # column: company
      cities.parquet      # column: city

Build one with :func:`build_pool` (deterministic in ``config.seed``), persist it
with :meth:`EntityPool.save`, and point a run at it via
``GenerationConfig(pool_dir=...)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import polars as pl
from faker import Faker

from potato_tornado.core.config import GenerationConfig
from potato_tornado.generators.common import people_frame

_PEOPLE_FILE = "people.parquet"
_COMPANIES_FILE = "companies.parquet"
_CITIES_FILE = "cities.parquet"


@dataclass(frozen=True, slots=True)
class EntityPool:
    """A materialised set of synthetic entities to sample from.

    Attributes:
        people: Frame with ``full_name`` and (unique) ``email`` columns.
        companies: Frame with a single ``company`` column.
        cities: Frame with a single ``city`` column.
    """

    people: pl.DataFrame
    companies: pl.DataFrame
    cities: pl.DataFrame

    def save(self, directory: str | Path) -> None:
        """Write the pool to ``directory`` as one Parquet file per category."""
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        self.people.write_parquet(d / _PEOPLE_FILE)
        self.companies.write_parquet(d / _COMPANIES_FILE)
        self.cities.write_parquet(d / _CITIES_FILE)

    @classmethod
    def load(cls, directory: str | Path) -> EntityPool:
        """Read a pool previously written by :meth:`save`."""
        d = Path(directory)
        return cls(
            people=pl.read_parquet(d / _PEOPLE_FILE),
            companies=pl.read_parquet(d / _COMPANIES_FILE),
            cities=pl.read_parquet(d / _CITIES_FILE),
        )


def build_pool(config: GenerationConfig, *, size: int = 5000) -> EntityPool:
    """Generate a pool of ``size`` entities per category, from scratch via Faker.

    Deterministic in ``config.seed``: the same seed and size yield an identical
    pool. This is the offline half of the "pool" path — run it once, ``save`` the
    result, then sample from it across many generation runs.
    """
    if size <= 0:
        raise ValueError(f"size must be positive, got {size}")
    faker = Faker()
    faker.seed_instance(config.seed)
    return EntityPool(
        people=people_frame(faker, size),
        companies=pl.DataFrame({"company": [faker.company() for _ in range(size)]}),
        cities=pl.DataFrame({"city": [faker.city() for _ in range(size)]}),
    )
