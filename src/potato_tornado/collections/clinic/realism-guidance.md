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
- **Provider tenure bounds.** `providers.years_experience ∈ [1, 35]` (uniform integer draw).
- **Reminder channel presence.** `appointments.reminder_channel` is non-null iff
  `appointments.reminder_sent` is true (a sent reminder always has a channel; an unsent one never
  does).
- **Days-to-pay presence.** `invoices.days_to_pay` is non-null iff `invoices.status = 'paid'`
  (an outstanding invoice has no payment latency yet); when present it is an integer in `[3, 90]`.

## Distributions & mixes (should look like the real world)

- **Appointment lifecycle.** completed ≈ 0.68 / no_show ≈ 0.12 / cancelled ≈ 0.12 /
  scheduled ≈ 0.08 (marginal). See `scenarios/no-show-rate.md`.
- **No-show vs. lead time.** No-show probability rises with `lead_days` — ≈ 9–10% under 15
  days up to ≈ 22% at 45+ days — while the marginal stays ≈ 12%. See
  `scenarios/no-show-rises-with-lead-time.md`.
- **No-show vs. visit type.** Independent of lead time, no-show probability also shifts by
  `visit_type`: New Patient ≈ 20–23% (highest), Annual Physical / Minor Procedure ≈ 8–9%
  (lowest), Follow-up / Chronic Care / Telehealth ≈ 10%. See `scenarios/no-show-rate.md`.
- **Slot utilisation.** ≈ 68–70% of slots booked overall, but keyed to specialty (not random
  per provider): Dermatology 0.88 / Cardiology 0.82 / Orthopedics 0.74 / Internal Medicine
  0.64 / Family Medicine 0.56 / Pediatrics 0.48, ±~4% per-provider jitter. Demand-heavy
  specialties run near-full; others carry spare capacity. See
  `scenarios/provider-utilisation.md`.
- **Visit-type mix.** Clinic-wide ≈ Follow-up 0.32 / Chronic Care 0.18 / Annual Physical 0.16
  / New Patient 0.13 / Minor Procedure 0.09 / Telehealth 0.10 — the appointment-weighted
  average of the per-specialty profiles, within a couple points of the base `VISIT_TYPES`
  weights (drifts slightly with the random specialty roster).
- **Visit mix by specialty.** Visit type is conditioned on the provider's specialty:
  Dermatology/Orthopedics Minor Procedure ≈ 21–27% (vs ≈ 9% overall, ≈ 0% for Pediatrics);
  Pediatrics New Patient ≈ 22%; Internal Medicine/Cardiology Chronic Care ≈ 32–43%. See
  `scenarios/visit-mix-by-specialty.md`.
- **Duration efficiency.** Mean `actual / scheduled` minutes by type ≈ 0.95 (Telehealth) up
  to ≈ 1.20 (Minor Procedure). See `scenarios/procedure-efficiency.md`.
- **Diagnosis category.** `visits.diagnosis_category ∈ {preventive, acute, chronic_followup,
  procedure}` at ≈ 0.25 / 0.40 / 0.25 / 0.10 — a flat categorical drawn **independently of
  `visit_type`** (and thus of the duration-overrun bias), so no category runs systematically long.
- **Payer mix & AR.** Commercial 0.38 / Medicare 0.32 / Medicaid 0.18 / Self-pay 0.12; ≈ 82%
  of invoices paid in full; self-pay ≈ 12% of invoices but ≈ 51% of outstanding balance. See
  `scenarios/revenue-and-ar.md`.
- **Days to pay.** On paid invoices, `invoices.days_to_pay` is a uniform integer in `[3, 90]`
  (mean ≈ 46); null on outstanding invoices. Flat and independent of payer.
- **Claim adjudication.** `invoices.adjustment_amount` (contractual write-down) is present on
  ≈ 85% of claims at ≈ 14% of charge; `invoices.denied_amount` is non-zero on ≈ 8% of claims at
  ≈ 25% of charge; `invoices.claim_status ∈ {adjusted, clean, denied}` (≈ 0.77 / 0.14 / 0.08),
  derived so `denied` iff denied_amount > 0, else `adjusted` iff written down, else `clean`. All
  flat and **independent of `payer`**; `allowed = charge − adjustment_amount − denied_amount ≥ 0`.
- **Charge per visit.** Mean billed charge tracks the visit type's base charge, ≈ $90
  (Telehealth) up to ≈ $340 (Minor Procedure), with mild ±8% variation; Minor Procedure is
  ≈ 9–10% of visits but ≈ 20% of gross charges. See `scenarios/charge-varies-by-procedure.md`.
- **Patient booking concentration.** Patients book with a per-patient lognormal propensity
  (σ ≈ 0.8), so the top decile of patients takes ≈ 31–35% of appointments (top quintile
  ≈ 48–53%) and ≈ 4% never book — far from uniform. See
  `scenarios/frequent-vs-one-off-patients.md`.
- **Seasonality & growth.** Slot days are drawn with a winter-peaking seasonal weight × an
  upward trend, so booked volume peaks in winter (Dec–Feb ≈ 1.3× the Jun–Aug trough) and
  grows ≈ 8%/year across the window. See `scenarios/seasonal-and-growth.md`.
- **Time of day.** Appointments cluster around late morning (peak ≈ 11:00, spread ≈ 3h).
- **Slot modality mix.** `slots.telehealth_flag` true ≈ 18% (flat Bernoulli). This is a property
  of the *slot* (published as virtual) and is independent of the appointment's `visit_type`
  "Telehealth" value — the two telehealth notions are separate and need not coincide.
- **Arrival delay by hour.** Mean `visits.arrival_delay_min` grows with the appointment's
  scheduled hour, from ≈ −2 min early morning to ≈ 11–13 min late afternoon; overall mean
  ≈ 2–3 min. See `scenarios/clinic-runs-late.md`.
- **Booking channel.** `appointments.booking_channel ∈ {phone, portal, walk_in, referral}` at
  ≈ 0.40 / 0.35 / 0.10 / 0.15 (flat categorical, independent of status / lead time / no-show).
- **Appointment reminders.** `appointments.reminder_sent` true ≈ 70% (flat Bernoulli);
  `appointments.reminder_channel ∈ {sms, email}` at ≈ 0.6 / 0.4 **only** where a reminder was
  sent, else null (channel is null iff `reminder_sent` is false — a hard invariant).
- **Lead time.** Lognormal, median ≈ 10 days, right-skewed out to the 120-day cap.
- **Provider capacity attributes.** `providers.years_experience` uniform 1–35 yrs (mean ≈ 18);
  `providers.panel_size` (empanelled patient count) uniform 200–2000 (mean ≈ 1100). Both are
  independent flat draws — no tenure→panel coupling and no specialty tilt.
- **Patient age band.** `patients.age_band ∈ {peds, 18-40, 41-65, 65+}` at ≈ 0.15 / 0.30 / 0.35 /
  0.20 (flat categorical draw, independent of every other patient attribute and of visit counts).
- **Patient insurance type.** `patients.insurance_type ∈ {commercial, medicare, medicaid,
  self_pay}` at ≈ 0.50 / 0.25 / 0.15 / 0.10 — a **patient-level** coverage band, drawn
  independently of the per-visit `invoices.payer` (they are separate axes and need not agree).
- **Patient clinical attributes.** `patients.chronic_flag` true ≈ 22% (Bernoulli);
  `patients.risk_score ∈ [0, 1]`, clamped-normal mean ≈ 0.35, sd ≈ 0.18. Both flat and mutually
  independent.

## Deliberate simplifications (intentional — do not "fix")

- **Slots are independent draws, not a fixed grid.** Each slot gets a random weekday and a
  clustered time rather than a rigid 30-minute template, so slot times don't line up on the
  clock. This still yields one-appointment-per-slot and no double-booking; it just isn't a
  literal calendar.
- **`scheduled` status is a flat 8% draw, not date-derived.** An appointment marked
  `scheduled` (still on the books) is chosen by probability, not by comparing its slot date to
  "today" — the dataset has a fixed window and no wall-clock notion of now.
- **No per-patient no-show history.** No-show probability depends on booking lead time, not on
  a patient's own past attendance — there is no per-patient reliability score. (The
  frequent-vs-one-off *booking* shape is now planted; see the booking-concentration line under
  Distributions & mixes.)
- **No cross-provider referral routing.** Visit type is tilted by the booked provider's
  specialty (see the visit-mix line above), but nothing models a *referral* — a patient
  isn't routed from one provider to another, and specialty is a per-appointment tilt, not a
  care pathway.
- **`days_to_pay` is a synthetic aging draw, not a date subtraction.** The model has no payment
  date to subtract from the service date, so `invoices.days_to_pay` is drawn directly as a
  plausible days-outstanding value on paid invoices — treat it as an aging bucket, not a computed
  latency.
- **Payer adjudication is flat, not payer-varying.** The funnel is now partly visible —
  `invoices.adjustment_amount` (contractual write-down), `invoices.denied_amount`, and
  `invoices.claim_status` expose `charge → allowed → paid → patient_balance` — but every rate is
  a flat draw **independent of `payer`**. There are still no line items or resubmission, and the
  teachable "denial / adjustment rate varies by payer (Medicaid writes down more)" cut is a
  deferred scenario, deliberately *not* planted here.
- **Patient clinical attributes carry no planted signal.** `chronic_flag` / `risk_score` are
  flat, independent draws — deliberately *not* correlated with `age_band`, and high-risk
  patients do *not* concentrate visits. The "small high-risk minority drives a disproportionate
  visit share" concentration is a candidate scenario, left for the scenario workflow to plant.
- **Reminders carry no attendance signal.** `reminder_sent` is a flat 70% draw with *no* effect
  on the no-show rate — reminded and un-reminded appointments no-show identically. The
  "reminded appointments no-show materially less" lift is a candidate scenario, left for the
  scenario workflow to plant.
