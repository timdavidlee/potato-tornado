---
description: Survey a collection's existing tables and suggest analytically-interesting fields to add to them, ordered quick-wins-first then high-leverage, and write the field-enrichment TODO doc — docs only, no generators, columns, or tests
model: opus
---

Look at a **collection**'s existing tables and propose *new columns worth adding to them* for
analytics richness — then capture the list as a `TODO.md` in the collection package. This is
the **field-enrichment** counterpart to [`/data-collection:propose`](propose.md): propose
designs a *whole new collection*, this one enriches the *tables that already exist*. It is
**docs only** — it does **not** edit any `build_<table>`, add columns to a generated frame,
touch `constants.py`, `register(...)`, `realism-guidance.md`, scenarios, or tests. It writes
one planning doc that a later run (the realism or scenario command) implements against.

Stay on the enrichment side of two lines:
- **Add fields to existing tables, don't design new tables.** A genuinely new entity (a new
  table + FKs) is `/data-collection:propose`'s job — note it as out-of-scope if it comes up.
- **Classify, don't plant.** Some suggested fields are plain realism enrichment (a new
  dimension to slice by); others carry a *surprising subset signal* and are therefore
  scenario-bearing. Label each, but don't build either here — realism fields route to
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

Suggest fields for **one** collection per run.

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

## 4. Write the enrichment TODO doc

Write `collections/<name>/TODO.md` (extend it in place if it already exists — don't clobber
prior items; add/curate). Order **quick wins first, then high-leverage items**, as a
checklist. Use this structure:

```markdown
# <name> — field-enrichment TODO

Candidate columns to add to the existing `<name>` tables for analytics richness. Ordered
quick wins first (realism enrichment), then high-leverage items (each unlocks an analysis
domain; scenario-bearing ones go through `/scenario:draft-or-propose`, not the realism
command).

For each: add the column in the relevant `tables/` builder with deterministic draws
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

## When the list is done

- [ ] **Revise `realism-guidance.md`.** After the fields above land, reconcile the realism
  rubric and invariant tests with the new columns (new dimensions to slice by, new
  invariants to pin). Run `/data-collection:review-edit-regen-for-realism` for this collection.
```

Always end the generated `TODO.md` with that closing "When the list is done" reminder to
revise `realism-guidance.md` — it's the last checklist item on every run, so the enrichment
work doesn't leave the realism rubric stale.

Keep it honest and buildable: real `table.column` targets, concrete dtypes, draws named
against real `ctx` primitives, and every field marked realism vs scenario-bearing. It should
be actionable later without re-deriving context.

## 5. Report

Summarize: the collection you enriched, how many quick-win vs high-leverage fields you
suggested (with the headline ones), which are scenario-bearing (and thus belong to
`/scenario:draft-or-propose`), any field that would need a new `core/distributions.py` helper
or that really implies a *new table* (out of scope → `/data-collection:propose`), and the doc
path. Note that nothing was implemented — the next step is to pick fields and realize them via
the realism or scenario command.
