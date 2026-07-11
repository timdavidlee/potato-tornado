# Realism log — clinic

The running **log** of realism work on this collection — history, not backlog. Companion to
[`realism-guidance.md`](realism-guidance.md) (the rubric) and [`TODO.md`](TODO.md) (the open
backlog: field-enrichment suggestions + open realism items to investigate). Two entry kinds: a
**realism iteration** is one `/data-collection:review-edit-regen-for-realism` pass (measure
invariants + distributions, sweep for too-synthetic artifacts, fix generators, regenerate,
reconcile the rubric + tests); a **field-enrichment run** is one
`/data-collection:suggest-analytic-fields` pass. Open items live in `TODO.md`, not here.

**Status: Converged** — the slot→booking→visit→billing workflow and its planted signals
(lead-time no-shows, duration overrun, self-pay AR) are in place with a realism rubric; residual
items are documented deliberate simplifications (open items in `TODO.md`). (as of 2026-07-02)

## Realism iterations

- **2026-07-01 — Build + realism docs.** Established the appointment lifecycle
  (completed/no-show/cancelled), the lead-time no-show gradient, per-visit-type duration
  overrun, and the self-pay-concentrated AR, with a realism-guidance rubric. (`b2eeb4e`)

## Field-enrichment runs

- **2026-07-02 — Field-enrichment survey.** Surveyed all six tables and wrote the candidate
  backlog (6 quick wins + 5 high-leverage, several scenario-bearing — incl. a reminder→no-show
  funnel and a payer-adjudication split) to [`TODO.md`](TODO.md). No columns implemented yet —
  the backlog is the open work.
- **2026-07-11 — Field-enrichment implementation (tackle-todos).** Realized backlog columns as
  flat, deterministic draws on new name-keyed child streams (no existing draw shifted; verified
  vs a seed=7/scale=0.3 column-hash baseline). Each column got a single-assert invariant test and
  a reconciled `realism-guidance.md` line. Scenario-bearing columns were shipped flat only (no
  planted signal — those are left for the scenario workflow). Columns shipped:
  - `providers.years_experience` (`Int64`, uniform 1–35).
  - `providers.panel_size` (`Int64`, uniform 200–2000; independent of tenure).
  - `patients.age_band` (`Utf8` {peds, 18-40, 41-65, 65+} @ 0.15/0.30/0.35/0.20).
  - `patients.insurance_type` (`Utf8` {commercial, medicare, medicaid, self_pay} @
    0.50/0.25/0.15/0.10; independent of `invoices.payer`).
  - `patients.chronic_flag` (`Boolean`, ≈ 0.22) + `patients.risk_score` (`Float64`, clamped
    normal in [0,1], mean ≈ 0.35) — flat, no high-risk-concentration signal (deferred to scenario).
  - `slots.telehealth_flag` (`Boolean`, ≈ 0.18; independent of `visit_type`).
  - `appointments.booking_channel` (`Utf8` {phone, portal, walk_in, referral} @
    0.40/0.35/0.10/0.15).
  - `appointments.reminder_sent` (`Boolean`, ≈ 0.70) + `appointments.reminder_channel` (`Utf8`
    {sms, email}, non-null iff sent) — flat, no reminder→no-show signal (deferred to scenario).
  - `visits.diagnosis_category` (`Utf8` {preventive, acute, chronic_followup, procedure} @
    0.25/0.40/0.25/0.10) — independent of `visit_type`, no overrun concentration (deferred to
    scenario).
  - `invoices.days_to_pay` (`Int64` [3,90], null unless `status == 'paid'`) — synthetic aging
    draw (no payment date exists to subtract), independent of payer.
  - `invoices.adjustment_amount` + `invoices.denied_amount` (`Float64`) + `invoices.claim_status`
    (`Utf8` {adjusted ≈ 0.77, clean ≈ 0.14, denied ≈ 0.08}) — a flat `charge → allowed → paid →
    patient_balance` split, independent of payer and preserving `charge = amount_paid + balance`.
    Reconciles the "billing collapses the payer process" simplification; the payer-varying denial
    rate is deferred to the scenario workflow.

Status stays **Converged** — all field-enrichment columns above are flat/deterministic, with no
new too-synthetic risk introduced; the surprising subset signals (reminder→no-show,
overrun-by-category, high-risk visit concentration, payer-varying denial) are explicitly deferred
to the scenario workflow.
