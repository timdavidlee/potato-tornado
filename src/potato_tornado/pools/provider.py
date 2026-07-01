"""Two interchangeable sources of person / company / city entities.

A collection asks its :class:`GenContext` for entities without caring where they
come from. The context is wired with one of:

- :class:`GeneratedEntities` — synthesises fresh entities every call via Faker
  (the default, "from scratch" path), or
- :class:`PooledEntities` — samples rows from a persisted :class:`EntityPool`
  (the "pull from a known pool" path).

Both satisfy :class:`EntityProvider`, so the call sites in ``collections/`` are
identical under either mode.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import polars as pl
from faker import Faker

from potato_tornado.core.rng import Rng
from potato_tornado.generators.common import people_frame
from potato_tornado.pools.store import EntityPool


@runtime_checkable
class EntityProvider(Protocol):
    """A source of synthetic people, companies and cities of a requested size."""

    def people(self, n: int) -> pl.DataFrame:
        """``n`` rows with ``full_name`` and unique ``email`` columns."""
        ...

    def companies(self, n: int) -> list[str]:
        """``n`` company names (may repeat)."""
        ...

    def cities(self, n: int) -> list[str]:
        """``n`` city names (may repeat)."""
        ...


class GeneratedEntities:
    """Synthesise entities on demand from a (seeded) Faker instance."""

    __slots__ = ("_faker",)

    def __init__(self, faker: Faker) -> None:
        self._faker = faker

    def people(self, n: int) -> pl.DataFrame:
        return people_frame(self._faker, n)

    def companies(self, n: int) -> list[str]:
        return [self._faker.company() for _ in range(n)]

    def cities(self, n: int) -> list[str]:
        return [self._faker.city() for _ in range(n)]


class PooledEntities:
    """Sample entities from a persisted :class:`EntityPool`.

    Sampling is with replacement and driven by ``rng``, so it is deterministic and
    stable per table. Sampled emails are made unique within each :meth:`people`
    call (a numeric ``+k`` suffix disambiguates repeats), preserving the
    uniqueness the generated path guarantees.
    """

    __slots__ = ("_pool", "_rng")

    def __init__(self, pool: EntityPool, rng: Rng) -> None:
        self._pool = pool
        self._rng = rng

    def people(self, n: int) -> pl.DataFrame:
        frame = self._pool.people
        names = frame["full_name"].to_list()
        emails = frame["email"].to_list()
        idx = self._rng.numpy.integers(0, frame.height, size=n)
        picked = [int(i) for i in idx]
        return pl.DataFrame(
            {
                "full_name": [names[i] for i in picked],
                "email": _uniquify([emails[i] for i in picked]),
            }
        )

    def companies(self, n: int) -> list[str]:
        return self._sample(self._pool.companies["company"].to_list(), n)

    def cities(self, n: int) -> list[str]:
        return self._sample(self._pool.cities["city"].to_list(), n)

    def _sample(self, pool: list[str], n: int) -> list[str]:
        idx = self._rng.numpy.integers(0, len(pool), size=n)
        return [pool[int(i)] for i in idx]


def _uniquify(emails: list[str]) -> list[str]:
    """Return ``emails`` with duplicates disambiguated by a ``+k`` local-part tag.

    Example: ``["a@x.io", "a@x.io"]`` -> ``["a@x.io", "a+2@x.io"]``.
    """
    seen: set[str] = set()
    out: list[str] = []
    for email in emails:
        if email not in seen:
            seen.add(email)
            out.append(email)
            continue
        local, _, domain = email.partition("@")
        k = 2
        while f"{local}+{k}@{domain}" in seen:
            k += 1
        candidate = f"{local}+{k}@{domain}"
        seen.add(candidate)
        out.append(candidate)
    return out
