"""Domain reference data (catalogs) for the streaming collection.

The fixed "seed" facts the generators draw from: the subscription-plan ladder, the
subscription lifecycle mix, the one-off premium-rental price points, and the
comedic title catalogue — a globally-famous public figure paired with a plausible
show name in a genre they are *not* known for (e.g. "Tom Cruise in Big Mama's
Family"). See ``scenarios/`` for the signals these values are tuned to produce.
"""

from __future__ import annotations

# (plan, monthly_price, signup_weight) — the subscription ladder. `PLANS` feeds
# both the `plans` reference table and the `subscriptions` plan mix, so it is the
# single source of truth for tier names/prices.
PLANS = [
    ("Basic", 7.99, 0.30),
    ("Standard", 13.99, 0.50),
    ("Premium", 19.99, 0.20),
]

# Subscription lifecycle: currently paying vs. churned.
SUB_STATUS = ["active", "cancelled"]
SUB_STATUS_WEIGHTS = [0.78, 0.22]

TITLE_KINDS = ["series", "film"]
TITLE_KIND_WEIGHTS = [0.6, 0.4]

# One-off premium-rental price points (PVOD): a cheap catalogue rental, a standard
# new-release rental, and a premium day-and-date release.
PREMIUM_RENTAL_PRICES = [4.99, 6.99, 19.99]

# (region, display_name, subscriber_weight, catalog_density) — the markets the
# service operates in. `subscriber_weight` is that market's share of the
# subscriber base; `catalog_density` is the probability a given title is licensed
# there, so larger markets carry more of the catalogue (US widest, Japan
# narrowest). `REGIONS` feeds the `regions` table, the `subscribers` region mix,
# and the `title_availability` licensing bridge — the single source of truth.
REGIONS = [
    ("US", "United States", 0.34, 0.85),
    ("GB", "United Kingdom", 0.14, 0.60),
    ("DE", "Germany", 0.12, 0.55),
    ("BR", "Brazil", 0.16, 0.50),
    ("IN", "India", 0.16, 0.45),
    ("JP", "Japan", 0.08, 0.30),
]

# --- Title catalogue -----------------------------------------------------------
# Each title pairs a globally-famous public figure with a plausible show in a
# genre they are NOT known for — the comedic device is the mismatch. Names are
# fictional parody; the figures are public. See `tables/titles.py` for how these
# are composed.

# (celebrity, home_genre) — `home_genre` is the domain they are famous for, so the
# generator can pick a show genre that is deliberately *off-brand*. Home genres
# that overlap GENRES (comedy, crime, ...) are excluded from that figure's picks.
CELEBRITIES = [
    ("Tom Cruise", "action"),
    ("Keanu Reeves", "action"),
    ("Dwayne Johnson", "action"),
    ("Arnold Schwarzenegger", "action"),
    ("Gordon Ramsay", "cooking"),
    ("Bobby Flay", "cooking"),
    ("Martha Stewart", "cooking"),
    ("Guy Fieri", "cooking"),
    ("Ina Garten", "cooking"),
    ("Serena Williams", "sports"),
    ("LeBron James", "sports"),
    ("Cristiano Ronaldo", "sports"),
    ("Taylor Swift", "music"),
    ("Beyoncé", "music"),
    ("Adele", "music"),
    ("Snoop Dogg", "music"),
    ("Dolly Parton", "music"),
    ("Morgan Freeman", "drama"),
    ("Meryl Streep", "drama"),
    ("Denzel Washington", "drama"),
    ("David Attenborough", "documentary"),
    ("Neil deGrasse Tyson", "science"),
    ("Bill Nye", "science"),
    ("Oprah Winfrey", "talk"),
    ("Simon Cowell", "reality"),
    ("RuPaul", "reality"),
    ("Kevin Hart", "comedy"),
    ("Jerry Seinfeld", "comedy"),
]

# The show genres a figure can be dropped into.
GENRES = ["comedy", "horror", "romance", "sci_fi", "fantasy", "western", "crime", "musical"]

# Per-genre show-name templates. Slots: `{a}` adjective, `{n}` noun, `{p}` place,
# `{fam}` familiar/folksy name. Every `{p}` sits in a prepositional slot so places
# that carry a leading article ("the Jungle") still read correctly.
GENRE_TEMPLATES = {
    "comedy": [
        "Big {fam}'s Family",
        "The {a} Roommates",
        "{fam}'s Big Break",
        "My {a} Neighbor",
        "Honey, I Moved to {p}",
    ],
    "horror": [
        "Nightmare in {p}",
        "The Haunting of {p}",
        "Blood {n}",
        "The {a} Below",
        "Whispers in {p}",
    ],
    "romance": [
        "Love in {p}",
        "The {a} Heart",
        "A {a} Affair",
        "Summer with {fam}",
        "Kisses in {p}",
    ],
    "sci_fi": [
        "Beyond {p}",
        "The {a} Protocol",
        "Starfall over {p}",
        "Quantum {n}",
        "The Last {n}",
    ],
    "fantasy": [
        "The {a} Crown",
        "Realm of {n}",
        "The {n} Prophecy",
        "Dragons of {p}",
        "The {a} Sorcerer",
    ],
    "western": [
        "Dust and {n}",
        "High Noon in {p}",
        "The Last Ride to {p}",
        "Outlaws of {p}",
        "{fam}'s Frontier",
    ],
    "crime": [
        "Heist in {p}",
        "{a} Streets",
        "Blood Money in {p}",
        "The {n} Syndicate",
        "Midnight in {p}",
    ],
    "musical": [
        "Dancing through {p}",
        "The {a} Melody",
        "Songs of {p}",
        "{fam}'s Big Number",
        "A {a} Rhythm",
    ],
}

# How the figure is stitched onto the show. `OUTER_POSSESSIVE` drops a leading
# "The "/"A " from the show so "Bobby Flay's The Silent Below" reads as
# "Bobby Flay's Silent Below".
OUTER_POSSESSIVE = "{celeb}'s {show}"
OUTER_TEMPLATES = ["{celeb} in {show}", OUTER_POSSESSIVE]

TITLE_ADJECTIVES = [
    "Silent",
    "Crimson",
    "Broken",
    "Golden",
    "Hidden",
    "Wild",
    "Electric",
    "Frozen",
    "Savage",
    "Velvet",
    "Midnight",
    "Restless",
]
TITLE_NOUNS = [
    "Harbor",
    "Empire",
    "Ashes",
    "Signal",
    "Frontier",
    "Reckoning",
    "Legacy",
    "Mirage",
    "Requiem",
    "Tempest",
    "Verdict",
    "Horizon",
]
TITLE_PLACES = [
    "the Jungle",
    "Willow Creek",
    "New Vegas",
    "the Bayou",
    "Cedar Falls",
    "Old Tucson",
    "the Highlands",
    "Miami",
    "the Outback",
    "Ravenwood",
    "Rio",
    "the Badlands",
]
TITLE_FAMILIARS = ["Mama", "Bubba", "Nana", "Papa", "Earl", "Granny", "Tank", "Gizmo"]
