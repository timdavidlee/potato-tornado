"""The ``adjuster_notes`` table: one free-text loss-description note per claim.

Each claim gets a single adjuster note whose ``body`` narrates the cause of loss and
renders the reported loss estimate in prose. For water-damage claims the note also
encodes the **sudden vs gradual** coverage trigger in its wording — the one fact that
lives nowhere in the structured columns (see
``scenarios/gradual-water-losses-settle-below-sudden.md``).

``body`` is the source of truth: the dollar figure it renders is ``claims.reported_amount``
(rounded to the nearest dollar) so a parser reconciles the estimate with no answer leaked;
the withheld ``water_cause`` answer-key column (``sudden``/``gradual``/null) exists **only**
to verify a parser recovers the label from the prose and is not handed to students. Three
name-keyed template variants vary the phrasing so the parser must handle real variation.
"""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.insurance.water_cause import WATER_PERIL, water_cause_labels
from potato_tornado.core.collection import GenContext

_N_VARIANTS = 3

# Water-damage note phrasings. Each variant carries the keyword cues a parser classifies on
# — gradual: "seepage" / "long-term" / "gradual" / "wear" / "deterioration" / "over time" /
# "maintenance"; sudden: "burst" / "sudden" / "accidental discharge" / "ruptured" /
# "sprang a leak". A sudden note never contains a gradual cue word (or vice versa), so the
# cause is unambiguously recoverable from the text.
_GRADUAL_TEMPLATES = (
    "Inspected {pol} on {date}. Damage traced to long-term seepage behind the wall — "
    "consistent with gradual deterioration rather than a single event. Initial loss "
    "estimate {est}. Coverage position under review given the wear-and-tear exclusion.",
    "FNOL for {pol} dated {date}: moisture damage from slow seepage that developed over "
    "time — a maintenance-related, gradual loss, not an abrupt failure. Initial loss "
    "estimate {est}. Reviewing the wear-and-tear exclusion before adjudication.",
    "Loss on {pol} reported {date}. Findings indicate long-term water intrusion and "
    "material deterioration from ongoing wear. Initial loss estimate {est}. Adjuster flags "
    "a gradual cause and a likely coverage limitation.",
)
_SUDDEN_TEMPLATES = (
    "FNOL for {pol}: a supply line burst on {date}, a sudden accidental discharge that "
    "flooded the area. Initial loss estimate {est}. Clear accidental-discharge trigger, a "
    "covered cause.",
    "Inspected {pol} on {date}. A pipe ruptured and sprang a leak — a sudden, one-time "
    "discharge. Initial loss estimate {est}. Covered accidental discharge.",
    "Loss on {pol} reported {date}. Cause: a hose that burst without warning, a sudden "
    "discharge across the floor. Initial loss estimate {est}. Straightforward accidental "
    "water-discharge claim.",
)

# Non-water perils get a generic description with the reported estimate. These deliberately
# avoid every water cue word so a broad parse never misreads them.
_PERIL_PHRASES = {
    "collision": "a vehicle collision",
    "theft": "a reported theft and break-in",
    "weather": "storm and hail damage to the roof",
    "fire": "fire and smoke damage",
    "liability": "a third-party liability incident",
}
_GENERIC_TEMPLATES = (
    "Inspected {pol} on {date}. Loss attributed to {phrase}. Initial loss estimate {est}. "
    "Proceeding with standard adjustment.",
    "FNOL for {pol} dated {date}: {phrase} reported by the insured. Initial loss estimate "
    "{est}. Documentation requested to finalize the file.",
    "Loss on {pol} reported {date}. Cause of loss: {phrase}. Initial loss estimate {est}. "
    "Handling under the applicable coverage.",
)


def build_adjuster_notes(ctx: GenContext) -> pl.DataFrame:
    claims = ctx.table("claims")
    claim_ids = claims["claim_id"].to_list()
    policy_ids = claims["policy_id"].to_list()
    perils = claims["peril"].to_list()
    claim_dates = claims["claim_date"].to_list()
    reported = claims["reported_amount"].to_numpy()
    n = len(claim_ids)

    is_water = [p == WATER_PERIL for p in perils]
    # The withheld answer key, recomputed from the same pure function that tilted
    # adjudication in `claims` — identical assignment, never a structured `claims` column.
    causes = water_cause_labels(ctx.config.seed, claim_ids, is_water)
    variant = ctx.rng.child("template").numpy.integers(0, _N_VARIANTS, n)

    bodies: list[str] = []
    for i in range(n):
        pol = policy_ids[i]
        date_str = claim_dates[i].isoformat()
        # Render the real reported amount (rounded to the dollar) — derived, not re-sampled.
        est = f"${round(float(reported[i])):,}"
        v = int(variant[i])
        match causes[i]:
            case "gradual":
                body = _GRADUAL_TEMPLATES[v].format(pol=pol, date=date_str, est=est)
            case "sudden":
                body = _SUDDEN_TEMPLATES[v].format(pol=pol, date=date_str, est=est)
            case _:
                phrase = _PERIL_PHRASES[perils[i]]
                body = _GENERIC_TEMPLATES[v].format(pol=pol, date=date_str, est=est, phrase=phrase)
        bodies.append(body)

    return pl.DataFrame(
        {
            "note_id": [f"NOTE-{i:07d}" for i in range(1, n + 1)],
            "claim_id": claim_ids,
            "body": bodies,
            "water_cause": causes,
        }
    )
