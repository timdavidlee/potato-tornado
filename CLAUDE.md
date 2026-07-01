# CLAUDE.md

Guidance for working in this repo.

## What this is

`potato-tornado` generates **synthetic teaching datasets** and loads them into a
DuckDB / Postgres database. A "collection" is a group of related tables (e.g.
`labor`, `hotel`) with realistic distributions and referential integrity.

## Layout

```
src/potato_tornado/
  core/
    config.py       GenerationConfig (seed, scale, date window)
    rng.py          Rng — deterministic, name-keyed child streams
    distributions.py  Distributions — realistic sampling helpers over an Rng
    collection.py   GenContext, TableSpec, Collection (+ topological build order,
                    Object->concrete-dtype normalization)
    registry.py     register() / get_collection() / iter_collections()
  generators/       cross-collection helpers (people, ids)
  pools/            entity pools: EntityProvider (generate from scratch vs. sample
                    a persisted EntityPool) + build_pool()/save/load (Parquet)
  collections/      one module per collection, each calls register(...)
  sinks/            Sink protocol + DuckDBSink (core) and PostgresSink (extra)
  runner.py         generate() / generate_to_sink()
  cli.py            Typer app: list / describe / generate / build-pool
tests/
```

## Conventions

- **Determinism is a hard requirement.** Same `(seed, scale, dates)` → identical
  output. Never use unseeded randomness, `Math.random`, wall-clock time, or the
  numpy global RNG. Draw from `ctx.dist` / `ctx.rng` (both derive from the seed).
  `ctx.faker` is seeded per-collection. There is a determinism test per
  collection — keep it green.
- **Random streams are name-keyed** (`Rng.child(name)`) so adding a table doesn't
  shift the draws of existing tables.
- **Row counts scale** via `ctx.n(base)` — author against `scale=1.0`.
- **Table builders return `polars.DataFrame`.** Date/datetime/string columns may
  start as numpy object arrays; `Collection.generate` normalizes `Object` columns
  to concrete Polars dtypes, so don't fight the dtype at the call site.
- **Dependencies are explicit:** to read another table via `ctx.table("x")`,
  declare `depends_on=("x",)`. Build order is topological; cycles raise.
- Keep referential integrity real (FKs point at rows that exist).
- **Entity fields go through `ctx.entities`** (`.people(n)` → `full_name`/`email`
  frame, `.companies(n)`, `.cities(n)`) — not `ctx.faker` directly. The same call
  site works whether the run generates from scratch or samples a persisted pool
  (`GenerationConfig.pool_dir`); pooled sampling is name-keyed off the table's
  `ctx.rng`, so it stays deterministic.

## Adding a collection

New module in `collections/`, `register("<name>", build)` at import time, then
add the module path to `_BUILTIN_MODULES` in `core/registry.py`. Add a row to the
README table. The parametrized tests in `tests/test_runner.py` will pick it
up automatically for determinism / non-empty checks.

## Checks (run before finishing)

```bash
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run pytest
```
