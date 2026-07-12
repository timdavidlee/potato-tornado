# Collections

Every collection under this directory is a **package** (`<name>/`), not a flat
module. The package name **is** the collection name passed to `register(...)` and
used on the CLI (`generate <name>`).

## Layout

```
collections/
  INVENTORY.md    directory-level index: one row per collection (table count,
                  realism status, scenario coverage, field-enrichment backlog).
                  Generated — regenerate with `/data-collection:refresh-inventory`
                  rather than hand-editing, so it stays in sync with the packages.
  <name>/
    __init__.py     assembles the Collection from its TableSpecs and calls
                    register("<name>", build) at import time.
    constants.py    domain reference data / catalogs (literal tables the
                    generators draw from). Optional — omit if the collection has
                    no shared literals.
    tables/
      __init__.py   re-exports every build_<table> so __init__ imports from one place.
      <table>.py    one module per table: `def build_<table>(ctx: GenContext) -> pl.DataFrame`.
    scenarios/
      <signal>.md   one markdown doc per intended analytical signal in the data.
    realism-guidance.md   the review rubric: plausibility rules the data must respect.
    realism-log.md  the running log of realism work — history, not backlog:
                    top-line status (converged / needs investigation), the realism
                    iterations done, and the field-enrichment runs done. Open items
                    live in TODO.md.
    TODO.md         the collection's open backlog — field-enrichment suggestions
                    (from `/data-collection:suggest-analytic-fields`) plus the open
                    realism items to investigate. A planning doc, not part of
                    generation.
```

`labor/` is the worked reference — copy its shape.

## Responsibilities of each part

- **`__init__.py`** — the assembly point and the *only* place that knows the table
  wiring. It imports the `build_<table>` functions from `tables/`, builds the
  `Collection(name=..., description=..., tables=(TableSpec(...), ...))`, declares
  each table's `depends_on`, and calls `register("<name>", build)`. Keep it thin:
  no generation logic here. Importing the package must have the side effect of
  registering the collection — that's how `registry._discover()` finds it, so the
  package path (`potato_tornado.collections.<name>`) goes in `_BUILTIN_MODULES`.

- **`tables/<table>.py`** — the generation logic for exactly one table. Export a
  public `build_<table>(ctx: GenContext) -> pl.DataFrame`. A `ctx` param that a
  trivial table doesn't use is fine (uniform signature). Table-local helpers and
  constants stay private (`_leading_underscore`) in the module that uses them —
  see `hotel/tables/stays.py` (`_rate_lookup`). Re-export the builder from
  `tables/__init__.py`.

- **`constants.py`** — the collection's fixed "seed" facts: catalog literals like
  the room-type ladder or the department list. A literal used by **two or more**
  tables (e.g. `hotel`'s `ROOM_TYPES`, read by both `room_types` and
  `reservations`) belongs here so there's one source of truth. Names are public
  (no underscore) since tables import them. A literal used by only one table can
  stay in that table's module — don't hoist speculatively.

- **`scenarios/<signal>.md`** — see below.

## Scenarios: the intended signals

A scenario documents a **signal deliberately planted in the generated data** — a
fact a student or agent querying the dataset is *meant* to discover. It is the
teaching "answer key": the no-show rate, the right-skewed overtime tail, the OTA
channel dominance. If a generator tunes a distribution to make a point, that point
gets a scenario doc.

**A scenario is an unexpected insight, usually about a subset of the data** — a
room class, a shift window, a region, a slice — not a fact that's simply true of
the dataset as a whole. "Night shifts no-show at 2x the day rate" is a scenario;
"no-shows happen sometimes" is not. A flat, expected fact about the whole table —
an invariant, a referential rule, a top-line mix or magnitude with no surprising
segment behind it — is a realism fact, not a scenario: it belongs in
`realism-guidance.md`'s Invariants or Distributions & mixes section instead. The
test: would a student be *surprised* by this, or would they simply expect the
data to look this way? Surprise is the bar. (A mix can still anchor a scenario if
the interesting part is how it inverts or concentrates in a slice — e.g. the
overall channel split flipping for upper-tier rooms — not the top-line number
alone.)

**Docs come first, code second.** Today scenarios are markdown only — the source
of truth. The planned next step is typed `Scenario` objects (name, signal,
tables, an optional `check(frames) -> bool` that verifies the signal holds on
freshly generated data). Those objects will be built **against these docs** so the
two can't drift — the doc is authored first and the object references it. So when
you add or retune a signal, **write/update the markdown**; don't invent a parallel
description elsewhere.

Every collection must ship at least one scenario doc — `tests/collections/
test_scenarios.py` enforces it.

### Scenario doc template

Filename is a kebab-case slug of the signal (`no-show-rate.md`,
`ota-is-the-largest-channel.md`). Keep this structure so the future `Scenario`
objects can be generated from it mechanically:

```markdown
# <one-line signal title>

- **Signal:** one sentence stating what is true in the data.
- **Tables:** `table.column`, ... (what to look at)
- **Magnitude:** the rough number to expect (rate / ratio / skew / bound).

<short prose: what to do to surface it, and why it's planted — the teaching point.>

## How to find it

<a SQL / query sketch that reveals the signal, with the expected value in a comment>
```

Keep magnitudes honest — they must match the generator. If you change a weight or
a distribution parameter in a `tables/` module, update the scenario magnitude in
the same change.

### Document-based scenarios (parse-the-prose signals)

Most scenarios are surfaced with a SQL query over clean columns. A **document-based
scenario** is a subtype where the analytical work is *parsing unstructured free-form
text* before any signal can be computed — an agent or student is handed prose
(markdown transaction records, a policy document of rules, a lab/financial report
with numbers buried in sentences) and must extract structured facts from it first.
Author these with [`/scenario:propose-document`](../../../.claude/commands/scenario/propose-document.md)
then [`/scenario:realize-document`](../../../.claude/commands/scenario/realize-document.md).

The convention that keeps them deterministic and testable:

- **The text column is always the source of truth.** A document is a row in a
  DuckDB table with a free-form text column (`body`), emitted by an ordinary
  `build_<docs>(ctx) -> pl.DataFrame`. This rides the existing generator / sink /
  determinism / test machinery with no new core plumbing. It can be a dedicated
  `documents` / `notes` table or a text column added to an existing table — decide
  per scenario. Size the row count through `ctx.n(base)` with a floor of 1 (scenario
  tests run at `scale=0.5`).
- **Render facts that already live in structured columns; don't invent an oracle.**
  Prefer a signal whose ground truth is already a real column elsewhere — the doc row
  carries `doc_id` + the FK + `body`, and the `body` merely *renders* those facts as
  prose. Then the test parses `body` and reconciles it against the source column, with
  no answer leaked into the text. Only if a fact exists nowhere else do you ship an
  answer-key column beside `body`; when you do, flag in the doc that it's withheld when
  handing data to students.
- **Derive numbers into the prose, never re-sample them.** Format the ground-truth
  value into the template string; never draw the same quantity twice (that desyncs the
  prose from the answer key). Vary 2–3 template phrasings off a name-keyed
  `ctx.rng.child(...)` stream so the parser must handle real variation, not one fixed
  layout.
- **Files on disk are an optional derived export, not the source of truth.** When a
  scenario genuinely wants a *folder of files* (one policy doc, a handful of reports),
  materialize the deterministic text column out to `docs/<doc_id>.md` in a post-
  `generate()` helper or CLI verb — never inside `generate()`, and never `depends_on`
  or read those files back (same rule as `working_cache/`).

The doc extends the standard template with **Documents** (which table.column holds the
text, doc type, rough count), **Parse target** (what to extract, with a snippet), and
**Ground truth** (structured-column reconciliation vs. a shipped answer-key column);
the scenario test is **two-layer** — (a) deterministic extraction from `body` equals
the ground truth, proving the signal is recoverable from prose, then (b) the analytical
assertion on the parsed values.

## Realism guidance: the review rubric

Alongside `scenarios/`, every collection ships one `realism-guidance.md` at the
package root (next to `__init__.py`). Where a scenario says what a student should
*find*, realism guidance says what the data must never get *wrong* — it's the
rubric a reviewer (human or Claude) checks freshly generated data against. It has
three jobs:

- **Invariants** — hard rules that must always hold (referential integrity,
  temporal ordering, non-negativity, arithmetic identities like
  `revenue = rate × nights`). A violation is a bug.
- **Distributions & mixes** — the intended shapes and weights, with the rough
  magnitudes, so a reviewer can tell "plausible" from "drifted".
- **Deliberate simplifications** — where the data knowingly departs from reality
  for teaching clarity (e.g. hotel rates have no weekday/weekend variation). This
  is what stops a reviewer from "fixing" an intentional choice — and it's the
  natural shortlist of candidates to promote into new scenarios.

Like scenario magnitudes, these numbers must track the generators: if you retune a
`tables/` distribution, update the matching line in `realism-guidance.md` in the
same change. `tests/collections/test_scenarios.py` enforces that the file exists.
The `labor` / `hotel` docs are the worked references.

## Realism log and TODO: history vs. backlog

Where `realism-guidance.md` is the *rubric* (the rules the data must respect),
`realism-log.md` and `TODO.md` (same package root) split the surrounding workflow
into **history** and **backlog** — the log is what's been done, the TODO is what's
left.

`realism-log.md` is a pure **log**: a **top-line status** (`Converged` — sweeps done,
residual items are deliberate simplifications — vs `Needs investigation` — unswept
too-synthetic risks remain), the **realism iterations** done (each
`/data-collection:review-edit-regen-for-realism` pass: what was measured, found, and
fixed, referencing the commit), and the **field-enrichment runs** done (each
`/data-collection:suggest-analytic-fields` pass: what was surveyed and which columns
shipped). It records history only — no open items — so append an entry whenever you
run a pass and re-evaluate the status.

`TODO.md` is the matching **open backlog**, in two sections: **field-enrichment**
suggestions (candidate new columns, quick-wins-first, written by
`/data-collection:suggest-analytic-fields`) and **open realism items to investigate**
(candidate too-synthetic artifacts — flat/uniform distributions, constant
sub-population averages, round-number lattices, absent noise — for
`/data-collection:review-edit-regen-for-realism`). When you clear an item, implement
it and move it into the log as a run. Both are planning/history docs, not part of
generation, so no test enforces them.

The dated working checklists under [`docs/todos/`](../../../docs/todos/) (written by
`/data-collection:scan-todos`, worked by `/data-collection:tackle-todos`) are
**progress trackers, not a second backlog**: each links into this `TODO.md` for the
item substance (recipe, class, definition of done) and carries none of its own, so the
substance has a single place to edit. Ticking an item means ticking it in both the dated
checklist and `TODO.md`, then recording the run in `realism-log.md`.

## Adding a collection

1. `mkdir collections/<name>/` with `__init__.py`, `tables/` (+ `__init__.py`),
   `scenarios/`, and `constants.py` if it has shared literals.
2. Write one `build_<table>` per table in `tables/`; re-export them from
   `tables/__init__.py`.
3. In `__init__.py`, assemble the `Collection` and `register("<name>", build)`.
4. Add `"potato_tornado.collections.<name>"` to `_BUILTIN_MODULES` in
   [`core/registry.py`](../core/registry.py).
5. Write at least one `scenarios/*.md` for the signals you planted.
6. Write `realism-guidance.md` at the package root — the review rubric (invariants,
   mixes, deliberate simplifications) for the collection.
7. Seed `realism-log.md` (status + the initial build as the first realism iteration)
   and `TODO.md` (the open too-synthetic areas to investigate; field-enrichment
   suggestions get added when `/data-collection:suggest-analytic-fields` is run).
8. Add a row to the README collections table.
9. Mirror tests under `tests/collections/<name>/` (behavioural tests go through
   `generate("<name>", ...)`); the parametrized `tests/test_runner.py` picks the
   collection up automatically for determinism / non-empty checks.

## Determinism still applies

Splitting a collection across files changes nothing about determinism: random
streams are name-keyed off the **table name** (`Rng.child(name)`), not the module
path. Draw only from `ctx.dist` / `ctx.rng` / `ctx.entities`; never wall-clock,
`random`, or the numpy global RNG. Keep the determinism test green.
