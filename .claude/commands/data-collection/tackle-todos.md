---
description: Work a collection's open TODO checklist(s) via subagents — fan out one worker per collection (parallel across collections, serial within), optionally each in its own git worktree, realize the realism-class items end-to-end (edit generators with deterministic draws, regenerate, pin tests, reconcile the rubric), tick the checklist + backlog, then integrate, run the full gate, and refresh the inventory. Scenario-bearing items are routed to the scenario workflow, not auto-planted.
model: opus
---

Take the open TODO items for one or more collections and **actually realize them**, using
subagents to parallelize across collections. This is the *execute* counterpart to
[`/data-collection:scan-todos`](scan-todos.md) (which only writes the dated checklists). Each
realism-class item is built for real — generator edit, regenerate, pin a test, reconcile
`realism-guidance.md`, tick the checklist + `TODO.md`, append `realism-log.md` — following the
exact workflow of [`review-edit-regen-for-realism.md`](review-edit-regen-for-realism.md).

Read the "Realism log and TODO" and "Determinism still applies" sections of
[collections/CLAUDE.md](../../../src/potato_tornado/collections/CLAUDE.md) first. Follow
[.claude/rules/python-style.md](../../rules/python-style.md) and
[.claude/rules/pytest.md](../../rules/pytest.md) throughout.

## 1. `$ARGUMENTS`

Free-text scope + flags (interpret loosely):

- **Empty** — every collection that has an open checklist under
  [`docs/todos/`](../../../docs/todos/) (newest per collection), realism-class items only.
- **Collection name(s)** (e.g. `clinic logistics`) — scope to those.
- **A checklist path** (e.g. `docs/todos/2026-07-11-12:28-clinic-enrichment-backlog.md`) —
  scope to that file's collection + items.
- `quick-wins` — only the quick-win columns (the smallest, all-realism batch).
- `include-scenarios` — also realize scenario-bearing items (each via the
  [scenario realize](../scenario/review-and-edit-regenerate.md) workflow). **Off by default** —
  see §2.
- `worktree` — run each collection worker in its **own git worktree** (hard isolation; see §3).
  Off by default (the in-place scoped-gate model below is lighter).
- `serial` — run collections one at a time instead of in parallel (maximum safety / low noise).
- `plan-only` (or `dry-run`) — do Phase 1 only: report the plan, make **no** edits.

If the scope is ambiguous (no checklists exist and no collection named), list the collections
with open work and ask before touching anything.

## 2. What is in scope — realism vs. scenario-bearing

Each checklist item is classed **realism** or **scenario-bearing** (the `scan-todos` output
tags every item; corroborate against the collection's `TODO.md`).

- **Realism items** (quick-win columns, realism enrichment, open realism investigations) have a
  clean, testable definition of done — build the column/table *flat*, reconcile the rubric, pin
  an invariant test. **These are what this command realizes by default.**
- **Scenario-bearing items** plant a *surprising subset signal* — a teaching decision that goes
  through [`/scenario:draft-or-propose <name>`](../scenario/draft-or-propose.md) then
  [scenario realize](../scenario/review-and-edit-regenerate.md). **Do not auto-plant a signal.**
  By default, build only the item's *flat column* (that part is realism) and **leave the signal
  unplanted**, listing it in the report as a candidate to route. Only with `include-scenarios`
  do you drive the full scenario workflow — and even then, serially within the collection.

## 3. Concurrency model — read this before spawning anything

The unit of parallelism is the **collection**; within a collection, work items **serially**.
This is a correctness requirement, not a preference:

- **Across collections is safe to parallelize** — each is a separate package with its own
  `tables/`, its own `tests/collections/<name>/test_<name>.py`, and its own determinism test.
  Disjoint files, no shared state.
- **Within a collection you must serialize** — random streams are name-keyed off the *table*
  name, so two columns added to the same `tables/*.py` need a defined draw order; and the one
  `test_<name>.py` + the collection determinism test are shared. Two items realized at once on
  one collection would race and can shift every downstream draw. One worker owns the whole
  collection and does its items in order.
- **Scoped gate per worker, full gate by the orchestrator.** A worker runs the gate **scoped to
  its own paths** — `uv run ruff format src/potato_tornado/collections/<name> tests/collections/<name>`,
  the same for `ruff check`, `pyright <those paths>`, and `pytest tests/collections/<name>`.
  It must **not** run the repo-wide `ruff format` (that would rewrite another worker's files
  mid-flight). The orchestrator runs the one full repo-wide gate at the end (§6).
- **The orchestrator owns shared files.** Workers never touch `collections/INVENTORY.md`
  (refreshed once at the end) or anything outside their collection.

With `serial`, run the workers one at a time instead — everything else is unchanged.

### Worktree isolation (`worktree`)

By default the workers edit disjoint files in the **same** working tree, kept safe by the
scoped gate above. With `worktree`, each collection worker instead runs in its **own git
worktree** — launch it via the Agent tool's `isolation: worktree` option. This trades a little
setup cost (a fresh checkout per collection) for hard isolation:

- A worker's half-finished or broken edit can never touch another worker or your main tree; each
  can even run the **full** gate in its own worktree without racing.
- Each collection's work lands as an independently reviewable branch — so you *could* open one PR
  per collection instead of one combined diff.
- **Integration is conflict-free by construction.** Collections touch disjoint files, so merging
  the worktree branches back has no overlaps — except `INVENTORY.md`, which workers never touch
  (the orchestrator regenerates it after integration, §6).
- **Precondition:** worktrees branch from `HEAD`, so a worker only sees *committed* state. Commit
  (or stage) any pending `docs/todos/` checklists and `TODO.md`/`realism-log.md` edits before an
  isolated run, or the workers won't see the items to tick. If that's not desired, run in-place
  (the default) instead.

`worktree` composes with `serial` (isolated **and** one at a time) and is ignored under
`plan-only` (Phase 1 is read-only — no isolation needed).

## 4. Phase 1 — Plan (parallel, read-only)

Fan out **one read-only subagent per in-scope collection** (the `Explore` agent type fits) — in
a single message so they run concurrently. Each returns a concrete, ordered plan for its
collection, and **makes no edits**:

- Read the checklist + the collection's `TODO.md`, `realism-guidance.md`, the relevant
  `tables/*.py`, and `constants.py`.
- Generate + measure the current data (`generate('<name>', GenerationConfig(seed=7, scale=0.3))`)
  so it knows, per item, whether the column/table is **already present**, **partially there**,
  or **absent**, and what the flat draw recipe + invariant test should be.
- Return, per item: `{class: realism|scenario-bearing, status: todo|already-done|ambiguous,
  file, draw recipe, test to add, notes}`.

The orchestrator collects the plans and **reports the intended batch** (which items, which
collections, what's already-done or ambiguous). On `plan-only`/`dry-run`, stop here.

## 5. Phase 2 — Execute (parallel across collections, serial within)

Fan out **one worker subagent per collection** (the `general-purpose` agent type — it can edit
and run the gate). Launch them together (or one at a time under `serial`); under `worktree`,
launch each with the Agent tool's `isolation: worktree` option so it mutates its own checkout.
Give each worker this brief, parameterized by collection + its planned realism items:

> Realize, **in order**, these realism-class items for the `<name>` collection, following
> [`/data-collection:review-edit-regen-for-realism`](review-edit-regen-for-realism.md) for each:
> for every item — edit the relevant `tables/*.py` to add the column/table with **deterministic
> draws only** (`ctx.dist` / `ctx.rng.child("<name-keyed>")` / `ctx.entities`; never reorder
> existing draws, never wall-clock / `random` / numpy global RNG); regenerate at `seed=7,
> scale=0.3` and confirm the value + that no existing column shifted; add/extend a single-assert
> invariant test in `tests/collections/<name>/test_<name>.py`; reconcile the matching
> `realism-guidance.md` line; tick the item `- [ ]`→`- [x]` in **both** the `docs/todos/`
> checklist and the collection's `TODO.md`; and append one dated bullet to `realism-log.md`.
> After **each** item, run the **collection-scoped** gate
> (`ruff format`/`ruff check`/`pyright`/`pytest` limited to `…/collections/<name>` and
> `tests/collections/<name>`) and keep it green before moving on. If an item's scoped gate fails
> and you can't fix it quickly, **revert just that item's edits**, leave the item unchecked, and
> report it as blocked rather than leaving the tree broken. Do **not** run the repo-wide gate,
> do **not** touch `INVENTORY.md` or any other collection, and for scenario-bearing items build
> only the flat column (no planted signal) unless told otherwise. Return: items realized (with
> the test `file:line` and rubric line for each), items skipped/blocked (with why), and
> candidate signals you noticed for the scenario workflow.

If a worker reports a genuinely ambiguous fix-vs-deliberate-simplification call, surface it — do
not guess.

## 6. Phase 3 — Finish (orchestrator)

After all workers return:

0. **Integrate (worktree mode only).** Bring each collection worker's worktree branch back into
   the working tree. Because collections touch disjoint files, the merges are conflict-free; if
   any worktree is unchanged (a worker realized nothing), it's discarded. Skip this step in the
   default in-place mode — the edits are already in the tree.
1. **Full gate.** Run the one repo-wide gate and fix any cross-collection fallout:
   `uv run ruff format && uv run ruff check && uv run pyright && uv run pytest`. If it fails,
   stop and surface it — don't force past a red gate.
2. **Refresh the inventory.** Statuses moved, so re-render `collections/INVENTORY.md` per
   [`/data-collection:refresh-inventory`](refresh-inventory.md) (docs-only).
3. **Do not commit or merge.** Leave the work in the tree; committing is
   [`/pr-push-and-merge`](../pr-push-and-merge.md)'s job.

## 7. Report

Summarize per collection: items realized (with test `file:line` + the reconciled rubric line),
items left (blocked, ambiguous, or scenario-bearing-and-deferred, each with why), the full-gate
result, and the inventory refresh. List the candidate signals workers surfaced as the natural
follow-up for `/scenario:draft-or-propose`. Name what's still open so a follow-up run — or a
fresh `/data-collection:scan-todos` — picks up cleanly.
