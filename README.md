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
| `hotel` | `properties`, `room_types`, `reservations`, `stays`, `service_orders`, `demand_forecast` | Reservations → actual stays, ancillary service spend, forecast vs. realised occupancy |

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

1. Create `src/potato_tornado/collections/<name>.py`.
2. Write one `_build_*` function per table. Each takes a
   [`GenContext`](src/potato_tornado/core/collection.py) and returns a
   `polars.DataFrame`. Use `ctx.dist` for distributions, `ctx.faker` for names,
   `ctx.n(base)` for scaled row counts, and `ctx.table("other")` to reference an
   already-built table (declare it in `depends_on`).
3. Assemble a `Collection` of `TableSpec`s and `register("<name>", build)`.
4. Add the module to `_BUILTIN_MODULES` in
   [`registry.py`](src/potato_tornado/core/registry.py).

See [`labor.py`](src/potato_tornado/collections/labor.py) for a worked example.

## Development

```bash
uv run ruff check .     # lint
uv run ruff format .    # format
uv run pyright          # type-check
uv run pytest           # test
```
