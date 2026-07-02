---
description: Propose teachable scenarios for a collection (or shape a rough idea into one) and write the scenario doc — docs only, no generator or test edits
model: opus
---

Design a data-collection **scenario** and capture it as a doc. This is the *docs-first*
step: identify a signal worth teaching, sanity-check that the collection's data can carry
it, and write the markdown answer key. It does **not** touch the `tables/` generators or
write tests — that's [`/scenario:review-and-edit-regenerate`](review-and-edit-regenerate.md),
which is the natural next step once a doc here is agreed on.

Read the "Scenarios: the intended signals" section of
[collections/CLAUDE.md](../../../src/potato_tornado/collections/CLAUDE.md) first — it
defines what a scenario is and the doc template. Follow
[.claude/rules/python-style.md](../../rules/python-style.md) where relevant.

## 1. Read `$ARGUMENTS`

Two modes:

- **Propose** — `$ARGUMENTS` is just a collection name (or empty). Survey that collection
  (or, if empty, ask which one) and propose a short menu of candidate scenarios the data
  could support but doesn't yet document. Recommend the strongest one or two.
- **Shape** — `$ARGUMENTS` describes a rough signal idea ("hotel: weekends cost more").
  Turn it into a concrete, checkable scenario for the right collection.

If the collection is ambiguous, ask before surveying.

## 2. Ground the proposal in the actual data

A scenario is only worth writing if the generated data can plausibly carry it. Before
drafting:

- Read the collection's `tables/` modules and `constants.py` to see what columns exist and
  how they're currently drawn.
- Check the existing `collections/<name>/scenarios/*.md` so you don't re-propose a signal
  that's already documented, and so new ones sit alongside them coherently.
- **Read `collections/<name>/realism-guidance.md`** — the review rubric. Its **Deliberate
  simplifications** section is your best shortlist: each one (e.g. "hotel rates have no
  weekday/weekend variation") is a realism gap that's a prime candidate to promote into a
  new scenario. And any signal you propose must respect that doc's **Invariants** — never
  propose something that would require breaking one.
- Skim the generated frame if you're unsure a column or relationship exists:

  ```bash
  uv run python -c "from potato_tornado.runner import generate; from potato_tornado.core.config import GenerationConfig; f = generate('<name>', GenerationConfig(seed=7, scale=0.3)); [print(k, v.columns) for k, v in f.items()]"
  ```

For each candidate, decide honestly: does today's generator likely **already** produce this
signal, or would it need a tune? Say which — the review-and-edit step needs that starting
point. Don't fabricate a magnitude; if the data doesn't clearly support the signal yet,
give a target magnitude to aim for and flag it as "to be planted".

**A scenario is an unexpected insight, usually about a subset of the data** (a room class, a
shift window, a region) — not a flat fact true of the dataset as a whole. Drop any candidate
that's really a broad top-line trend, invariant, or overall mix with no surprising segment
behind it; that belongs in `collections/<name>/realism-guidance.md`'s Invariants or
Distributions & mixes section, not a scenario doc. If it's genuinely missing there, add it
directly rather than writing it up as a scenario.

## 3. Write the doc(s)

For each agreed scenario, write `collections/<name>/scenarios/<slug>.md` where `<slug>` is
a kebab-case slug of the signal (`weekend-rate-premium.md`). Use the exact template from
collections/CLAUDE.md:

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

## 4. Report

Summarize the scenario(s) you proposed or drafted: each signal, its target tables, whether
you believe the generator already produces it or it needs planting, and the doc path(s) you
wrote. Then point the user at `/scenario:review-and-edit-regenerate <name>/<slug>` to make
it real (tune generators, verify, add the scenario test). If you only *proposed* a menu and
wrote nothing, list the options and ask which to draft.
