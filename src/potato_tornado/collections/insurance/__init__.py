"""Collection: insurance — a property-and-casualty book.

Policyholders buy policies that earn premium; a minority file claims; each claim is
adjudicated to a payout (or denied); and the book is measured by its loss ratio.
The first collection built on a **frequency-severity** model — *whether* a policy
claims (a rare Poisson event, keyed to risk tier) is separate from *how much* a
claim costs (a heavy right-skew severity) — with a portfolio-level loss ratio
(Σ paid ÷ Σ premium) that rises with risk tier.

Tables
------
- ``brokers``        : the selling-broker dim.
- ``adjusters``      : the claims-handler dim.
- ``policyholders``  : the insured parties, each with a risk tier.
- ``policies``       : one policy sold per row — the premium side (the plan).
- ``quotes``         : pre-bind quotes upstream of policies; most never convert.
- ``claims``         : the filings — frequency x severity; most policies produce none.
- ``claim_payments`` : the payout (the actual), one row per settled claim.

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.insurance.tables import (
    build_adjusters,
    build_brokers,
    build_claim_payments,
    build_claims,
    build_policies,
    build_policyholders,
    build_quotes,
)
from potato_tornado.core.collection import Collection, TableSpec
from potato_tornado.core.registry import register


def build() -> Collection:
    return Collection(
        name="insurance",
        description="A property-and-casualty insurer: policyholders buy policies that earn "
        "premium, a minority file claims adjudicated to a payout or denied, and the book is "
        "measured by its loss ratio — a frequency-severity model with loss ratio by risk tier.",
        tables=(
            TableSpec("brokers", build_brokers, description="Selling-broker dim."),
            TableSpec("adjusters", build_adjusters, description="Claims-handler dim."),
            TableSpec(
                "policyholders",
                build_policyholders,
                description="Insured parties, each with a risk tier.",
            ),
            TableSpec(
                "policies",
                build_policies,
                depends_on=("policyholders", "brokers"),
                description="One policy sold per row — premium, coverage, deductible.",
            ),
            TableSpec(
                "quotes",
                build_quotes,
                depends_on=("policies", "policyholders"),
                description="Pre-bind quotes; one converting quote per policy plus non-converting.",
            ),
            TableSpec(
                "claims",
                build_claims,
                depends_on=("policies", "policyholders", "adjusters"),
                description="The filings — frequency x severity; most policies produce none.",
            ),
            TableSpec(
                "claim_payments",
                build_claim_payments,
                depends_on=("claims", "policies"),
                description="Payout (actual), one row per settled claim.",
            ),
        ),
    )


register("insurance", build)
