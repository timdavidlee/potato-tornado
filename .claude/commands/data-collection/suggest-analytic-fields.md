---
description: Survey a collection's existing tables and suggest analytically-interesting fields to add to them (quick-wins-first then high-leverage), plus candidate new tables to add within the same collection, and write the enrichment TODO doc — docs only, no generators, columns, or tests
model: opus
---

Look at a **collection**'s existing tables and propose both *new columns worth adding to them*
and *new tables worth adding within the collection* for analytics richness — then capture the
list as a `TODO.md` in the collection package. This is the **enrichment** counterpart to
[`/data-collection:propose`](propose.md): propose designs a *whole new collection*, this one
works **inside an existing one** — enriching the tables that already exist and adding new
tables that join into them. It is **docs only** — it does **not** edit any `build_<table>`,
add columns or tables to a generated frame, touch `constants.py`, `register(...)`,
`realism-guidance.md`, scenarios, or tests. It writes one planning doc that a later run (the
realism or scenario command) implements against.

Stay on the enrichment side of two lines:
- **Work within this collection — new columns *and* new tables, but not a new collection.**
  Enrich existing tables with columns, and propose new tables that join into the collection (a
  new entity or event + its FK/`depends_on` into an existing table). A whole new *collection*
  (a fresh top-level domain, its own package) is still `/data-collection:propose`'s job — note
  it as out-of-scope if one comes up.
- **Classify, don't plant.** Some suggestions are plain realism enrichment (a new dimension to
  slice by); others carry a *surprising subset signal* and are therefore scenario-bearing.
  Label each, but don't build either here — realism suggestions route to
  [`/data-collection:review-edit-regen-for-realism`](review-edit-regen-for-realism.md),
  signal-bearing ones to [`/scenario:draft-or-propose`](../scenario/draft-or-propose.md).

Read the "Realism guidance" and "Scenarios" sections of
[collections/CLAUDE.md](../../../src/potato_tornado/collections/CLAUDE.md) first so your
suggestions fit the package's shape and the realism-vs-scenario distinction. Follow
[.claude/rules/python-style.md](../../rules/python-style.md) where it informs a suggested
dtype or draw.

## 1. Resolve the target

`$ARGUMENTS` names a **collection** (e.g. `hotel`, `clinic`), or is empty.

- **A collection** — enrich that one.
- **Empty** — prefer the collection named most recently in the conversation; if none, list
  the collections (`labor`, `hotel`, `clinic`, `streaming`, …) and ask which to enrich before
  writing anything.

Enrich **one** collection per run (its columns and any new tables).

## 2. Ground against the actual schema

Don't suggest a column that already exists, and don't suggest one the generators can't
plausibly draw. So first learn the real shape:

- Read the collection's `__init__.py` (the table wiring + `depends_on`), each `tables/*.py`
  builder, and `constants.py`. Note every existing column and how it's drawn.
- Generate once and list columns per table to confirm the live schema:

  ```bash
  uv run python -c "from potato_tornado.runner import generate; from potato_tornado.core.config import GenerationConfig; f = generate('<name>', GenerationConfig(seed=7, scale=0.3)); [print(t, list(df.columns)) for t, df in f.items()]"
  ```

- Skim `scenarios/*.md` and `realism-guidance.md` so you don't re-propose a signal or field
  that's already covered, and so scenario-bearing suggestions build on (not duplicate) the
  planted signals.
- Confirm each suggested field is buildable from the existing `ctx` primitives (`ctx.dist` /
  `ctx.rng` / `ctx.entities` / catalog literals). If a field would need a
  `core/distributions.py` helper that doesn't exist, say so — don't assume it.

## 3. Generate the candidate fields

For each existing table, ask what a hotel/clinic/etc. analyst would want to slice, join, or
measure by that the current columns can't answer. For every candidate note: the **target
table.column**, a **concrete Polars dtype**, a one-line **deterministic draw** sketch (which
`ctx` primitive, and what it keys off), what analysis it **unlocks**, and its **class**:

- **Quick win (realism enrichment)** — a new dimension to group/slice by with no surprising
  segment behaviour: `market_segment`, `guest_country`, `service_category`, `payment_method`,
  `star_rating`. These would be realized via the realism command.
- **High-leverage** — a field that unlocks a whole analysis domain (cancellation timing, guest
  satisfaction, per-class inventory, rate-plan economics). Many of these are
  **scenario-bearing**: if the interesting part is a *surprising* subset signal (non-refundable
  rates cancel less, satisfaction dips after an early checkout), flag it for
  `/scenario:draft-or-propose` and describe the signal — don't plant it.

Prefer fields that compose with existing columns (a `taxes_fees` that lets ADR/RevPAR derive,
an `adults`/`children` split that must sum to `party_size`) and introduce realistic texture
the dataset lacks (nullable columns, cost-vs-price margins). Keep referential integrity in
mind: a field that keys off another table implies a `depends_on` the implementer will add.

## 3b. Generate candidate new tables (within this collection)

Some analytics need a whole entity or event the collection doesn't model yet — one that would
be a **new table joined into the existing schema**, not just a column. Look for:

- **An entity referenced only implicitly.** A column or catalog hints at a thing that has no
  table of its own (an `adjuster` behind claims, a `rate_plan` behind reservations, a
  `department` behind shifts) — normalising it out into its own dim unlocks per-entity rollups.
- **A child/event table at a finer grain.** The current grain is one row per X, but an analyst
  wants the events under it (status-history, line items, endorsements, payments-over-time) —
  a new fact table with an FK back to the parent. Check `realism-guidance.md`'s **Deliberate
  simplifications** first: if "one row per claim, no reopenings" is an intentional choice, a
  status-history table contradicts it — note the tension rather than proposing it blindly.
- **A bridge for a many-to-many** the schema currently flattens.

Each candidate new table needs, at **sketch** level (not a full column spec): a **clear grain**
(one row per what), the **FK / `depends_on`** into an existing table (referential integrity is
non-negotiable — the FK must point at rows that exist), a **handful of key columns** with
dtypes and deterministic-draw sketches (the ones that matter, not every column), what it
**unlocks**, and its **class** (realism enrichment vs scenario-bearing). A new table is a
bigger lift than a column — it needs a new `tables/<table>.py` builder and a `TableSpec` (with
`depends_on`) in `__init__.py`, but **no** `core/registry.py` change (it's the same package).
Keep whole-new-*collection* ideas out (→ `/data-collection:propose`); only tables that join
into *this* collection belong here.

## 4. Write the enrichment TODO doc

Write `collections/<name>/TODO.md` (extend it in place if it already exists — don't clobber
prior items; add/curate). `TODO.md` is the collection's shared **open backlog**: it may also
hold an **Open realism items to investigate** section (owned by
`/data-collection:review-edit-regen-for-realism`) — leave it intact and add your enrichment
sections alongside it. Order **quick-win fields first, then high-leverage fields, then
candidate new tables** (a new table is the biggest lift), as a checklist. Use this structure:

```markdown
# <name> — enrichment TODO

Candidate columns and new tables to add to the existing `<name>` collection for analytics
richness. Ordered quick-win fields first (realism enrichment), then high-leverage fields, then
candidate new tables — each unlocks an analysis domain; scenario-bearing ones go through
`/scenario:draft-or-propose`, not the realism command.

For each: add the column/table in the relevant `tables/` builder with deterministic draws
(`ctx.dist` / `ctx.rng` / `ctx.entities`, name-keyed child streams — don't reorder existing
draws), then reconcile `realism-guidance.md` and pin tests. See collections/CLAUDE.md.

## Quick wins (realism enrichment)

- [ ] **`table.column`** (`dtype`) — draw sketch. Unlocks: <analysis>.
- ...

## High-leverage additions

### 1. `table.column`
- [ ] <what to add> (`dtype`, draw sketch).
- **Unlocks:** <analysis domain>.
- **Class:** realism enrichment, or **scenario-bearing** → route to /scenario:draft-or-propose
  with the signal named.

(one ### block per high-leverage item; add a "Later / depends-on" block for anything that
builds on an earlier item.)

## Candidate new tables (within this collection)

New tables that join into `<name>` (a new entity or event + its FK into an existing table),
sketch-level — enough to act on, not a full column spec. A whole new *collection* is
`/data-collection:propose`'s job, not this.

### `<new_table>`
- [ ] **Grain:** one row per <entity/event>. **Joins:** `depends_on=("<existing>",)`, FK
      `<new_table>.<existing>_id → <existing>`.
- **Key columns:** `col` (`dtype`, draw sketch), `col` (`dtype`, draw sketch), … (the handful
      that matter — not every column).
- **Unlocks:** <analysis domain the current schema can't reach>.
- **Class:** realism enrichment, or **scenario-bearing** → `/scenario:draft-or-propose` with
      the signal named.
- **Wiring:** new `tables/<new_table>.py` builder + a `TableSpec` (with `depends_on`) in
      `__init__.py`; no `registry.py` change (same package).

(one ### block per candidate table; omit this whole section if none came up.)

## When the list is done

- [ ] **Revise `realism-guidance.md`.** After the columns and tables above land, reconcile the
  realism rubric and invariant tests with the new columns and tables (new dimensions to slice
  by, new referential-integrity + non-negativity invariants to pin). Run
  `/data-collection:review-edit-regen-for-realism` for this collection.
```

Always end the generated `TODO.md` with that closing "When the list is done" reminder to
revise `realism-guidance.md` — it's the last checklist item on every run, so the enrichment
work doesn't leave the realism rubric stale.

Keep it honest and buildable: real `table.column` targets and real join keys, concrete dtypes,
draws named against real `ctx` primitives, and every column/table marked realism vs
scenario-bearing. It should be actionable later without re-deriving context.

## 4b. Log the run in `realism-log.md`

The backlog you just wrote is *open work*; `realism-log.md` records that a survey **happened**
(see collections/CLAUDE.md, "Realism log and TODO"). Append a dated bullet under
`## Field-enrichment runs` in `collections/<name>/realism-log.md` — how many quick-win vs
high-leverage fields **and how many candidate new tables** you surveyed, the headline ones, and
that the backlog landed in `TODO.md` with nothing implemented yet. Mirror the existing entries.
If the collection has no `realism-log.md` yet, seed it (status + this run) per
collections/CLAUDE.md. Don't put the open suggestions in the log — those live in `TODO.md`.

## 5. Report

Summarize: the collection you enriched, how many quick-win vs high-leverage fields **and
candidate new tables** you suggested (with the headline ones), which are scenario-bearing (and
thus belong to `/scenario:draft-or-propose`), any suggestion that would need a new
`core/distributions.py` helper or that really implies a *whole new collection* (out of scope →
`/data-collection:propose`), the `TODO.md` doc path, and the `realism-log.md` field-enrichment
run you appended. Note that nothing was implemented — the next step is to pick columns/tables
and realize them via the realism or scenario command.
