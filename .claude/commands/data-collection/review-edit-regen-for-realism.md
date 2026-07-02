---
description: Review a collection's generated data against its realism-guidance.md rubric — measure invariants and distributions, sweep for "too-synthetic" artifacts the rubric doesn't yet name (constant sub-population averages, flat/uniform distributions, round-number lattices, absent noise), fix the tables/ generators where the data is wrong or drifted, regenerate to confirm, and keep the rubric + invariant tests honest. Collection-level realism, independent of any scenario signal.
model: opus
---

Take a data **collection** and make its generated data *realistic*: check freshly generated
data against `realism-guidance.md` — the review rubric — fix the `tables/` generators where
an invariant is violated or a distribution has drifted, regenerate to confirm, keep the
rubric honest, and pin the invariants with tests.

This is the **realism** counterpart to
[`/scenario:review-and-edit-regenerate`](../scenario/review-and-edit-regenerate.md), and it
is **independent of scenarios**. A scenario realizes one deliberately-planted *teachable
signal* (usually about a subset). This command instead audits the whole collection against
the plausibility rules that must hold *regardless* of any teaching point — referential
integrity, temporal ordering, arithmetic identities, top-line mixes, non-negativity. Where
the two overlap (`realism-guidance.md`'s **Deliberate simplifications** section is the
shortlist of candidates to promote into scenarios), stay on the realism side of the line:
do **not** invent or plant a new subset signal here — that's the scenario command's job.

Read the "Realism guidance: the review rubric" section of
[collections/CLAUDE.md](../../../src/potato_tornado/collections/CLAUDE.md) first. Follow
[.claude/rules/python-style.md](../../rules/python-style.md) and
[.claude/rules/pytest.md](../../rules/pytest.md) throughout.

## 1. Resolve the target

`$ARGUMENTS` names a **collection** (e.g. `hotel`, `clinic`), or is empty.

- **A collection** — audit that one.
- **Empty** — prefer the collection named most recently in the conversation; if none, list
  the collections (`labor`, `hotel`, `clinic`, `streaming`, …) and ask which to review
  before touching anything.

Audit **one** collection per run. If the collection has no `realism-guidance.md` yet, write
one first per the template in collections/CLAUDE.md (invariants / distributions & mixes /
deliberate simplifications) — you can't review against a rubric that doesn't exist.

## 2. Ground-truth the current data

Don't trust the rubric's numbers — measure the generator as it stands.

- Read `collections/<name>/realism-guidance.md` end to end: its **Invariants**,
  **Distributions & mixes** (with target magnitudes), **Deliberate simplifications**, and
  the "How to review" queries.
- Read the `tables/` modules and `constants.py` so you know how each reviewed column is
  drawn.
- Generate the collection and run the rubric against it. Use a fixed seed and small scale:

  ```bash
  uv run python -c "from potato_tornado.runner import generate; from potato_tornado.core.config import GenerationConfig; f = generate('<name>', GenerationConfig(seed=7, scale=0.3)); print(...)"
  ```

  For each **Invariant**, compute the check the "How to review" query describes (expect 0
  violations / the stated identity to hold). For each **Distributions & mixes** line,
  compute the actual mix / rate / skew and compare to the stated magnitude. Note every
  invariant that is violated (a bug) and every distribution that has drifted from its
  documented target.

### 2b. Sweep for "too-synthetic" artifacts (beyond the written rubric)

The rubric only catches what someone already thought to write down. A dataset can satisfy
every documented line and still *read* as fake — the tell-tale fingerprints of a generator
that drew columns independently, uniformly, or without noise. So after the rubric pass, run
an **open-ended plausibility sweep** for artifacts the rubric doesn't yet name. Probe for:

- **Constant / degenerate sub-population stats.** Group a numeric column by every natural
  segment (property, city, channel, room class, month, cohort) and compare the mean **and**
  spread across groups. If a metric that should differ by segment is flat across all of them
  — every property with the same average stay length, every channel the same party size —
  that's a driver drawn independently of the segment. (`df.group_by(seg).agg(mean, std)` and
  eyeball the range; near-zero variation between groups is the smell.)
- **Flat / uniform where reality is skewed.** A categorical drawn ~uniformly (all levels
  ≈equal share) or a numeric that's ~uniform where the real world is peaked or heavy-tailed.
  Check level shares and a rough histogram / quantiles.
- **Absent noise & lattice artifacts.** Too few distinct values, everything a round multiple
  (5/10/100, prices with no cents, all timestamps at midnight), or a hard spike piled at a
  clamp boundary. Count `n_unique`, inspect the modal values and the min/max pile-up.
- **Missing or mechanical correlations.** Variables that should co-move but were drawn
  independently (price↔demand, tenure↔pay, stay-length↔spend), *or* the opposite — a perfect
  ±1.0 correlation from a deterministic formula where reality has scatter. Check pairwise
  `corr` on plausibly-linked columns.
- **Too-clean structure.** Every group the same size, no missing/NULL where reality leaves
  gaps, no rare events, no calendar structure (weekday/weekend, seasonality) where it'd exist.

These are **candidate** smells, not automatic bugs — some are legitimate **Deliberate
simplifications** (check that section before flagging). For each one that isn't already
documented as intentional, note it for step 3 with the segment/column and the measured
numbers.

## 3. Fix realism issues in the generators

Rank what you found: **invariant violations first** (they're bugs), then **distribution
drift** against the rubric, then **synthetic-smell findings** from the 2b sweep. Leave
anything under **Deliberate simplifications** alone — that departure is intentional. For each
real issue, make the **smallest** edit to the `tables/` module(s) that restores it.
Non-negotiables (same as the rest of the repo):

- **Determinism.** Draw only from `ctx.dist` / `ctx.rng` / `ctx.entities` (and `ctx.faker`
  for incidental text). Never wall-clock, `random`, or the numpy global RNG. Streams are
  name-keyed off the table name, so prefer `ctx.rng.child("<something>")` for a new draw
  rather than reordering existing draws (which would shift every downstream value).
- **Scale-free.** Author against `scale=1.0`; size counts through `ctx.n(base)`.
- **Referential integrity.** FKs must point at rows that exist; if a fix keys off another
  table, declare `depends_on` and read it via `ctx.table(...)`.
- **Minimal + in-style.** No speculative parameters or new abstractions — match the
  surrounding builder. A clamp, a corrected identity, a retuned weight, or a modest per-segment
  jitter / noise term is usually enough.
- **Fix the smell, don't plant a signal.** Fixing a synthetic-smell finding means restoring
  *plausible heterogeneity or noise* — breaking a flat sub-population average into believable
  scatter, adding cents, giving a segment its own modest offset. Keep the effect small and
  unsurprising. If making a constant vary would create a *large, surprising, discoverable*
  subset gap (the kind a student is meant to find), that's scenario work — stop, and note it
  in step 5 as a candidate rather than building it here.

Re-run the step-2 measurements with the same one-liner to confirm every invariant now holds
with 0 violations and each distribution sits at its target (this is the "regenerate" check —
it must pass before you touch tests). Confirm you didn't disturb a *different* rubric line
while fixing one.

## 4. Pin the invariants with tests

Realism invariants belong in the collection's structural test file, alongside the existing
referential-integrity checks: `tests/collections/<name>/test_<name>.py` (create it if
absent — mirror the `src` path). Add or extend a test per invariant you verified or fixed,
one behavior per test.

- **Single assert**, seeded config, small scale (copy the module-scoped `generate(...)`
  fixture from the existing `test_<name>.py`). Assert the invariant directly (0 violations,
  the arithmetic identity holds, the mix sits within a tolerance wide enough to survive the
  seed but tight enough to catch regressions — base the bound on step 2, not a guess).
- Fully typed (`def test_...() -> None:`), pytest-native (`assert`, `pytest.raises`,
  fixtures, `tmp_path`/`monkeypatch`) — never `unittest`. Use `@pytest.mark.parametrize` for
  the same invariant across seeds/inputs.
- Assert *invariants and top-line mixes* here; leave subset-signal magnitudes to
  `test_scenarios.py`.

## 5. Keep the rubric honest

`realism-guidance.md` is the answer key — it must match the generator you just measured:

- Update any **Distributions & mixes** magnitude you moved (or that drifted) to the measured
  value.
- **Record what the 2b sweep resolved.** If you fixed a synthetic-smell finding, add the new
  plausibility rule it established — a **Distributions & mixes** line for the per-segment
  spread / noise you introduced, or an **Invariant** if it's now a hard rule — with the
  measured magnitude, so the artifact can't silently creep back. If instead you judged a smell
  to be an acceptable teaching simplification, document that decision as a **Deliberate
  simplifications** bullet so the next reviewer doesn't re-flag it.
- If a fix removed a departure that a **Deliberate simplifications** bullet described, delete
  that bullet; if you *added* an intentional simplification, document it there.
- Keep the "How to review" queries runnable against the current schema.
- If you spotted a surprising subset signal in step 3, list it as a **candidate scenario**
  in your report (for `/scenario:draft-or-propose`) — don't add it to the rubric.

## 6. Gate and report

Run the full gate and fix anything it flags:

```bash
uv run ruff format && uv run ruff check && uv run pyright && uv run pytest
```

Then summarize: the collection you audited, each invariant violation and distribution drift
you found (with before/after numbers), each **synthetic-smell finding from the 2b sweep**
(the segment/column, the measured artifact, and whether you fixed it or judged it an
intentional simplification), which `tables/` modules you edited (or that the data was already
realistic), the tests you added/extended (`file:line`), the `realism-guidance.md` lines you
reconciled, and any candidate scenarios you noticed but deliberately left for the scenario
command. If a fix vs. deliberate-simplification call was genuinely ambiguous, surface it as a
question rather than guessing.
