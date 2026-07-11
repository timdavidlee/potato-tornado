---
description: Scan the built-in data collections and, for each one that still has open work, write a timestamped working TODO checklist under docs/todos/ — extracted from that collection's TODO.md + realism-log status. Docs only, no generators, columns, or tests.
model: opus
---

Scan every built-in data collection, decide which ones still have **open work**, and for each
of those write a **timestamped working checklist** under
[`docs/todos/`](../../../docs/todos/). This command **surveys nothing new and proposes
nothing** — it distills the backlog that already lives in each collection's own status docs
into a dated, actionable checklist. It is **docs only**: it never touches a `build_<table>`,
`constants.py`, `register(...)`, `realism-guidance.md`, scenarios, or tests.

The output shape is fixed by the existing example,
[`docs/todos/2026-07-11-12:18-labor-round2-enrichment.md`](../../../docs/todos/2026-07-11-12:18-labor-round2-enrichment.md)
— read it first and match it. Each generated file is a thin, dated **progress tracker that links
into** a collection's authoritative [`TODO.md`] — **not** a copy of it. The checklist carries
**no item substance of its own** (no recipe / class / unlocks / file per item): that lives in
`TODO.md`, the single source of truth, and each checklist section links to the matching `TODO.md`
section. This keeps the substance in one place to edit. Don't invent backlog items; if a
collection's TODO.md is thin or missing, say so in the file rather than fabricating work.

## 1. `$ARGUMENTS`

- **Empty** — scan all collections.
- **One or more collection names** — scan only those (still one output file per named
  collection that has open work).

## 2. Enumerate the collections

The source of truth for *which* collections exist is `_BUILTIN_MODULES` in
[`core/registry.py`](../../../src/potato_tornado/core/registry.py) — enumerate from there (or
equivalently the package dirs under
[`collections/`](../../../src/potato_tornado/collections/)), not from any prior scan output, so
a newly added or removed collection is picked up.

## 3. Decide whether a collection has work left

For each collection, read its own status docs and judge whether anything is open. The
authoritative backlog is `collections/<name>/TODO.md`; corroborate with `realism-log.md`.
**Work is left** when any of these hold:

- `TODO.md` has unchecked items (`- [ ]`), or its **Status** section names items as *open*,
  *unstarted*, *surveyed-only / nothing built yet*, *deferred*, or *partially built*.
- `realism-log.md`'s **Status:** line is anything other than a clean *Converged* with no open
  items — e.g. *Needs investigation*, or *Converged* but naming open realism items / caveats.
- (Secondary signal) `scenarios/` describes intended signals the collection notes as
  **set up but deliberately not planted** — call these out but keep TODO.md the source of truth.

**No work left** = TODO.md backlog fully done **and** realism converged with no open items.
Skip those collections (don't write a file for them) and note them in the report.

Read the actual files — don't infer status from the previous scan or from `INVENTORY.md`.

## 4. Timestamp

Get the real wall-clock stamp from the shell (the injected `# currentDate` context has the date
but no time):

```bash
date "+%Y-%m-%d-%H:%M"    # for the filename, e.g. 2026-07-11-12:18
date "+%Y-%m-%d %H:%M"    # for the "Created:" line, e.g. 2026-07-11 12:18
```

Use one stamp for the whole run so a batch of files shares a timestamp. Create `docs/todos/` if
it's missing.

## 5. Write one checklist per collection with work left

Path: `docs/todos/<YYYY-MM-DD-HH:MM>-<collection>-<slug>.md`, where `<slug>` is a short
kebab-case summary of the open scope (e.g. `round2-enrichment`, `realism-investigation`,
`enrichment-backlog`). Match the example file's structure exactly:

- **Title** — `# <Collection> — dated working checklist (<created stamp>)`.
- **Metadata bullets** — **Scope** (this collection only), **Source of truth** (link to that
  collection's `TODO.md`, stating the checklist carries **no item substance of its own** — each
  item links into `TODO.md` for the recipe / class / definition of done — plus the "keep the two
  in step" note: tick here → tick in `TODO.md` → log the run in `realism-log.md`, and a pointer to
  [`collections/CLAUDE.md`](../../../src/potato_tornado/collections/CLAUDE.md) and the
  `/data-collection:*` / `/scenario:*` commands for the workflow), and **Status** (what's already
  done vs. what's open, in the collection's own words). The realism-vs-scenario routing and the
  definition-of-done are **not** re-copied per file — they live in `collections/CLAUDE.md` and each
  `TODO.md` item.
- **Checklist sections** — mirror the groupings the collection's `TODO.md` already uses (quick-win
  columns / high-leverage columns / candidate new tables / open realism items). Head each section
  with a link to the matching `TODO.md` section
  (``[`TODO.md` § <Section>](../../src/potato_tornado/collections/<name>/TODO.md#<github-anchor>)``),
  then list each item as a bare `- [ ]` checkbox with only its **identifier** (the `table.column`
  in backticks, or a short phrase for an investigate item) and, optionally, a compact dated
  run-note on completed items (e.g. `*(2026-07-11 — flat)*`). **No File / Draw / Unlocks / Class
  sub-bullets** — that substance stays in `TODO.md`. Don't add items the `TODO.md` doesn't have.

Keep the checklist and the collection's `TODO.md` in step: checking an item here means checking
it there when it lands, and recording the run in that collection's `realism-log.md`. Each run
writes a **new dated snapshot** — don't overwrite or delete earlier ones (they're a history).

## 6. Report

Summarize: which collections were scanned, which got a file (with its path and a one-line scope),
and which were skipped as done (with why). If nothing had open work, say so — that's a valid,
useful result. Nothing outside `docs/todos/` is created or edited.
