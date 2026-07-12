---
description: Propose one document-based scenario for a data collection — a signal hidden in free-form text (markdown records, a policy/rules doc, a lab/financial report) that must be parsed before it can be computed — and write its scenario doc. Docs only, no generator or test edits.
model: opus
---

Propose **one document-based scenario** for a data collection and capture it as a doc.
A document-based scenario is one where the analytical work is *parsing unstructured
free-form text* — an agent or student is handed prose (markdown transaction records, a
policy document of rules, a lab or financial report with numbers buried in sentences)
and must extract structured facts from it *before* any signal can be computed. This is
the *docs-first* step: find a signal worth teaching that genuinely needs parsing,
sanity-check that the collection can carry it, and write the markdown answer key. It
does **not** touch the `tables/` generators or write tests — that's
[`/scenario:realize-document`](realize-document.md), the natural next step once the doc
here is agreed on.

Use this when you want the analytical challenge to be *reading documents*, not querying
clean columns. For an ordinary SQL-checkable signal, use
[`/scenario:propose`](propose.md) instead.

Read the "Scenarios: the intended signals" section of
[collections/CLAUDE.md](../../../src/potato_tornado/collections/CLAUDE.md) first, and in
particular its **"Document-based scenarios (parse-the-prose signals)"** subsection — it
defines the convention (text column is the source of truth; render facts that already
live in structured columns; files are an optional derived export). Follow
[.claude/rules/python-style.md](../../rules/python-style.md) where relevant.

## 1. Read `$ARGUMENTS`

`$ARGUMENTS` is a collection name (e.g. `clinic`, `insurance`, `retail`, `labor`),
optionally followed by a rough document idea ("insurance: severity hidden in adjuster
notes"). If it's empty or the collection is ambiguous, ask which collection before going
further — don't guess.

## 2. Ground the proposal in the actual data

A document-based scenario is only worth writing if the collection's data can plausibly
carry both the *prose* and the *signal inside it*. Before drafting:

- Read the collection's `tables/` modules and `constants.py` to see what columns and
  entities exist — these are the raw material a document would *render into prose*.
- Read **every** existing `collections/<name>/scenarios/*.md` so you don't re-propose a
  signal that's already documented (in prose or in SQL form), and so the new one sits
  alongside them coherently.
- **Read `collections/<name>/realism-guidance.md`** — the review rubric. Any signal you
  propose must respect its **Invariants**; a **Deliberate simplification** is a prime
  candidate to promote into a document scenario (e.g. "notes are not modelled" → a notes
  table whose text carries a signal).
- Skim the generated frame if you're unsure a column or relationship exists:

  ```bash
  uv run python -c "from potato_tornado.runner import generate; from potato_tornado.core.config import GenerationConfig; f = generate('<name>', GenerationConfig(seed=7, scale=0.3)); [print(k, v.columns) for k, v in f.items()]"
  ```

## 3. Pick the signal and decide the four document choices

**A scenario is an unexpected insight, usually about a subset of the data** (a payer, a
category, a shift window) — not a flat fact about the whole dataset. That bar still
applies. What makes this *document-based* is that the insight is **only reachable by
parsing prose**: if a plain `SELECT` over an existing column would answer it, it's an
ordinary scenario — route it to [`/scenario:propose`](propose.md), not here.

Sketch two or three candidate signals, commit to the strongest, then pin down the four
choices the realize step needs (record each in the doc):

1. **Document type** — which flavour of prose carries it: an *unstructured transaction
   record* (a markdown receipt / ledger blob to parse for line items), a *policy or rules
   document* (prose rules that must be applied to other rows), a *lab / financial report*
   (numbers embedded in narrative), or a *free-form note* (an adjuster / clinical / support
   note whose wording hides the signal).
2. **Where the text lives** — a new `documents` / `notes` table, or a free-form text
   column added to an existing table. Prefer a new table when the documents are their own
   entity with a clear FK; add a column when each existing row naturally has one note.
3. **Ground-truth placement** *(the important one)* — **strongly prefer** a signal whose
   answer already exists in a structured column somewhere, so the `body` merely *renders*
   those facts and the test can reconcile parsed text against the real column with no
   answer leaked into the prose. Only if the fact exists nowhere else do you ship an
   answer-key column beside `body`; if so, say in the doc that it is **withheld** when
   handing documents to students.
4. **Delivery** — in-DB text column only (the default), or *also* materialized to files
   on disk. Only ask for files when the scenario genuinely wants a folder of documents
   (one policy doc, a handful of reports); note that files are a derived export of the
   same deterministic text column, never a second source of truth.

Decide honestly whether today's data already contains the facts the prose would render
(then realizing is mostly *writing the generator that renders them*) or whether a new
column/quantity must be planted first — and say which. Don't fabricate a magnitude; if
the signal isn't supported yet, give a target to aim for and flag it "to be planted".

## 4. Write the doc

Write `collections/<name>/scenarios/<slug>.md` where `<slug>` is a kebab-case slug of the
signal (`severity-understated-in-adjuster-notes.md`). Use the standard scenario template
**extended with the three document fields**:

```markdown
# <one-line signal title>

- **Signal:** one sentence stating what is true in the data (the insight, not "there are documents").
- **Documents:** `table.column` holding the free-form text · doc type (record / policy / report / note) · rough count (`ctx.n(...)`).
- **Parse target:** what must be extracted from the prose to surface the signal, with a short example snippet of the text and the field(s) pulled from it.
- **Ground truth:** where the answer lives — reconciled against `other_table.column` (preferred, no leak), or a `body`-adjacent answer-key column **withheld from students**.
- **Tables:** `table.column`, ... (structured columns the parsed values reconcile against)
- **Magnitude:** the rough number to expect (rate / ratio / skew / bound), or a target flagged "to be planted".

<short prose: what an analyst does — extract fields from the prose, then aggregate — and why it's planted (the teaching point: the signal is legible only after parsing).>

## How to find it

<a two-step recipe: (1) the extraction (a regex / rule sketch over the text column, or the
parse an LLM would do), then (2) the SQL / dataframe aggregation over the extracted values,
with the expected value in a comment.>
```

Keep it honest and specific: name real tables/columns, show a realistic snippet of the
prose, give the extraction *and* the aggregation, and mark any magnitude still to be
planted as a target (the realize step measures and firms it up).

## 5. Update the realism markdown where relevant

The new doc may make part of `collections/<name>/realism-guidance.md` stale — reconcile it
in prose only (don't touch generators or magnitudes):

- If the scenario **promotes a listed deliberate simplification** (e.g. "notes are not
  modelled" — you're now modelling them), remove or reword that bullet.
- If it **introduces a new table or a new invariant** (e.g. "every `documents` row FKs a
  real claim", "the amount in the prose equals the structured `amount`"), note it under
  the relevant section so the rubric stays a faithful description of the data.
- If nothing there is affected, leave it untouched — don't add churn for its own sake.

## 6. Report

Summarize the scenario you wrote: the signal, the document type and where the text lives,
the ground-truth placement (reconciled column vs. withheld answer-key column), the delivery
(in-DB only vs. also files), whether the facts already exist or must be planted, the doc
path, and any `realism-guidance.md` edit. Then point the user at
`/scenario:realize-document <name>/<slug>` to make it real (write the document generator,
verify, add the parse-and-assert test).
