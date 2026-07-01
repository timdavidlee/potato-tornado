---
description: Review CLAUDE.md / README.md against the current repo and update them (and add nested CLAUDE.md files where they'd help navigation)
model: opus
---

Audit this repo's guidance docs against reality and bring them up to date. The goal: a
teammate (or Claude Code) reading `CLAUDE.md` / `README.md` should find nothing stale, no
broken pointers, and no missing map for a part of the tree that has grown enough to need one.

If `$ARGUMENTS` is provided, scope the audit to that path or topic (e.g. a single package,
`README.md` only, "just check the toolchain commands"). Otherwise audit the whole repo.

## 1. Gather ground truth first

Do not trust the docs — check them against the repo as it is *now*.

- Find every guidance doc: the root `CLAUDE.md`, `README.md`, and all nested `CLAUDE.md`
  files (`find . -name CLAUDE.md -not -path './.git/*'`).
- Read the enforced conventions under [.claude/rules/](../rules/) — `python-style.md`,
  `pytest.md` — these are the source of truth the docs summarize.
- Establish the real layout: the packages under `src/potato_tornado/` (`core/`, `sinks/`,
  `generators/`, `collections/`, `cli`) and the test tree under `tests/`.
- Confirm the toolchain claims by inspection, not memory: read `pyproject.toml`
  (deps, optional extras, ruff/pyright/pytest config, scripts), `uv.lock` presence, and any
  git hooks. Use `git log --oneline -20` to see what changed recently.

## 2. Check each doc for staleness

For every guidance doc, verify and flag:

- **Broken or moved pointers.** Every file/dir path and relative link must resolve. Renamed or
  deleted modules are the most common rot here.
- **Layout drift.** The described directory structure matches the actual tree (new packages
  documented; removed ones gone).
- **Command / toolchain drift.** Commands, tool versions, Python version, lint rule sets,
  and config claims match `pyproject.toml` / the rules files.
- **Convention drift / new caveats.** Coding conventions and caveats still hold; anything a
  new pattern in the code now requires that the docs don't mention gets captured.
- **Contradictions.** A nested `CLAUDE.md` must not contradict the root one or the rules
  files; the root should point down to the nested maps rather than duplicate them.

## 3. Consider adding nested CLAUDE.md files

Nested `CLAUDE.md` files are how Claude Code navigates without loading the whole tree. Propose
a new one for any directory that (a) is a distinct enough subsystem that its own conventions or
entry points aren't obvious from the root doc, and (b) has grown enough to warrant a local map
(e.g. the `sinks/` package with its DuckDB/Postgres split, a `generators/` subtree). Keep each
one short: what lives here, how it's meant to be used, local gotchas, and a pointer back up.
Don't add one to a thin or self-explanatory directory — a CLAUDE.md that just restates the
filenames is noise.

## 4. Apply and report

- Make the edits directly. Keep the existing voice and formatting; prefer minimal, precise
  changes over rewrites. Follow the repo's own doc conventions.
- Do **not** invent conventions the code doesn't actually follow.
- When you finish, give a short summary: what was stale (with `file:line`), what you changed,
  and any new `CLAUDE.md` files you added and why. If something looks stale but you're not
  sure of the intended direction, list it as a question rather than guessing.
