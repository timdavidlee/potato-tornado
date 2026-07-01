"""Tests for potato_tornado.core.collection."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest
from faker import Faker

from potato_tornado.core.collection import Collection, GenContext, TableSpec
from potato_tornado.core.config import GenerationConfig


def test_build_order_is_topological() -> None:
    coll = Collection(
        name="t",
        description="",
        tables=(
            TableSpec("c", lambda ctx: pl.DataFrame({"x": [1]}), depends_on=("b",)),
            TableSpec("a", lambda ctx: pl.DataFrame({"x": [1]})),
            TableSpec("b", lambda ctx: pl.DataFrame({"x": [1]}), depends_on=("a",)),
        ),
    )
    order = [spec.name for spec in coll.build_order()]
    assert order.index("a") < order.index("b") < order.index("c")


def test_detects_circular_dependency() -> None:
    coll = Collection(
        name="t",
        description="",
        tables=(
            TableSpec("a", lambda ctx: pl.DataFrame({"x": [1]}), depends_on=("b",)),
            TableSpec("b", lambda ctx: pl.DataFrame({"x": [1]}), depends_on=("a",)),
        ),
    )
    with pytest.raises(ValueError, match="circular"):
        coll.build_order()


def test_rejects_dependency_on_unknown_table() -> None:
    coll = Collection(
        name="t",
        description="",
        tables=(TableSpec("a", lambda ctx: pl.DataFrame({"x": [1]}), depends_on=("ghost",)),),
    )
    with pytest.raises(ValueError, match="unknown table"):
        coll.build_order()


def test_table_requires_declared_dependency() -> None:
    def build_b(ctx: GenContext) -> pl.DataFrame:
        return ctx.table("missing")

    coll = Collection(name="t", description="", tables=(TableSpec("b", build_b),))
    with pytest.raises(KeyError):
        coll.generate(GenerationConfig(), Faker())


def test_object_columns_are_normalized_to_concrete_dtype() -> None:
    def build(ctx: GenContext) -> pl.DataFrame:
        # numpy object array of str would otherwise land as pl.Object.
        return pl.DataFrame({"label": np.array(["a", "b"], dtype=object)})

    coll = Collection(name="t", description="", tables=(TableSpec("only", build),))
    out = coll.generate(GenerationConfig(), Faker())["only"]
    assert out.schema["label"] == pl.Utf8
