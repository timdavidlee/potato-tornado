"""The ``brokers`` table: the selling-broker dimension.

Per-broker ``tenure_years`` and ``commission_rate`` are producer attributes (the
commission the broker earns on a policy's ``annual_premium``), each drawn off its own
name-keyed child stream so adding them leaves ``region`` byte-identical. Both are
signal-free — no producer-performance coupling is planted here (that remains a
scenario candidate).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from potato_tornado.core.collection import GenContext

# Coarse sales regions a broker covers — a single-table literal, so inline.
_REGIONS = ["Northeast", "South", "Midwest", "West"]
# Commission band on premium (single-table literals).
_COMMISSION_LOW = 0.08
_COMMISSION_HIGH = 0.15

# Tenure (years as a producer) is right-skewed, not uniform: an agency keeps many
# newer producers and a thinning tail of veterans. Geometric-style decaying weights
# over [1, 30] (ratio 0.90) concentrate mass at low tenure with a smooth taper — no
# pile-up at the boundary (value 30 is the smallest weight). Single-table literals.
_TENURE_MIN = 1
_TENURE_MAX = 30
_TENURE_DECAY = 0.90
_TENURE_VALUES = np.arange(_TENURE_MIN, _TENURE_MAX + 1)
_TENURE_P = _TENURE_DECAY ** (_TENURE_VALUES - _TENURE_MIN)
_TENURE_P = _TENURE_P / _TENURE_P.sum()


def build_brokers(ctx: GenContext) -> pl.DataFrame:
    n = ctx.n(40)
    people = ctx.entities.people(n)
    commission_rate = ctx.rng.child("commission").numpy.uniform(
        _COMMISSION_LOW, _COMMISSION_HIGH, size=n
    )
    return pl.DataFrame(
        {
            "broker_id": [f"BRK-{i:03d}" for i in range(1, n + 1)],
            "full_name": people["full_name"],
            "email": people["email"],
            "region": ctx.dist.choice(n, _REGIONS),
            "tenure_years": ctx.rng.child("tenure").numpy.choice(
                _TENURE_VALUES, size=n, p=_TENURE_P
            ),
            "commission_rate": np.round(commission_rate, 3),
        }
    )
