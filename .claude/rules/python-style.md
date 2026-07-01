# Python style

Conventions for all Python in this repo. These reflect the enforced config in
[pyproject.toml](../../pyproject.toml) — when in doubt, run the tools rather than guess.

## Baseline

- **Target:** Python 3.11+ (`requires-python = ">=3.11"`, ruff/pyright target `py311`). Use
  modern syntax freely (`X | None`, `match`, `list[int]`, built-in generics — never
  `typing.List`/`Optional`). Avoid 3.12+-only syntax that would break the floor.
- **Formatter is authoritative.** Run `uv run ruff format`; never hand-format. Double quotes,
  space indent, 100-col line length (the formatter wraps).
- **Lint clean.** `uv run ruff check` must pass. Active rule sets: `E` (pycodestyle),
  `F` (pyflakes), `I` (isort — let ruff sort imports), `UP` (pyupgrade), `B` (bugbear),
  `SIM` (simplify), `C4` (comprehensions), `RUF`. Prefer `--fix` for mechanical issues; fix
  real warnings by hand.

## Typing (pyright standard)

- `uv run pyright` runs in **standard** mode over `src` and `tests`. This is a typed library
  (ships `py.typed`), so treat public API as fully typed: every public `def` gets annotated
  params and an explicit return type, including `-> None`.
- No implicit `Any` in public signatures. If a third-party value is untyped, narrow or cast it
  deliberately; don't let `Any` propagate through the API.
- Avoid `# type: ignore` — prefer fixing the type. If unavoidable, scope it to the specific
  rule (`# pyright: ignore[reportX]`) and add a one-line why.

## Functions vs. classes

- **Prefer plain functions.** A function with a few typed parameters is the default unit of
  code here — reach for it before a class. Free functions are easier to read and test.
- **When the parameter list grows unwieldy** (rough rule of thumb: more than ~4–5 positional
  args, or you find yourself threading the same bundle of values through several functions),
  stop passing loose arguments and pick one of:
  - a **class** when there's genuine mutable state or behavior to manage across calls
    (e.g. a sink that holds a connection, a stateful builder), or
  - a **dataclass / typed container** when you just need to pass a structured bundle of data
    around — a typed container is clearer than a long signature or a bare `dict`.
- Don't introduce a class purely to group functions that share no state — that's a module's
  job. Use a class when state or lifecycle justifies it, not as a namespace.
- **Everything stays fully type-annotated** regardless of which shape you choose.

## Docstrings

- **Private/helper functions can keep docstrings minimal** — a one-line summary is fine, or
  none at all when the name and signature already say everything.
- **When a function has a complex or loosely-typed shape, show a concrete example.** If a
  param or return is a generic container whose structure isn't obvious from the type alone —
  `dict[str, Any]`, `list[dict[str, Any]]`, nested/heterogeneous structures — include a small
  foo-bar example of the actual shape in the docstring:

  ```python
  def parse_events(raw: list[dict[str, Any]]) -> dict[str, Any]:
      """Group raw events by type.

      Example input:
          [{"type": "click", "x": 10}, {"type": "key", "code": "Esc"}]
      Example output:
          {"click": [{"x": 10}], "key": [{"code": "Esc"}]}
      """
  ```

  The example matters more than prose here — a reader should see the shape at a glance instead
  of reverse-engineering it from `dict[str, Any]`.
- Prefer a dataclass or `TypedDict` when the shape is fixed and worth naming. The
  example-in-docstring guidance is for the genuinely dynamic cases where a precise type isn't
  practical.

## Code reuse & structure

- **Check for existing functionality before writing new code.** Before adding a helper,
  parser, sink wrapper, etc., search the repo (`rg`/grep, or scan the relevant package) for
  something that already does it. Reuse or extend the existing thing rather than introducing a
  parallel implementation.
- **Shared functionality lives in `core/`.** When logic is used by more than one
  generator/sink/module — or you can see it about to be — move it into
  `src/potato_tornado/core/` and import it from there, rather than copy-pasting or leaving it
  buried in one module. Promote to `core/` only once it's genuinely shared.
- **Be minimal and precise.** Add the smallest change that solves the problem. Don't
  speculatively generalize, add unused parameters/branches, or build abstractions for a
  second caller that doesn't exist yet. New code should read like the code already around it.

## Layout & imports

- `src/` layout only. Import via the package path
  (`from potato_tornado.core import ...`); never import from a top-level dir.
- Keep imports at module top, sorted by ruff's isort. No conditional/lazy imports unless
  there's a real reason (heavy optional dep, circular-import break) — note it in a comment.
  The `postgres` extra is optional: guard imports of its deps (`sqlalchemy`, `psycopg`,
  `connectorx`) so the core install works without them.

## Dependencies

- New runtime deps go through `uv add` (dev deps `uv add --dev`) so `uv.lock` stays in sync —
  never hand-edit `pyproject.toml` dependency tables. Keep the core install light; put
  heavyweight or backend-specific deps behind an optional extra.
