---
description: Regenerate collections/INVENTORY.md — the at-a-glance table of every built-in collection (table count, realism status, scenario coverage, field-enrichment backlog state) — from the current repo state. Docs only, no generators or tests.
model: opus
---

Rebuild [`collections/INVENTORY.md`](../../../src/potato_tornado/collections/INVENTORY.md), the
one-screen index of every built-in collection. Unlike the other `data-collection:*` commands,
this one **surveys nothing new and proposes nothing** — it just reads the facts that already
live in the repo (package contents + each collection's own status docs) and re-renders the
inventory table so it matches reality. It is **docs only**: it does not touch any
`build_<table>`, `constants.py`, `register(...)`, `realism-guidance.md`, scenarios, or tests.

Run it whenever the inventory could have drifted — after adding a collection or a table, after
a realism/enrichment/scenario pass flips a status, or just to re-verify the snapshot date.

## 1. `$ARGUMENTS`

Normally empty — refresh the whole inventory. If `$ARGUMENTS` names one collection, still
re-render the **entire** file (the table is all-or-nothing), but focus your re-measurement and
your report on that collection.

## 2. Enumerate the collections

The source of truth for *which* collections exist is `_BUILTIN_MODULES` in
[`core/registry.py`](../../../src/potato_tornado/core/registry.py) — enumerate from there (or
equivalently the package dirs under `collections/`), not from the old INVENTORY.md, so a newly
added or removed collection is picked up. For each one, measure the four columns from the repo:

- **Tables** — count the table-builder modules under `collections/<name>/tables/` (the
  `*.py` files, excluding `__init__.py`). One module = one table.
- **Realism status** — read the **Status:** line at the top of
  `collections/<name>/realism-log.md` (e.g. *Converged*, *Needs investigation*). Carry over its
  short qualifier (e.g. "reference collection", "2 fixes landed") verbatim where it adds signal.
- **Scenarios** — count the scenario docs under `collections/<name>/scenarios/` (`*.md`,
  excluding any `README`/index file). If some are proposed-but-not-yet-realized, note it.
- **Field-enrichment backlog** — read the **Status** section of `collections/<name>/TODO.md`:
  fully done, N-of-M shipped (name what's deferred), partially built (name the built tables), or
  surveyed-only / nothing-built-yet. Prefer the TODO's own wording.

Read the actual files — don't infer status from the previous INVENTORY.md. If a collection is
missing one of these docs, say so in that cell rather than guessing.

## 3. Re-render `INVENTORY.md`

Rewrite the file in place, preserving its existing shape (intro blurb, the `_As of <date>_`
line, the pipe table with the collection name linked to its package dir, a **Totals** line, and
the `## Notes` bullets). Specifically:

- **Order** the rows by maturity — most mature first (converged + backlog done), the
  not-yet-converged collection last — matching how the file already reads. Don't sort
  alphabetically.
- **Totals** line: number of collections and the summed table count.
- **`_As of <date>_`**: stamp today's date (from the `# currentDate` context / environment).
  Don't invent a date or copy the stale one — if you're unsure of today's date, ask.
- **Notes**: refresh the prose bullets so they still match the table — the not-converged
  outlier, the mature group, the surveyed-vs-built split, and the "every collection ships a full
  doc set + tests" line. Keep them tight; the table carries the detail.

If the on-disk INVENTORY.md was hand-edited since the last refresh (the injected-file notice or
a diff will show it), treat those edits as intentional — reconcile your measurements with them
rather than blindly reverting, and only change cells the repo actually contradicts.

## 4. Report

Summarize what changed versus the previous INVENTORY.md: any new/removed collection, table-count
deltas, status flips (realism or backlog), scenario-count changes, and the new snapshot date. If
everything already matched, say so — a no-op refresh is a valid, useful result. Nothing outside
INVENTORY.md is edited.
