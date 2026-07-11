# clinic — field-enrichment TODO

Candidate columns to add to the existing `clinic` tables for analytics richness. Ordered
quick wins first (realism enrichment), then high-leverage items (each unlocks an analysis
domain; scenario-bearing ones go through `/scenario:draft-or-propose`, not the realism
command).

For each: add the column in the relevant `tables/` builder with deterministic draws
(`ctx.dist` / `ctx.rng` / `ctx.entities`, name-keyed child streams — don't reorder existing
draws), then reconcile `realism-guidance.md` and pin tests. See collections/CLAUDE.md.

Context: an outpatient workflow — `providers` publish `slots`, `patients` book them
(`appointments`, with a lead-time-driven no-show), completed bookings become `visits` (with
duration overrun), each billed on an `invoices` row (with a self-pay-concentrated AR). Existing
covariates: `providers.specialty`, `appointments.visit_type` / `lead_days` / `status`,
`invoices.payer`. Gaps: **no patient demographics or clinical detail, no provider depth beyond
specialty, no booking-channel / reminder funnel, and billing collapses the payer process into
one row** — so no-shows and AR can't be attributed to patient type, and the clinical mix is
invisible. The additions below close those gaps.

## Quick wins (realism enrichment)

- [x] **`patients.age_band`** (`Utf8`) — `ctx.dist.choice` over {peds, 18-40, 41-65, 65+}.
      Unlocks: no-show / visit-type slicing by age.
- [x] **`patients.insurance_type`** (`Utf8`) — a *patient-level* coverage band
      {commercial, medicare, medicaid, self_pay} weighted; distinct from the per-visit
      `invoices.payer`. Unlocks: payer-mix demographics; a covariate for AR.
- [x] **`providers.years_experience`** (`Int64`) — `ctx.dist.integers(1, 35)`. Unlocks:
      seniority slicing (overrun / panel by tenure).
- [x] **`slots.telehealth_flag`** (`Boolean`) — `ctx.dist.bernoulli`. Unlocks: modality mix
      (in-person vs. virtual); a plausible no-show covariate.
- [x] **`appointments.booking_channel`** (`Utf8`) — {phone, portal, walk_in, referral}.
      Unlocks: booking-funnel analysis.
- [x] **`invoices.days_to_pay`** (`Int64`, nullable until paid) — derivable from a payment date
      draw. Unlocks: AR aging (days-sales-outstanding) beyond the current `balance`/`status`.

## High-leverage additions

### 1. `appointments.reminder_sent`
- [x] Whether a reminder was sent (`Boolean`), plus optional `reminder_channel` (sms/email/none).
- **Unlocks:** the reminder→attendance funnel — the single most actionable no-show lever.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: reminded
  appointments no-show materially less (interacts with the existing lead-time gradient). Name
  it; don't plant it here.
- Shipped **flat** (`reminder_sent` ≈ 0.70, `reminder_channel` {sms, email} non-null iff sent);
  NO reminder→no-show effect — that signal is deferred to the scenario workflow.

### 2. `visits.diagnosis_category`
- [x] A coarse clinical category (`Utf8`: preventive / acute / chronic_followup / procedure),
      keyed to `visit_type`.
- **Unlocks:** clinical-mix analysis; a covariate for duration overrun and follow-up.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: overrun
  concentrates in one category (procedures run long) — a deeper cut of the existing
  duration-overrun scenario.
- Shipped **flat** (≈ 0.25/0.40/0.25/0.10) and **independent of `visit_type`** (no overrun
  concentration planted); the concentration signal is deferred to the scenario workflow.

### 3. `patients.chronic_flag` / risk score
- [x] A chronic-condition flag (`Boolean`) or `risk_score` (`Float64`), correlated with age.
- **Unlocks:** utilization analysis — do chronic patients book/visit more?
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: a small
  high-risk patient minority drives a disproportionate visit share (a concentration signal).
- Shipped **flat** (chronic_flag ≈ 0.22, risk_score ∈ [0,1]; independent of age_band and visit
  counts); the concentration signal is deferred to the scenario workflow.

### 4. `invoices.adjustment_amount` + denial detail
- [x] Split the payer process: `adjustment_amount` (`Float64`, contractual write-down) and a
      `denied_amount` / `claim_status`, so `charge → allowed → paid → patient_balance` is
      visible rather than collapsed.
- **Unlocks:** the payer adjudication funnel — directly addresses the standing realism note
  that billing collapses the payer process into one row.
- **Class:** **scenario-bearing** → `/scenario:draft-or-propose`. Candidate signal: denial /
  adjustment rate varies by `payer` (Medicaid writes down more) — attributes the AR.
- Shipped **flat** (adjustment ≈ 85% @ ≈ 14% of charge; denial ≈ 8% @ ≈ 25%; `claim_status ∈
  {adjusted, clean, denied}`), **independent of `payer`** and preserving `charge = amount_paid +
  balance`; the payer-varying denial rate is deferred to the scenario workflow.

### 5. `providers.panel_size`
- [x] Empanelled patient count (`Int64`), a provider capacity attribute.
- **Unlocks:** utilization denominator — visits per panel, provider load.
- **Class:** realism enrichment.

## Open realism items to investigate

Too-synthetic / drift candidates for `/data-collection:review-edit-regen-for-realism`
(existing data to investigate, not new fields). The realism-log records the *runs*; these are
the *open* items.

- [ ] **Slots are independent draws, not a grid.** Each slot gets a random weekday/time rather
      than a provider's fixed daily schedule — a provider's day won't look like a real clinic
      template. Candidate to move to a per-provider grid.
- [ ] **`scheduled` status is a flat 8% draw, not date-derived.** Future-dated appointments
      aren't specifically the still-scheduled ones — check whether the status×date cross-tab
      reads wrong.
- [ ] **No per-patient no-show history.** No-show depends on lead time only; there's no repeat
      no-show behaviour by patient. Flag only if per-patient autocorrelation is expected.
- [x] **Billing collapses the payer process into one row.** Addressed by the flat
      `adjustment_amount` / `denied_amount` / `claim_status` split (item 4 above); the funnel is
      now visible. The *payer-varying* denial rate remains a deferred scenario.

## When the list is done

- [ ] **Revise `realism-guidance.md`.** After the fields above land, reconcile the realism
      rubric and invariant tests with the new columns (new dimensions to slice by, new
      invariants — e.g. `days_to_pay ≥ 0` and null iff unpaid, `adjustment_amount ≤ charge`,
      `diagnosis_category` consistent with `visit_type`). Run
      `/data-collection:review-edit-regen-for-realism` for this collection.
