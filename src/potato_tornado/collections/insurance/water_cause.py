"""The note-native sudden/gradual water-loss label.

The sudden-vs-gradual coverage trigger for a water-damage claim — a burst pipe (a
covered *accidental discharge*) vs. long-term seepage/wear (an *excluded* cause) — is
recorded **only** in the adjuster's free-text loss description, never as a structured
``claims`` column, so a plain ``GROUP BY peril`` cannot see it. Two builders nonetheless
need the *same* label: ``claims`` tilts water-damage adjudication on it, and
``adjuster_notes`` renders it into prose (and ships it as a withheld answer-key column).

Because random streams are keyed per table (``Rng.child(<table>)``), those two builders
can't share a child stream. So the label is a **pure, seed-keyed function of the claim
id** — reproducible identically in both, without the label ever becoming a queryable
``claims`` field. See ``scenarios/gradual-water-losses-settle-below-sudden.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

from potato_tornado.core.rng import Rng

# The peril whose adjudication splits on the note-native cause.
WATER_PERIL = "water_damage"

# Share of water-damage claims described as a *gradual* (wear/seepage, coverage-excluded)
# loss; the rest are *sudden* accidental discharge (a covered cause). ≈60/40 sudden/gradual.
GRADUAL_SHARE = 0.40


def water_cause_labels(
    seed: int, claim_ids: Sequence[str], is_water: Sequence[bool]
) -> list[str | None]:
    """Per-claim ``"sudden"``/``"gradual"`` label for water-damage claims (else ``None``).

    A pure function of ``(seed, claim_id)`` so both consumers reproduce the identical
    assignment without the label leaking into a structured column. It is keyed off the run
    ``seed`` (so it responds to it) through the repo's own name-hashed :class:`Rng`, and
    off each ``claim_id`` (so it is independent of row order across the two callers).
    ~``GRADUAL_SHARE`` of water claims come back ``"gradual"``, the rest ``"sudden"``;
    every non-water claim is ``None``.

    Example:
        ``water_cause_labels(7, ["CLM-0000001", "CLM-0000002"], [True, False])``
        → ``["gradual", None]``
    """
    stream = Rng(seed).child("insurance/water_cause")
    out: list[str | None] = []
    for claim_id, water in zip(claim_ids, is_water, strict=True):
        if not water:
            out.append(None)
            continue
        draw = float(stream.child(claim_id).numpy.random())
        out.append("gradual" if draw < GRADUAL_SHARE else "sudden")
    return out
