# Realism guidance — clinic

What "realistic" means for this collection: the plausibility rules a reviewer (human or
Claude) checks freshly generated data against. This is the **review rubric**, distinct from
`scenarios/` (the intended teachable signals). Scenarios say what a student should *find*;
this doc says what the data must never get *wrong*, and which departures from reality are
deliberate so a reviewer doesn't "fix" them.

Magnitudes here must track the generators in `tables/` — if you retune a distribution,
update the matching line below in the same change.

## Invariants (must always hold)

- **Referential integrity.** Every `appointments.patient_id ∈ patients` and
  `appointments.provider_id ∈ providers`.
- **Booking arithmetic.** `lead_days ∈ [0, 120]`; `appointments.scheduled_at` falls inside
  the config `[start_date, end_date)` window.
- **Status is one of the lifecycle values.** `appointments.status ∈ {completed, no_show,
  cancelled, scheduled}`.

## Distributions & mixes (should look like the real world)

- **Appointment lifecycle.** completed 0.68 / no_show 0.12 / cancelled 0.12 / scheduled 0.08.
  See `scenarios/no-show-rate.md`.
- **Time of day.** Appointments cluster around late morning (peak ≈ 11:00, spread ≈ 3h).
- **Lead time.** Lognormal, median ≈ 10 days, right-skewed out to the 120-day cap.

## Deliberate simplifications (intentional — do not "fix")

- **Placeholder scope.** Only `providers`, `patients` and `appointments` exist today. Open
  appointment slots, realised `visits`, and `invoices` are the intended expansion — the
  slot → booking → visit → billing workflow is not modelled yet.
- **No per-patient booking history shape.** Appointments draw patients uniformly; there is
  no notion of frequent vs. one-off patients, and no correlation between lead time and
  no-show yet (a natural future scenario once visits land).
- **No provider capacity.** Nothing enforces one appointment per provider per time slot;
  double-bookings are possible.
