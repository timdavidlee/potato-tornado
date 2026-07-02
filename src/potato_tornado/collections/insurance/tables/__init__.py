"""Table builders for the insurance collection.

One module per table; each exposes a ``build_<table>(ctx) -> pl.DataFrame``
function that the collection wires into a ``TableSpec``. Re-exported here so the
collection's ``__init__`` can import them from one place.
"""

from __future__ import annotations

from potato_tornado.collections.insurance.tables.brokers import build_brokers
from potato_tornado.collections.insurance.tables.claim_payments import build_claim_payments
from potato_tornado.collections.insurance.tables.claims import build_claims
from potato_tornado.collections.insurance.tables.policies import build_policies
from potato_tornado.collections.insurance.tables.policyholders import build_policyholders

__all__ = [
    "build_brokers",
    "build_claim_payments",
    "build_claims",
    "build_policies",
    "build_policyholders",
]
