---
description: Realize a document-based scenario doc — plant the text-emitting generator (a build_<docs> table whose free-form prose renders the signal), regenerate to confirm the signal is recoverable by parsing, and write the two-layer parse-and-assert test. With no scenario named, round-robins the next unrealized document scenario.
model: opus
---

Take a **document-based scenario** and make it real: write (or tune) the `tables/`
generator that emits the free-form text, confirm the planted signal is genuinely
*recoverable by parsing the prose*, keep the scenario doc's magnitude honest, and write a
**two-layer scenario test** that (a) extracts the signal from the text and (b) asserts it.

This is the *realize* step for the document subtype — the parallel of
[`/scenario:review-and-edit-regenerate`](review-and-edit-regenerate.md), specialized for
prose signals. The scenario doc usually already exists — authored by
[`/scenario:propose-document`](propose-document.md). If no doc exists, prefer running that
first; you may draft a minimal one here if the signal is clear.

Read the "Scenarios: the intended signals" section of
[collections/CLAUDE.md](../../../src/potato_tornado/collections/CLAUDE.md), and especially
its **"Document-based scenarios (parse-the-prose signals)"** subsection — it is the
convention this command realizes. Follow
[.claude/rules/python-style.md](../../rules/python-style.md) and
[.claude/rules/pytest.md](../../rules/pytest.md) throughout.

## 1. Resolve the target

`$ARGUMENTS` may name a specific document scenario, name only a collection, or be empty.

- **A specific scenario** — a slug or path like `insurance/severity-understated-in-adjuster-notes`.
  Locate its doc at `collections/<name>/scenarios/<slug>.md` and confirm it is a *document*
  scenario (it has the **Documents** / **Parse target** / **Ground truth** fields). If it's
  an ordinary SQL scenario, hand off to
  [`/scenario:review-and-edit-regenerate`](review-and-edit-regenerate.md) instead.
- **A collection only** (e.g. `insurance`) — round-robin **within its document scenarios**:
  enumerate the `scenarios/*.md` that carry the **Documents** field in a stable order
  (alphabetical by slug) and pick the first not yet realized (magnitude still "to be
  planted", **or** no parse-and-assert test under `tests/collections/<name>/` covers it).
- **Empty** — round-robin document scenarios across all collections; if several qualify,
  prefer the collection named most recently in the conversation, else ask.

Realize exactly **one** scenario per run unless the user asks for the whole backlog. If
every in-scope document scenario is already realized, say so and re-verify the first in
stable order as a no-op pass. Name the scenario you picked and list any still unrealized in
step 6. If the target tables aren't clear from the doc, ask before writing — don't guess.

## 2. Ground-truth the current data

Do not trust the doc's magnitude — measure what exists.

- Read the doc; note its **Signal / Documents / Parse target / Ground truth / Tables /
  Magnitude** and its "How to find it" recipe.
- Read the `tables/` modules and `constants.py` for the tables the signal touches, so you
  know what structured facts already exist to *render into prose* and how they're drawn.
- **Read `collections/<name>/realism-guidance.md`** — its **Invariants** are hard
  constraints your edits must not break; a **Deliberate simplification** the scenario fills
  (e.g. "notes are not modelled") gets removed in step 5.
- Generate the collection and check the starting point: does the fact the prose must render
  already live in a column (then this is mostly *writing the renderer*), or must the
  underlying quantity be planted first? Measure it with a fixed seed and small scale:

  ```bash
  uv run python -c "from potato_tornado.runner import generate; from potato_tornado.core.config import GenerationConfig; f = generate('<name>', GenerationConfig(seed=7, scale=0.3)); print(...)"
  ```

## 3. Plant the document generator

Emit the free-form text as an ordinary table column — **the text column is the source of
truth**. Make the smallest change that renders the signal into prose. Non-negotiables:

- **Text lives in a `body` (or named) column of a DataFrame.** A new `documents` / `notes`
  table means a new `build_<docs>(ctx) -> pl.DataFrame` under `tables/`: re-export it from
  `tables/__init__.py` and add a `TableSpec(name=..., build=..., depends_on=(...))` in the
  collection's `__init__.py` (no `_BUILTIN_MODULES` change — that's per collection, not per
  table). If instead the doc puts the text on an existing table, add the column in that
  builder.
- **Render facts; don't invent an oracle.** Read the structured source via
  `ctx.table("<src>")` (declare `depends_on`), and format its real values into the prose so
  the signal reconciles against the source column with no answer leaked. Ship an
  answer-key column beside `body` **only** if the fact exists nowhere else (the doc must say
  it's withheld from students).
- **Derive numbers, never re-sample.** Format the ground-truth value into the template
  string; never draw the same quantity a second time (that desyncs prose from answer key).
- **Vary the phrasing.** Pick among 2–3 template variants off a name-keyed
  `ctx.rng.child("template")` stream so the text isn't one fixed layout the parser could
  memorize byte-for-byte. Keep the *extractable fields* consistent across variants.
- **Determinism & scale.** Draw only from `ctx.dist` / `ctx.rng` / `ctx.entities` (and
  `ctx.faker` for incidental filler). Never wall-clock, `random`, or the numpy global RNG.
  Prefer `ctx.rng.child("<name>")` for new draws rather than reordering existing ones. Size
  the row count through `ctx.n(base)`; the scenario test runs at `scale=0.5`, so keep a
  floor of at least 1 document. Spread any document dates across `ctx.config.span_days`.

**If (and only if) the doc's delivery includes files on disk**, add the export *outside*
`generate()` — a small post-generate helper or CLI verb that writes the deterministic text
column to `docs/<doc_id>.md` (use `\n` newlines; never `depends_on` or read those files
back). Do not build a general document sink; materialize the one column the scenario needs.

Re-measure with the one-liner to confirm the rendered prose *parses back* to the ground
truth and the signal holds at the intended magnitude. Then **re-check the regenerated data
against `realism-guidance.md`** — confirm you didn't break an invariant or shift a
documented mix.

## 4. Write the two-layer scenario test

Add a behavioral test that goes through `generate()`. Mirror the `src` path:
`tests/collections/<name>/test_scenarios.py` (create if absent), one test per signal, named
for the behavior (`test_adjuster_notes_understate_severity`).

The test is **two layers** — keep each as its own single-assert test (or tight parametrize):

1. **Round-trip / recoverability** — run the *same deterministic extraction the student
   would* (a regex / rule parse over the text column) and assert the extracted values equal
   the ground truth (the reconciled source column, within cents/tolerance). This proves the
   signal is genuinely legible from the prose, and that the parser survives the template
   variants.
2. **Signal** — aggregate the parsed (or reconciled) values and assert the analytical claim
   *and* its magnitude, with a tolerance wide enough to survive the seed but tight enough to
   catch regressions — base the bound on what you measured in step 2, not a guess.

Fully typed (`def test_...() -> None:`), pytest-native (`assert`, `pytest.raises`, fixtures,
`tmp_path`/`monkeypatch`) — never `unittest`. Use a module-scoped fixture that generates the
collection once (see the existing `test_scenarios.py` files for the shape).

## 5. Keep the docs honest

- **`scenarios/<slug>.md`** — update its **Magnitude** to the measured value and make sure
  the **Parse target** snippet matches the prose you actually emit (a reader should be able
  to write the extractor from it). If no doc existed, write one now per the extended template
  in [`/scenario:propose-document`](propose-document.md).
- **`realism-guidance.md`** — if you added a `documents`/`notes` table or a new invariant
  (e.g. "the amount in each note equals the structured `amount`"), record it; if you filled a
  **Deliberate simplification** ("notes are not modelled"), remove that bullet.

## 6. Gate and report

Run the full gate and fix anything it flags:

```bash
uv run ruff format && uv run ruff check && uv run pyright && uv run pytest
```

Then summarize: the scenario you targeted (and, if you round-robined, which document
scenarios remain unrealized), the document type and where the text lives, the generator you
wrote/tuned (`file:line`), whether the signal reconciles against a real column or a withheld
answer-key column, the two-layer test you added (`file:line`), any file-export helper, and
the docs you updated. If a design choice was genuinely ambiguous, surface it as a question
rather than guessing.
