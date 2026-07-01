"""Collection: streaming service subscriptions and one-off premium rentals.

Models a subscription video service with two revenue streams: recurring
subscriptions on a plan ladder (Basic / Standard / Premium), and one-off premium
"pay-per-view" rentals of eligible titles billed on top of the subscription. Title
names are parody — a famous public figure dropped into an off-genre show ("Tom
Cruise in Big Mama's Family") — see ``tables/titles.py``.

Subscribers belong to a region (market), and titles are licensed to a subset of
regions, so a subscriber can only rent a title available where they are.

Tables
------
- ``plans``              : the subscription-tier catalogue with monthly prices.
- ``regions``            : the markets the service operates in.
- ``actors``             : the public-figure catalogue with each figure's home genre.
- ``titles``             : the content catalogue; parody "figure in off-genre show"
                           names, with the figure/genre split out as columns.
- ``title_availability`` : which titles are licensed in which regions (many-to-many).
- ``subscribers``        : user accounts, each in a region.
- ``subscriptions``      : one subscription per subscriber, active or cancelled.
- ``rentals``            : one-off premium (PVOD) rentals, licensed to the renter's region.

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.streaming.tables import (
    build_actors,
    build_plans,
    build_regions,
    build_rentals,
    build_subscribers,
    build_subscriptions,
    build_title_availability,
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
            TableSpec("regions", build_regions, description="Markets the service operates in."),
            TableSpec(
                "actors",
                build_actors,
                description="Public-figure catalogue with each figure's home genre.",
            ),
            TableSpec(
                "titles",
                build_titles,
                description="Content catalogue: parody figure-in-off-genre-show titles.",
            ),
            TableSpec(
                "title_availability",
                build_title_availability,
                depends_on=("titles",),
                description="Which titles are licensed in which regions (many-to-many).",
            ),
            TableSpec(
                "subscribers", build_subscribers, description="User accounts, each in a region."
            ),
            TableSpec(
                "subscriptions",
                build_subscriptions,
                depends_on=("subscribers", "plans"),
                description="One subscription per subscriber, active or cancelled.",
            ),
            TableSpec(
                "rentals",
                build_rentals,
                depends_on=("subscribers", "titles", "title_availability"),
                description="One-off premium rentals, licensed to the renter's region.",
            ),
        ),
    )


register("streaming", build)
