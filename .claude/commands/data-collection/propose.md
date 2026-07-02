---
description: Propose a new data collection (purpose, tables, distributions, candidate scenarios) and write the proposal doc — docs only, no generators, register(), or tests
model: opus
---

Design a brand-new **collection** and capture it as a proposal doc. This is the
*docs-first* step, one level up from [`/scenario:propose`](../scenario/propose.md): pick a
domain worth teaching, shape it into a concrete set of related tables with realistic
distributions and referential integrity, and write the markdown answer key for the whole
collection. It does **not** create the `collections/<name>/` package, write any
`build_<table>`, call `register(...)`, touch `_BUILTIN_MODULES`, or add tests — that
implementation step comes later, driven by the doc this command produces.

Read [collections/CLAUDE.md](../../../src/potato_tornado/collections/CLAUDE.md) first — it
defines the package layout, the scenario doc template, the realism-guidance rubric, and the
"Adding a collection" checklist your proposal should be implementable against. Follow
[.claude/rules/python-style.md](../../rules/python-style.md) and the determinism/`ctx`
conventions in [CLAUDE.md](../../../CLAUDE.md) where relevant.

## 1. Read `$ARGUMENTS`

`$ARGUMENTS` is a domain or theme for the collection (e.g. `airline`, `retail returns`,
`gym memberships`, `library lending`). Two modes:

- **Shape** — `$ARGUMENTS` names a domain. Turn it into a concrete, buildable collection.
- **Propose** — `$ARGUMENTS` is empty or vague. Survey what exists (step 2), then propose a
  short menu of 2–3 candidate domains that fill a gap, recommend the strongest, and ask
  which to write up before drafting the full doc.

## 2. Ground the proposal against what already exists

A new collection is only worth proposing if it teaches something the current set doesn't
already cover, and if it can be built on the existing core.

- Read the **Built-in collections** table in [README.md](../../../README.md) and skim each
  existing `collections/<name>/__init__.py` to see the domains, table shapes, and signals
  already taught. Don't propose a near-duplicate of `labor`, `hotel`, `clinic`, or
  `streaming` — aim for a distinct workflow / distribution story.
- Read `labor/` (the worked reference) and one other collection end to end so your proposed
  tables, `depends_on` wiring, and column dtypes match how collections are actually built.
- Confirm the building blocks you'll lean on exist: entity fields must come from
  `ctx.entities` (`.people`/`.companies`/`.cities`), sampling from `ctx.dist` / `ctx.rng`,
  and event dates should spread across the full `[start_date, end_date)` window
  (`ctx.config.span_days`), ~3 years. If the domain needs a distribution helper that
  `core/distributions.py` doesn't have, say so — flag it as "new helper needed", don't
  assume it exists.

## 3. Design the collection

Commit to one coherent domain and design it concretely. A good collection is: a small set
of related tables (roughly 3–7) with real FKs, at least one right-skewed money/duration
distribution, a plan-vs-actual or funnel workflow that creates a teachable signal, and
enough shape to carry 2–3 distinct scenarios. Decide:

- **Tables** — for each, its purpose, key columns with **concrete Polars dtypes**, the FK(s)
  it holds, and its `depends_on`. Sketch the build order so it's a DAG (no cycles).
- **Constants** — any catalog literals shared by two or more tables (the `constants.py`
  candidates).
- **Distributions & magnitudes** — the intended shapes and rough numbers (skew, weights,
  rates, bounds). These are targets to plant later; mark them as such, don't fabricate a
  measured value.
- **Candidate scenarios** — 2–3 signals the data would deliberately carry, each checkable
  with a concrete query. These become `scenarios/*.md` when the collection is built.
- **Realism** — the invariants that must always hold (referential integrity, temporal
  ordering, non-negativity, arithmetic identities) and any deliberate simplifications.

## 4. Write the proposal doc

Write `proposals/<name>.md` (create the `proposals/` dir if it doesn't exist), where
`<name>` is the kebab/snake collection name as it would be passed to `register(...)` and the
CLI. Use this structure:

```markdown
# <name> — collection proposal

- **Domain:** one line on what real-world workflow this models.
- **Teaching value:** what an agent/student learns that existing collections don't cover.

## Tables

For each table:
- `<table>` — purpose. Columns: `col: dtype`, `fk_col: dtype → other_table.pk`, ...
  `depends_on=(...)`.

(Build order must be a DAG — list it.)

## Constants

Shared catalog literals (the `constants.py` candidates), or "none".

## Distributions & target magnitudes

The intended shapes/weights/rates, each flagged as a target to be planted.

## Candidate scenarios

2–3 bullets, each: signal (one sentence), tables/columns, target magnitude, and a
one-line "how to find it" query sketch. These become `scenarios/*.md` on build.

## Realism guidance (seed)

- Invariants — hard rules the data must never violate.
- Deliberate simplifications — where it knowingly departs from reality for clarity.

## Building it

Map to the "Adding a collection" checklist in collections/CLAUDE.md; note any new
`core/distributions.py` helper or `ctx.entities` need.
```

Keep it honest and buildable: name real core APIs, give concrete dtypes and FKs, and mark
every magnitude as a target. The proposal should be detailed enough that someone can follow
collections/CLAUDE.md's "Adding a collection" steps against it without re-deciding the design.

## 5. Report

Summarize the collection you proposed: the domain and why it's distinct from the existing
four, its tables and build order, the headline distributions/scenarios, any new core helper
it would need, and the doc path. If you only *proposed a menu* (empty/vague `$ARGUMENTS`)
and wrote nothing, list the candidate domains and ask which to write up. Then note that the
next step is to implement it per collections/CLAUDE.md — writing the `tables/` generators,
`scenarios/*.md`, `realism-guidance.md`, registration, and tests — and firm up the target
magnitudes once the data is generated.
