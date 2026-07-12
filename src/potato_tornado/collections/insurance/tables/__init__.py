"""Table builders for the insurance collection.

One module per table; each exposes a ``build_<table>(ctx) -> pl.DataFrame``
function that the collection wires into a ``TableSpec``. Re-exported here so the
collection's ``__init__`` can import them from one place.
"""

from __future__ import annotations

from potato_tornado.collections.insurance.tables.adjuster_notes import build_adjuster_notes
from potato_tornado.collections.insurance.tables.adjusters import build_adjusters
from potato_tornado.collections.insurance.tables.brokers import build_brokers
from potato_tornado.collections.insurance.tables.claim_payments import build_claim_payments
from potato_tornado.collections.insurance.tables.claim_status_history import (
    build_claim_status_history,
)
from potato_tornado.collections.insurance.tables.claims import build_claims
from potato_tornado.collections.insurance.tables.coverage_lines import build_coverage_lines
from potato_tornado.collections.insurance.tables.policies import build_policies
from potato_tornado.collections.insurance.tables.policyholders import build_policyholders
from potato_tornado.collections.insurance.tables.premium_billing import build_premium_billing
from potato_tornado.collections.insurance.tables.quotes import build_quotes

__all__ = [
    "build_adjuster_notes",
    "build_adjusters",
    "build_brokers",
    "build_claim_payments",
    "build_claim_status_history",
    "build_claims",
    "build_coverage_lines",
    "build_policies",
    "build_policyholders",
    "build_premium_billing",
    "build_quotes",
]
