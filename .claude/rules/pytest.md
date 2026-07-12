# Pytest

How tests are written and run in this repo. Config lives in
[pyproject.toml](../../pyproject.toml) under `[tool.pytest.ini_options]`.

## Running

- Always via uv: `uv run pytest`. Tests are collected from `tests/` only (`testpaths`).
- `addopts = "-ra --strict-markers"` is active:
  - `--strict-markers` — every `@pytest.mark.<x>` must be registered in `pyproject.toml`
    first, or collection errors. Don't invent ad-hoc markers.
  - `-ra` — a short summary of non-passing tests prints after each run.
- **Full suite: run it in parallel** with `uv run pytest -n auto --dist loadscope`
  (`pytest-xdist`, ~2.5× faster). Tests are deterministic (seeded) and isolated (DuckDB
  in-memory / `tmp_path`, no shared files or global state), so parallelizing is safe.
  `--dist loadscope` pins each test module to a single worker so the module-scoped
  collection-generation fixtures generate once per module instead of once per worker —
  materially faster than the default `--dist load`. `-n` is intentionally left out of
  `addopts` so a single-test debug run (`uv run pytest tests/foo.py::test_bar`) skips the
  worker-startup overhead; add `-n auto --dist loadscope` yourself for full-suite runs.
- `pytest-cov` is available; run `uv run pytest --cov=potato_tornado` when you want coverage.

## Layout

- The `tests/` tree **mirrors the `src/` tree one-to-one**. Every module gets a sibling test
  file at the same relative path:
  `src/potato_tornado/sinks/duckdb_sink.py` -> `tests/sinks/test_duckdb_sink.py`.
  Mirror the directory structure exactly — don't flatten or regroup tests.
- Files are `test_*.py`, functions are `test_*`, classes (rare) are `Test*`.

## Writing tests

- **Prefer a single assert per test.** Each test pins one behavior with one assertion; if you
  reach for a second `assert`, that's usually a second test (or a parametrize case). A few
  tightly-related asserts on one logical outcome are fine — many asserts checking different
  behaviors is not.
- **Use pytest-native structures, not `unittest`.** Plain `assert` (pytest rewrites it for rich
  diffs), `pytest.raises`, `pytest.fixture`, `tmp_path`, `monkeypatch`, `capsys`. Never
  `unittest.TestCase`, `self.assertEqual`, `setUp`/`tearDown`, or `@mock.patch` decorators —
  use the `monkeypatch` fixture instead.
- **Prefer `@pytest.mark.parametrize` for repetition.** Any time tests differ only in
  inputs/expected values, collapse them into one parametrized test rather than copy-pasting —
  it keeps the single-assert shape and makes the case table obvious. (`parametrize` is built in
  and fine under `--strict-markers`; custom markers must be registered first.)
- Prefer **fixtures** over setup/teardown; keep them in a local `conftest.py` when shared
  across a directory.
- **Annotate test functions** too — `def test_x() -> None:`. pyright covers `tests/`, so keep
  test code typed to match the project's style.
- One behavior per test; name it for the behavior (`test_rejects_empty_seed`), not the
  function under test.
- Use `tmp_path`/`monkeypatch` for filesystem and env isolation — never touch real files,
  cwd, or global state.

## Determinism & external systems

- **Randomness must be seeded.** Generators are backed by a seeded RNG (`core/rng.py`); tests
  that assert on generated values must pin the seed so results are reproducible. Never rely on
  unseeded `random`/`numpy` state.
- **DuckDB tests** can run against an in-memory or `tmp_path`-backed database — cheap and
  deterministic, so exercise the real DuckDB sink rather than mocking it.
- **Postgres is optional** (the `postgres` extra). Don't require a live Postgres server for the
  default test run: mock the connection/engine, or mark and skip Postgres-backed tests when the
  extra / server isn't present. `uv run pytest` must pass on a bare core install.

## Before committing

Full gate:
`uv run ruff format && uv run ruff check && uv run pyright && uv run pytest -n auto --dist loadscope`.
