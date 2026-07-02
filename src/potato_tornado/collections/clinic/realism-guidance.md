# Realism guidance — clinic

What "realistic" means for this collection: the plausibility rules a reviewer (human or
Claude) checks freshly generated data against. This is the **review rubric**, distinct from
`scenarios/` (the intended teachable signals). Scenarios say what a student should *find*;
this doc says what the data must never get *wrong*, and which departures from reality are
deliberate so a reviewer doesn't "fix" them.

Magnitudes here must track the generators in `tables/` — if you retune a distribution,
update the matching line below in the same change.

## Invariants (must always hold)

- **Referential integrity.** Every `slots.provider_id ∈ providers`;
  `appointments.patient_id ∈ patients`; `appointments.slot_id ∈ slots` and points at a
  `is_booked = true` slot; `visits.appointment_id ∈ appointments`;
  `invoices.visit_id ∈ visits`.
- **One appointment per slot (no double-booking).** `appointments.slot_id` is unique, and
  the set of booked appointment slots equals exactly the `is_booked = true` slots. A slot's
  provider and time flow through to the appointment, so `appointments.provider_id` /
  `scheduled_at` match the booked slot.
- **Visits only for completed appointments.** A `visits` row exists iff its appointment has
  `status = 'completed'`. No-shows and cancellations never produce a visit; every visit has
  exactly one invoice.
- **Booking arithmetic.** `lead_days ∈ [0, 120]`; `slots.slot_at` (and thus
  `appointments.scheduled_at`) falls inside the config `[start_date, end_date)` window, on a
  weekday.
- **Status is one of the lifecycle values.** `appointments.status ∈ {completed, no_show,
  cancelled, scheduled}`.
- **Billing identity.** On every invoice `charge = amount_paid + balance` (cents), with
  `0 ≤ amount_paid ≤ charge`; `status = 'paid'` iff `balance = 0`, else `'outstanding'`.
- **Duration positivity.** `visits.actual_minutes ≥ 5`.

## Distributions & mixes (should look like the real world)

- **Appointment lifecycle.** completed ≈ 0.68 / no_show ≈ 0.12 / cancelled ≈ 0.12 /
  scheduled ≈ 0.08 (marginal). See `scenarios/no-show-rate.md`.
- **No-show vs. lead time.** No-show probability rises with `lead_days` — ≈ 9–10% under 15
  days up to ≈ 22% at 45+ days — while the marginal stays ≈ 12%. See
  `scenarios/no-show-rises-with-lead-time.md`.
- **No-show vs. visit type.** Independent of lead time, no-show probability also shifts by
  `visit_type`: New Patient ≈ 18% (highest), Annual Physical / Telehealth ≈ 9% (lowest),
  Follow-up / Chronic Care / Minor Procedure ≈ 12%. See `scenarios/no-show-rate.md`.
- **Slot utilisation.** ≈ 71% of slots booked overall; per-provider ≈ 49%–90%. See
  `scenarios/provider-utilisation.md`.
- **Visit-type mix.** Follow-up 0.30 / Chronic Care 0.20 / Annual Physical 0.18 / New Patient
  0.12 / Telehealth 0.12 / Minor Procedure 0.08.
- **Duration efficiency.** Mean `actual / scheduled` minutes by type ≈ 0.95 (Telehealth) up
  to ≈ 1.20 (Minor Procedure). See `scenarios/procedure-efficiency.md`.
- **Payer mix & AR.** Commercial 0.38 / Medicare 0.32 / Medicaid 0.18 / Self-pay 0.12; ≈ 82%
  of invoices paid in full; self-pay ≈ 12% of invoices but ≈ 51% of outstanding balance. See
  `scenarios/revenue-and-ar.md`.
- **Time of day.** Appointments cluster around late morning (peak ≈ 11:00, spread ≈ 3h).
- **Lead time.** Lognormal, median ≈ 10 days, right-skewed out to the 120-day cap.

## Deliberate simplifications (intentional — do not "fix")

- **Slots are independent draws, not a fixed grid.** Each slot gets a random weekday and a
  clustered time rather than a rigid 30-minute template, so slot times don't line up on the
  clock. This still yields one-appointment-per-slot and no double-booking; it just isn't a
  literal calendar.
- **`scheduled` status is a flat 8% draw, not date-derived.** An appointment marked
  `scheduled` (still on the books) is chosen by probability, not by comparing its slot date to
  "today" — the dataset has a fixed window and no wall-clock notion of now.
- **Patients book uniformly.** Appointments draw patients uniformly; there is no
  frequent-vs-one-off patient shape and no per-patient no-show history (a natural future
  scenario).
- **No cross-provider referral or specialty routing.** Visit type is independent of the
  booked provider's specialty; nothing routes a dermatology visit to a dermatologist.
- **No claim-adjustment detail.** Billing collapses the payer process into a single
  paid-in-full-or-partial outcome — no line items, adjustments, denials, or resubmission.
