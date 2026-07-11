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
| `labor` | `departments`, `employees`, `shifts`, `assignments`, `time_entries`, `projects`, `project_members` | Labor assignment & utilization: plan vs. actual attendance, overtime, no-shows, plus cross-functional project staffing, off-site location mix, and consulting economics (cost vs. bill rates, realization, client/industry/billing dimensions) |
| `hotel` | `properties`, `room_types`, `reservations`, `stays`, `service_orders`, `room_upgrades`, `stay_changes`, `demand_forecast` | Reservations → actual stays, ancillary service spend & fees, room-class upgrades, stay-length amendments, forecast vs. realised occupancy |
| `clinic` | `providers`, `patients`, `slots`, `appointments`, `visits`, `invoices` | Outpatient slot → booking → visit → billing workflow: provider slot utilisation, a no-show rate that rises with booking lead time, per-visit-type duration overrun, and self-pay-concentrated accounts receivable |
| `streaming` | `plans`, `regions`, `actors`, `titles`, `title_availability`, `subscribers`, `subscriptions`, `rentals` | Streaming service: recurring subscriptions on a plan ladder plus one-off premium (PVOD) rentals; regional catalogue licensing (a subscriber only rents titles licensed in their region); parody titles pair a famous figure (`lead_actor`) with an off-genre show (`genre`) |
| `logistics` | `carriers`, `warehouses`, `shipments`, `scan_events`, `deliveries` | Parcels through a carrier network: a per-shipment tracking event log (variable-length timeline, first/last scan, elapsed time) plus promised-vs-actual SLA — an on-time rate that degrades with shipping distance (zone), a weight-driven right-skewed cost tail, and a terminal delivered/returned/lost outcome recovered from the scans |
| `insurance` | `brokers`, `adjusters`, `policyholders`, `policies`, `premium_billing`, `coverage_lines`, `quotes`, `claims`, `claim_payments`, `claim_status_history` | Property-and-casualty book on a frequency-severity model: most policies never claim, the few that do have a heavy-tailed payout; a loss ratio (paid ÷ premium) that rises with risk tier; and an adjudication funnel (reported → approved/partial/denied → paid) surfaced by left-joining claims to payments |
| `retail` | `customers`, `products`, `orders`, `order_items`, `returns`, `order_charges` | Online store with a one-to-many basket fan-out (`orders` header → variable `order_items` lines, basket value = Σ line totals, with per-order shipping/tax totals in `order_charges`) and a category-dependent return funnel: return rate ranges ~2% (consumables) to ~22% (apparel), and the return-reason mix shifts by category (apparel skews fit/mind-change, electronics skews defective) |

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
  realism-guidance.md  review rubric: invariants, mixes, deliberate simplifications
  realism-log.md  running log of realism work: status + iterations + enrichment runs
  TODO.md         open backlog: field-enrichment suggestions + open realism items
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
4. Document the signals you planted in `scenarios/*.md` (the teaching "answer key"),
   and write `realism-guidance.md` — the review rubric of invariants, mixes, and
   deliberate simplifications for the collection.
5. Seed `realism-log.md` (the running log of realism work — status plus the
   iterations and field-enrichment runs done) and `TODO.md` (the open backlog —
   field-enrichment suggestions plus open realism items to investigate). The log is
   history; open work lives in the TODO.

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

## Seeding Postgres

Load collections into a Postgres database — **one schema per collection**, so
`hotel.reservations` and `labor.employees` live side by side in one database.
Requires the `postgres` extra:

```bash
uv sync --extra postgres
uv run potato-tornado seed postgresql://user:pass@localhost:5432/teaching   # all collections
uv run potato-tornado seed postgresql://... -c hotel -c labor --scale 2     # a subset
```

A bare `postgresql://` DSN is routed to the psycopg 3 driver automatically. From
Python, use `PostgresSink` directly (it takes the same DSN and a `schema`):

```python
from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate_to_sink
from potato_tornado.sinks.postgres_sink import PostgresSink

with PostgresSink("postgresql://user:pass@localhost:5432/teaching", schema="hotel") as sink:
    generate_to_sink("hotel", sink, GenerationConfig(seed=7))
```

## Development

```bash
uv run ruff check .     # lint
uv run ruff format .    # format
uv run pyright          # type-check
uv run pytest           # test
```
