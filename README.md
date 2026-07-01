# potato-tornado

Synthetic dataset generators for teaching, designed to pair with the *fluffy
potato curriculum*. Each generator produces a **collection** — a set of related
tables with realistic distributions and referential integrity — and loads it
into a **DuckDB** (or **Postgres**) database that an agent or a student can query.

Data is fully synthetic but aims to mimic realistic distributions (right-skewed
money and durations, weighted categories, no-shows, forecast error, etc.).

## Quick start

```bash
uv sync                       # install (add --extra postgres for the Postgres sink)

uv run potato-tornado list                     # list collections
uv run potato-tornado describe labor           # show a collection's tables
uv run potato-tornado generate labor --out labor.duckdb --scale 2 --seed 7
```

Then query the result:

```bash
uv run python -c "import duckdb; print(duckdb.connect('labor.duckdb').sql('SHOW TABLES'))"
```

Generation is **deterministic**: the same `--seed`, `--scale` and date window
always produce byte-identical tables.

## Built-in collections

| Collection | Tables | Teaches |
|------------|--------|---------|
| `labor` | `departments`, `employees`, `shifts`, `assignments`, `time_entries` | Labor assignment & utilization: plan vs. actual attendance, overtime, no-shows |
| `hotel` | `properties`, `room_types`, `reservations`, `stays`, `service_orders`, `room_upgrades`, `stay_changes`, `demand_forecast` | Reservations → actual stays, ancillary service spend & fees, room-class upgrades, stay-length amendments, forecast vs. realised occupancy |
| `clinic` | `providers`, `patients`, `appointments` | Outpatient appointment scheduling: patient/provider bookings through a completed / no-show / cancelled lifecycle (placeholder — slots/visits/invoices to come) |
| `streaming` | `plans`, `titles`, `subscribers`, `subscriptions`, `rentals` | Streaming service: recurring subscriptions on a plan ladder plus one-off premium (PVOD) rentals (placeholder title names) |

## Using it as a library

```python
from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate, generate_to_sink
from potato_tornado.sinks.duckdb_sink import DuckDBSink

cfg = GenerationConfig(seed=42, scale=1.0)

tables = generate("hotel", cfg)          # dict[str, polars.DataFrame]

with DuckDBSink("hotel.duckdb") as sink:  # or PostgresSink(dsn)
    generate_to_sink("hotel", sink, cfg)
```

## Adding a collection

Each collection is a **package** `src/potato_tornado/collections/<name>/`:

```
<name>/
  __init__.py     assembles the Collection and calls register("<name>", build)
  constants.py    domain reference data / catalogs (optional)
  tables/         one module per table: build_<table>(ctx) -> polars.DataFrame
  scenarios/      markdown docs for the intended signals planted in the data
```

1. Write one `build_<table>` per table under `tables/`. Each takes a
   [`GenContext`](src/potato_tornado/core/collection.py) and returns a
   `polars.DataFrame`. Use `ctx.dist` for distributions, `ctx.entities` for
   people / companies / cities, `ctx.n(base)` for scaled row counts, and
   `ctx.table("other")` to reference an already-built table (declare it in
   `depends_on`). Re-export the builders from `tables/__init__.py`.
2. Assemble a `Collection` of `TableSpec`s and `register("<name>", build)` in
   `__init__.py`.
3. Add the package to `_BUILTIN_MODULES` in
   [`registry.py`](src/potato_tornado/core/registry.py).
4. Document the signals you planted in `scenarios/*.md` (the teaching "answer key").

See [`labor/`](src/potato_tornado/collections/labor) for a worked example and
[`collections/CLAUDE.md`](src/potato_tornado/collections/CLAUDE.md) for the full
pattern.

## Entity pools

Names, emails, companies and cities can either be **generated from scratch** on
every run (the default) or **sampled from a pool** you build once offline and
persist. Same call site in a collection (`ctx.entities.people(n)`) — the source is
chosen by config.

```bash
uv run potato-tornado build-pool ./pool --size 5000 --seed 7   # generate + persist (Parquet)
uv run potato-tornado generate labor --out labor.duckdb --pool ./pool   # sample from it
```

From Python, point a config at the pool directory:

```python
from pathlib import Path

from potato_tornado.core.config import GenerationConfig
from potato_tornado.pools import build_pool
from potato_tornado.runner import generate

build_pool(GenerationConfig(seed=7), size=5000).save("pool")
tables = generate("labor", GenerationConfig(pool_dir=Path("pool")))  # names drawn from the pool
```

Sampling is deterministic and keeps emails unique per table; omit `pool_dir` to
generate entities from scratch instead.

## Development

```bash
uv run ruff check .     # lint
uv run ruff format .    # format
uv run pyright          # type-check
uv run pytest           # test
```
