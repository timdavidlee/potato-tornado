"""The table / collection model.

A :class:`Collection` is a named bundle of related tables (a "data collection
definition", e.g. *labor assignment and utilization*). Each table is described by
a :class:`TableSpec` whose ``build`` function receives a :class:`GenContext` — the
run's config plus a name-keyed random stream plus every table built so far — and
returns a Polars DataFrame. Tables declare dependencies so a table can reference
the rows of another (e.g. assignments referencing employees).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import polars as pl

from potato_tornado.core.config import GenerationConfig
from potato_tornado.core.distributions import Distributions
from potato_tornado.core.rng import Rng
from potato_tornado.pools.provider import EntityProvider, GeneratedEntities, PooledEntities

if TYPE_CHECKING:
    from faker import Faker

    from potato_tornado.pools.store import EntityPool

TableBuilder = Callable[["GenContext"], pl.DataFrame]


class GenContext:
    """Everything a table builder needs, scoped to a single table.

    A fresh context is handed to each ``TableSpec.build`` call. ``rng`` and
    ``dist`` are derived from the table name so builds are independent and stable.
    ``entities`` yields people / companies / cities either freshly generated or
    sampled from a persisted pool, depending on the run's config. Already-built
    tables in the same collection are available via :meth:`table`.
    """

    def __init__(
        self,
        *,
        config: GenerationConfig,
        rng: Rng,
        faker: Faker,
        entities: EntityProvider,
        built: dict[str, pl.DataFrame],
    ) -> None:
        self.config = config
        self.rng = rng
        self.dist = Distributions(rng)
        self.faker = faker
        self.entities = entities
        self._built = built

    def table(self, name: str) -> pl.DataFrame:
        """Return an already-generated table in this collection by name."""
        try:
            return self._built[name]
        except KeyError:
            raise KeyError(f"table {name!r} is not available; declare it in `depends_on`") from None

    def n(self, base: int) -> int:
        """Shorthand for ``self.config.scaled(base)``."""
        return self.config.scaled(base)


@dataclass(frozen=True, slots=True)
class TableSpec:
    """Declarative description of one table within a collection."""

    name: str
    build: TableBuilder
    depends_on: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True, slots=True)
class Collection:
    """A named set of interrelated tables."""

    name: str
    description: str
    tables: tuple[TableSpec, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        names = [t.name for t in self.tables]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"collection {self.name!r} has duplicate tables: {sorted(dupes)}")

    def build_order(self) -> list[TableSpec]:
        """Topologically sort tables so dependencies build first."""
        by_name = {t.name: t for t in self.tables}
        ordered: list[TableSpec] = []
        seen: set[str] = set()
        visiting: set[str] = set()

        def visit(spec: TableSpec) -> None:
            if spec.name in seen:
                return
            if spec.name in visiting:
                raise ValueError(f"circular dependency involving {spec.name!r}")
            visiting.add(spec.name)
            for dep in spec.depends_on:
                if dep not in by_name:
                    raise ValueError(f"table {spec.name!r} depends on unknown table {dep!r}")
                visit(by_name[dep])
            visiting.discard(spec.name)
            seen.add(spec.name)
            ordered.append(spec)

        for spec in self.tables:
            visit(spec)
        return ordered

    def generate(
        self,
        config: GenerationConfig,
        faker: Faker,
        pool: EntityPool | None = None,
    ) -> dict[str, pl.DataFrame]:
        """Build every table in dependency order and return them by name.

        When ``pool`` is given, entity fields (names / companies / cities) are
        sampled from it; otherwise they are generated from scratch via ``faker``.
        """
        master = Rng(config.seed).child(self.name)
        # Seed Faker deterministically for this collection. Build order is stable,
        # so Faker's own sequential state stays reproducible across runs.
        faker.seed_instance(master.seed)
        built: dict[str, pl.DataFrame] = {}
        for spec in self.build_order():
            table_rng = master.child(spec.name)
            entities: EntityProvider = (
                PooledEntities(pool, table_rng.child("entities"))
                if pool is not None
                else GeneratedEntities(faker)
            )
            ctx = GenContext(
                config=config,
                rng=table_rng,
                faker=faker,
                entities=entities,
                built=built,
            )
            built[spec.name] = _normalize(spec.build(ctx))
        return built

    def __iter__(self) -> Iterator[TableSpec]:
        return iter(self.tables)


def _normalize(df: pl.DataFrame) -> pl.DataFrame:
    """Re-infer ``Object`` columns into concrete Polars dtypes.

    Building columns from numpy object arrays of ``date``/``datetime``/``str``
    yields ``Object`` columns, which don't support value comparison and don't map
    cleanly onto database types. Rebuilding each such column from its Python
    values lets Polars infer a proper ``Date`` / ``Datetime`` / ``Utf8`` dtype.
    """
    object_cols = [name for name, dtype in df.schema.items() if dtype == pl.Object]
    if not object_cols:
        return df
    return df.with_columns([pl.Series(name, df[name].to_list()) for name in object_cols])
