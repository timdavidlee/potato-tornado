---
description: Realize a scenario doc — measure the signal, tune the tables/ generators to plant it, regenerate to confirm, and write the scenario test that asserts it. With no scenario named, round-robins the next unrealized scenario (or a collection to scope the rotation).
model: opus
---

Take a data-collection **scenario** and make it real: confirm the intended signal is
actually planted in the generated data, tune the `tables/` generators if it isn't,
regenerate to verify, keep the scenario doc's magnitude honest, and write a **scenario
test** that asserts the signal on freshly generated data.

This is the *realize* step. The scenario doc usually already exists — authored by
[`/scenario:draft-or-propose`](draft-or-propose.md) or by hand. If no doc exists yet,
prefer running that first; you may still draft a minimal one here if the signal is clear.

Read the "Scenarios: the intended signals" section of
[collections/CLAUDE.md](../../../src/potato_tornado/collections/CLAUDE.md) first. Follow
[.claude/rules/python-style.md](../../rules/python-style.md) and
[.claude/rules/pytest.md](../../rules/pytest.md) throughout.

## 1. Resolve the target

`$ARGUMENTS` may name a specific scenario, name only a collection, or be empty. Resolve it
to a single target scenario:

- **A specific scenario** — a slug or path like `labor/no-show-rate` or `overtime-right-skew`.
  Identify the **collection** and the **signal** and locate its doc at
  `collections/<name>/scenarios/<slug>.md`.
- **A collection only** (e.g. `clinic`) — **round-robin within that collection**: pick the
  next scenario that still needs work (see *Round-robin selection* below).
- **Empty** — **round-robin across all collections**. If exactly one collection has
  unrealized scenarios, use it; if several do, prefer the collection named most recently in
  the conversation, and otherwise ask which one before selecting.

If the collection is ambiguous or the target tables aren't clear, ask before writing
anything — don't guess which tables to touch.

**Round-robin selection.** Enumerate the in-scope `scenarios/*.md` docs in a stable order
(alphabetical by `<collection>/<slug>`) and pick the **first that is not yet realized** — a
scenario counts as *not realized* if its doc still flags a **Magnitude** as "to be planted"
**or** no test under `tests/collections/<name>/` asserts its signal. Realize exactly **one**
scenario per run (the classic round-robin turn), not the whole backlog — unless the user
explicitly asks for all of them. If **every** in-scope scenario is already realized, don't
invent a new signal: say so, then re-verify the first scenario in the stable order (or one
the user names) as a no-op pass — measure it, confirm the doc magnitude and test still hold,
and report. Either way, name the scenario you picked and list the ones still unrealized in
step 6 so the next no-argument run advances to the following one.

## 2. Ground-truth the current data

Do not trust the doc's magnitude — measure the generator as it stands.

- Read the doc; note its stated **Signal / Tables / Magnitude** and "How to find it" query.
- Read the `tables/` modules the signal touches, plus `constants.py`, so you know how the
  relevant columns are currently drawn.
- **Read `collections/<name>/realism-guidance.md`** — the review rubric. Its **Invariants**
  are hard constraints your edits must not break; its **Distributions & mixes** tell you
  which other numbers your change might disturb; and if the signal you're planting fills a
  gap listed under **Deliberate simplifications**, that entry will need removing in step 5.
- Generate the collection and measure the signal directly, so you know the real starting
  point. Use a fixed seed and a small scale:

  ```bash
  uv run python -c "from potato_tornado.runner import generate; from potato_tornado.core.config import GenerationConfig; f = generate('<name>', GenerationConfig(seed=7, scale=0.3)); print(...)"
  ```

  Compute the actual rate / ratio / skew the scenario claims. This number decides whether
  step 3 is a tune or a no-op, and it anchors the test's tolerance in step 4.

## 3. Plant or tune the signal in the generators

If the measured signal already matches the doc, change no generation code. Otherwise make
the **smallest** edit to the `tables/` module(s) that produces it. Non-negotiables:

- **Determinism.** Draw only from `ctx.dist` / `ctx.rng` / `ctx.entities` (and `ctx.faker`
  for incidental text). Never wall-clock, `random`, or the numpy global RNG. Streams are
  name-keyed off the table name, so prefer `ctx.rng.child("<something>")` for a new draw
  rather than reordering existing draws (which would shift every downstream value).
- **Scale-free.** Author against `scale=1.0`; size any counts through `ctx.n(base)`.
- **Referential integrity.** FKs must still point at rows that exist; if you add a pattern
  keyed to another table, declare `depends_on` and read it via `ctx.table(...)`.
- **Minimal + in-style.** No speculative parameters or new abstractions — match the
  surrounding builder. A tuned weight or an added branch is usually enough.

Re-measure with the same one-liner to confirm the signal now holds at the intended
magnitude (this is the "regenerate" check — it must pass before you write the test). Then
**re-check the regenerated data against `realism-guidance.md`**: run its "How to review"
queries to confirm you didn't break an invariant or unintentionally shift a documented mix
while planting the signal.

## 4. Write the scenario test

Add a behavioral test that goes through `generate()` and asserts the signal. Mirror the
`src` path: put per-collection scenario tests in
`tests/collections/<name>/test_scenarios.py` (create it if absent), one test function per
signal, named for the behavior (`test_weekend_rates_run_above_weekday`), not the function
under test.

- **Single assert**, seeded config, small scale (see the labor/hotel collection tests for
  the fixture shape). Assert the signal *and* its magnitude with a tolerance wide enough to
  survive the seed but tight enough to catch regressions — base the bound on what you
  measured in step 2, not a guess.
- Fully typed (`def test_...() -> None:`), pytest-native (`assert`, `pytest.raises`,
  fixtures, `tmp_path`/`monkeypatch`) — never `unittest`. Use `@pytest.mark.parametrize`
  if you're checking the same signal across seeds/inputs.

## 5. Keep the docs honest

Two docs must match the generator you just measured — the structural check in
[tests/collections/test_scenarios.py](../../../tests/collections/test_scenarios.py) requires
both to exist per collection:

- **`scenarios/<slug>.md`** — update its **Magnitude** to the measured value; this is the
  answer key. (If no doc existed, write one now per the template in collections/CLAUDE.md.)
- **`realism-guidance.md`** — if your edit changed the realism envelope, reconcile it in the
  same change: update any **Distributions & mixes** number you shifted, and if you planted a
  signal that a **Deliberate simplifications** bullet said the data *didn't* have, remove
  that bullet (the simplification is no longer true).

## 6. Gate and report

Run the full gate and fix anything it flags:

```bash
uv run ruff format && uv run ruff check && uv run pyright && uv run pytest
```

Then summarize: the scenario you targeted (and, if you round-robined, that you picked it and
which scenarios remain unrealized), the signal and its final magnitude, which `tables/`
modules you edited (or that none needed editing), the test you added (`file:line`), and the
docs you wrote/updated (the scenario doc and any `realism-guidance.md` reconciliation).
If a design choice was genuinely ambiguous, surface it as a question rather than guessing.
