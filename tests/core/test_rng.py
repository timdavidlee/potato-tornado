"""Tests for potato_tornado.core.rng."""

from __future__ import annotations

from potato_tornado.core.rng import Rng


def _draw(rng: Rng) -> list[int]:
    return rng.numpy.integers(0, 1000, 5).tolist()


def test_child_stream_is_stable_across_sibling_creation() -> None:
    root = Rng(123)
    before = _draw(root.child("employees"))
    _ = root.child("shifts")  # creating a sibling must not shift "employees"
    after = _draw(root.child("employees"))
    assert before == after


def test_child_streams_differ_by_name() -> None:
    root = Rng(123)
    assert _draw(root.child("employees")) != _draw(root.child("shifts"))
