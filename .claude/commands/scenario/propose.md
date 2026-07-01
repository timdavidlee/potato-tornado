---
description: Propose one new scenario for a given data collection and write its scenario doc — docs only, no generator or test edits
model: opus
---

Propose **one new scenario** for a data collection and capture it as a doc. This is the
*docs-first* step: find a fresh signal worth teaching, sanity-check that the collection's
data can carry it, and write the markdown answer key. It does **not** touch the `tables/`
generators or write tests — that's
[`/scenario:review-and-edit-regenerate`](review-and-edit-regenerate.md), the natural next
step once the doc here is agreed on.

Use this when you know which collection you want another scenario for and just want the
next good doc written. To shape a rough signal idea you already have into a scenario, use
[`/scenario:draft-or-propose`](draft-or-propose.md) instead.

Read the "Scenarios: the intended signals" section of
[collections/CLAUDE.md](../../../src/potato_tornado/collections/CLAUDE.md) first — it
defines what a scenario is and the doc template. Follow
[.claude/rules/python-style.md](../../rules/python-style.md) where relevant.

## 1. Read `$ARGUMENTS`

`$ARGUMENTS` is a collection name (e.g. `clinic`, `hotel`, `labor`, `streaming`). If it's
empty or the collection is ambiguous, ask which collection before going further — don't
guess.

## 2. Ground the proposal in the actual data

A scenario is only worth writing if the generated data can plausibly carry it. Before
drafting:

- Read the collection's `tables/` modules and `constants.py` to see what columns exist and
  how they're currently drawn.
- Read **every** existing `collections/<name>/scenarios/*.md` so you don't re-propose a
  signal that's already documented, and so the new one sits alongside them coherently and
  covers different tables/columns where possible.
- **Read `collections/<name>/realism-guidance.md`** — the review rubric. Its **Deliberate
  simplifications** section is your best shortlist: each one (e.g. "hotel rates have no
  weekday/weekend variation") is a realism gap that's a prime candidate to promote into a
  new scenario. Any signal you propose must respect that doc's **Invariants** — never
  propose something that would require breaking one.
- Skim the generated frame if you're unsure a column or relationship exists:

  ```bash
  uv run python -c "from potato_tornado.runner import generate; from potato_tornado.core.config import GenerationConfig; f = generate('<name>', GenerationConfig(seed=7, scale=0.3)); [print(k, v.columns) for k, v in f.items()]"
  ```

Decide honestly whether today's generator **already** produces the signal or it would need
a tune, and say which — the review-and-edit step needs that starting point. Don't fabricate
a magnitude; if the data doesn't clearly support the signal yet, give a target magnitude to
aim for and flag it as "to be planted".

## 3. Pick the strongest candidate

Sketch two or three candidate signals in your head, then commit to the single strongest one
to write up. A good scenario is: checkable with a concrete query, distinct from the existing
docs, grounded in real tables/columns, and teachable (a clear analytical payoff). Prefer one
that promotes a listed *deliberate simplification* or exercises tables no current scenario
touches. If two are equally strong and genuinely different, it's fine to write both — but
default to one clean doc.

**Propose a new table if necessary.** Most scenarios should live in the columns that already
exist, but if the strongest signal genuinely needs data the collection doesn't yet model
(e.g. a new dimension or event stream), it's fine to propose a **new table** as part of the
scenario. Say so explicitly in the doc — name the table, its key columns, and how it relates
to existing tables (FKs) — and flag it as "new table, to be added" so the review-and-edit
step knows to author the `build_<table>` module, not just tune an existing one. Don't reach
for a new table when an existing column can carry the signal.

## 4. Write the doc

Write `collections/<name>/scenarios/<slug>.md` where `<slug>` is a kebab-case slug of the
signal (`weekend-rate-premium.md`). Use the exact template from collections/CLAUDE.md:

```markdown
# <one-line signal title>

- **Signal:** one sentence stating what is true in the data.
- **Tables:** `table.column`, ... (what to look at)
- **Magnitude:** the rough number to expect (rate / ratio / skew / bound).

<short prose: what to do to surface it, and why it's planted — the teaching point.>

## How to find it

<a SQL / query sketch that reveals the signal, with the expected value in a comment>
```

Keep it honest and specific: name real tables/columns, give a concrete "How to find it"
query, and mark any magnitude that still has to be planted as a target (the next step
measures and firms it up).

## 5. Update the realism markdown where relevant

The new doc may make part of `collections/<name>/realism-guidance.md` stale — reconcile it:

- If the scenario **promotes a listed deliberate simplification** (you're now teaching the
  thing the collection used to hand-wave), remove or reword that bullet so the rubric no
  longer claims the gap exists.
- If the scenario **introduces a new invariant or a new table**, note it under the relevant
  section so the review rubric stays a faithful description of the data.
- If nothing there is affected, leave it untouched — don't add churn for its own sake.

Keep this doc-only: adjust the prose, don't touch generators or magnitudes (the
review-and-edit step firms up numbers once the signal is actually planted).

## 6. Report

Summarize the scenario you wrote: the signal, its target tables (noting any **new table**
proposed), whether you believe the generator already produces it or it needs planting, the
doc path, and any edit you made to `realism-guidance.md`. Then point the user at
`/scenario:review-and-edit-regenerate <name>/<slug>` to make it real (tune generators, add
any new table, verify, add the scenario test).
