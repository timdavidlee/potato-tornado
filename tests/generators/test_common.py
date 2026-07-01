"""Tests for potato_tornado.generators.common."""

from __future__ import annotations

import polars as pl
import pytest
from faker import Faker

from potato_tornado.generators.common import people_frame, sequential_ids


def test_sequential_ids_are_zero_padded_with_prefix() -> None:
    ids = sequential_ids(3, prefix="EMP-", width=5)
    assert ids.to_list() == ["EMP-00001", "EMP-00002", "EMP-00003"]


def test_sequential_ids_without_prefix_are_integers() -> None:
    ids = sequential_ids(3)
    assert ids.dtype == pl.Int64


def test_sequential_ids_respect_start() -> None:
    ids = sequential_ids(2, prefix="X", width=2, start=10)
    assert ids.to_list() == ["X10", "X11"]


@pytest.mark.parametrize("column", ["full_name", "email"])
def test_people_frame_has_expected_columns(column: str) -> None:
    faker = Faker()
    faker.seed_instance(1)
    assert column in people_frame(faker, 4).columns


def test_people_frame_emails_are_unique() -> None:
    faker = Faker()
    faker.seed_instance(1)
    frame = people_frame(faker, 10)
    assert frame["email"].n_unique() == frame.height
