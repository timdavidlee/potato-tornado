"""Tests for potato_tornado.core.registry."""

from __future__ import annotations

import pytest

from potato_tornado.core.registry import get_collection, iter_collections


def test_builtin_collections_are_registered() -> None:
    assert {c.name for c in iter_collections()} == {"labor", "hotel", "clinic", "streaming"}


def test_get_unknown_collection_raises() -> None:
    with pytest.raises(KeyError, match="unknown collection"):
        get_collection("does-not-exist")
