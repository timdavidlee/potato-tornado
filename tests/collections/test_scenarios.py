"""Structural checks on the per-collection scenario / realism docs.

Every collection must ship at least one ``scenarios/*.md`` doc describing an
intended signal in its data, plus a ``realism-guidance.md`` review rubric at the
package root. This guards the docs-first convention (see ``collections/CLAUDE.md``):
the markdown is the source of truth that the planned ``Scenario`` objects will be
built against, so it must not silently go missing.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from potato_tornado.core.registry import iter_collections

COLLECTION_NAMES = [c.name for c in iter_collections()]


def _package_dir(name: str) -> Path:
    module = importlib.import_module(f"potato_tornado.collections.{name}")
    assert module.__file__ is not None
    return Path(module.__file__).parent


@pytest.mark.parametrize("name", COLLECTION_NAMES)
def test_collection_has_scenario_docs(name: str) -> None:
    assert list((_package_dir(name) / "scenarios").glob("*.md"))


@pytest.mark.parametrize("name", COLLECTION_NAMES)
def test_collection_has_realism_guidance(name: str) -> None:
    assert (_package_dir(name) / "realism-guidance.md").is_file()
