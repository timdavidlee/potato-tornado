"""Collection: streaming service subscriptions and one-off premium rentals.

Models a subscription video service with two revenue streams: recurring
subscriptions on a plan ladder (Basic / Standard / Premium), and one-off premium
"pay-per-view" rentals of eligible titles billed on top of the subscription. Title
*names* are placeholders today (see ``tables/titles.py``) pending a curated
fake-show catalogue.

Tables
------
- ``plans``         : the subscription-tier catalogue with monthly prices.
- ``titles``        : the content catalogue (placeholder names).
- ``subscribers``   : user accounts.
- ``subscriptions`` : one subscription per subscriber, active or cancelled.
- ``rentals``       : one-off premium (PVOD) rentals of premium-eligible titles.

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.streaming.tables import (
    build_plans,
    build_rentals,
    build_subscribers,
    build_subscriptions,
    build_titles,
)
from potato_tornado.core.collection import Collection, TableSpec
from potato_tornado.core.registry import register


def build() -> Collection:
    return Collection(
        name="streaming",
        description="Streaming service: recurring subscriptions on a plan ladder "
        "plus one-off premium (PVOD) rentals of eligible titles.",
        tables=(
            TableSpec("plans", build_plans, description="Subscription-tier catalogue."),
            TableSpec("titles", build_titles, description="Content catalogue (placeholder names)."),
            TableSpec("subscribers", build_subscribers, description="User accounts."),
            TableSpec(
                "subscriptions",
                build_subscriptions,
                depends_on=("subscribers", "plans"),
                description="One subscription per subscriber, active or cancelled.",
            ),
            TableSpec(
                "rentals",
                build_rentals,
                depends_on=("subscribers", "titles"),
                description="One-off premium rentals of premium-eligible titles.",
            ),
        ),
    )


register("streaming", build)
