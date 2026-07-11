"""Tests for the labor collection.

These pin the realism invariants from ``realism-guidance.md`` (referential
integrity, temporal ordering, arithmetic identities, non-negativity) — the rules
that must hold regardless of any teaching signal. Subset-signal magnitudes live in
``test_scenarios.py``.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from potato_tornado.collections.labor.constants import (
    BILLING_TYPES,
    ENABLING_DEPARTMENTS,
    HIRE_SOURCES,
    INDUSTRIES,
    LOCATIONS,
    PROJECT_PRIORITIES,
    ROLES,
    SKILLS_BY_DEPARTMENT,
    WORK_MODES,
)
from potato_tornado.core.config import GenerationConfig
from potato_tornado.runner import generate


@pytest.fixture(scope="module")
def labor() -> dict[str, pl.DataFrame]:
    return generate("labor", GenerationConfig(seed=13, scale=0.3))


def test_assignment_employee_ids_reference_employees(labor: dict[str, pl.DataFrame]) -> None:
    emp_ids = set(labor["employees"]["employee_id"].to_list())
    assert set(labor["assignments"]["employee_id"].to_list()) <= emp_ids


def test_assignment_shift_ids_reference_shifts(labor: dict[str, pl.DataFrame]) -> None:
    shift_ids = set(labor["shifts"]["shift_id"].to_list())
    assert set(labor["assignments"]["shift_id"].to_list()) <= shift_ids


def test_time_entries_are_one_to_one_with_assignments(labor: dict[str, pl.DataFrame]) -> None:
    assert labor["time_entries"].height == labor["assignments"].height


def test_assignments_only_roster_employed_staff(labor: dict[str, pl.DataFrame]) -> None:
    # An employee is rostered onto a shift only while employed: on/after hire and
    # strictly before termination (when they left).
    joined = (
        labor["assignments"]
        .join(
            labor["employees"].select("employee_id", "hire_date", "termination_date"),
            on="employee_id",
        )
        .join(labor["shifts"].select("shift_id", "planned_start"), on="shift_id")
        .with_columns(pl.col("planned_start").dt.date().alias("shift_date"))
    )
    invalid = joined.filter(
        (pl.col("shift_date") < pl.col("hire_date"))
        | (
            pl.col("termination_date").is_not_null()
            & (pl.col("shift_date") >= pl.col("termination_date"))
        )
    )
    assert invalid.height == 0


def test_assigned_at_is_before_shift_and_after_hire(labor: dict[str, pl.DataFrame]) -> None:
    # The roster is published before the shift starts and never before the employee
    # was hired.
    joined = (
        labor["assignments"]
        .join(labor["shifts"].select("shift_id", "planned_start"), on="shift_id")
        .join(labor["employees"].select("employee_id", "hire_date"), on="employee_id")
    )
    out_of_band = joined.filter(
        (pl.col("assigned_at") > pl.col("planned_start"))
        | (pl.col("assigned_at").dt.date() < pl.col("hire_date"))
    )
    assert out_of_band.height == 0


def test_rostering_stays_within_department(labor: dict[str, pl.DataFrame]) -> None:
    cross_dept = (
        labor["assignments"]
        .join(labor["employees"].select(["employee_id", "department_id"]), on="employee_id")
        .join(
            labor["shifts"]
            .select(["shift_id", "department_id"])
            .rename({"department_id": "shift_department_id"}),
            on="shift_id",
        )
        .filter(pl.col("department_id") != pl.col("shift_department_id"))
    )
    assert cross_dept.height == 0


def test_no_show_entries_have_null_clock_in(labor: dict[str, pl.DataFrame]) -> None:
    no_shows = labor["time_entries"].filter(labor["time_entries"]["no_show"])
    assert no_shows["clock_in"].null_count() == no_shows.height


def test_no_show_entries_have_null_worked_hours(labor: dict[str, pl.DataFrame]) -> None:
    no_shows = labor["time_entries"].filter(labor["time_entries"]["no_show"])
    assert no_shows["worked_hours"].null_count() == no_shows.height


def test_worked_entries_have_populated_clocks(labor: dict[str, pl.DataFrame]) -> None:
    worked = labor["time_entries"].filter(~labor["time_entries"]["no_show"])
    populated = worked.filter(
        pl.col("clock_in").is_not_null()
        & pl.col("clock_out").is_not_null()
        & pl.col("worked_hours").is_not_null()
    )
    assert populated.height == worked.height


def test_clock_out_is_after_clock_in(labor: dict[str, pl.DataFrame]) -> None:
    worked = labor["time_entries"].filter(~labor["time_entries"]["no_show"])
    assert worked.filter(pl.col("clock_out") <= pl.col("clock_in")).height == 0


def test_worked_hours_never_below_planned(labor: dict[str, pl.DataFrame]) -> None:
    worked = labor["time_entries"].filter(~labor["time_entries"]["no_show"])
    assert worked.filter(pl.col("worked_hours") < pl.col("planned_hours")).height == 0


def test_planned_end_matches_start_plus_hours(labor: dict[str, pl.DataFrame]) -> None:
    shifts = labor["shifts"]
    mismatched = shifts.filter(
        (pl.col("planned_end") - pl.col("planned_start")).dt.total_hours()
        != pl.col("planned_hours")
    )
    assert mismatched.height == 0


def test_planned_hours_are_from_the_allowed_set(labor: dict[str, pl.DataFrame]) -> None:
    assert set(labor["shifts"]["planned_hours"].unique().to_list()) <= {8, 10, 12}


def test_required_headcount_within_bounds(labor: dict[str, pl.DataFrame]) -> None:
    out_of_range = labor["shifts"].filter(
        (pl.col("required_headcount") < 2) | (pl.col("required_headcount") > 8)
    )
    assert out_of_range.height == 0


def test_hourly_rate_is_positive(labor: dict[str, pl.DataFrame]) -> None:
    assert labor["employees"].filter(pl.col("hourly_rate") <= 0).height == 0


def test_hire_dates_are_within_window(labor: dict[str, pl.DataFrame]) -> None:
    # Fixture uses the default window, whose exclusive upper bound is 2025-01-01.
    assert labor["employees"].filter(pl.col("hire_date") >= date(2025, 1, 1)).height == 0


def test_termination_is_after_hire_when_present(labor: dict[str, pl.DataFrame]) -> None:
    terminated = labor["employees"].filter(pl.col("termination_date").is_not_null())
    assert terminated.filter(pl.col("termination_date") <= pl.col("hire_date")).height == 0


def test_termination_dates_stay_before_window_end(labor: dict[str, pl.DataFrame]) -> None:
    # A leaver's date is kept strictly before the window's exclusive upper bound.
    assert labor["employees"].filter(pl.col("termination_date") >= date(2025, 1, 1)).height == 0


def test_standard_bill_rate_exceeds_cost(labor: dict[str, pl.DataFrame]) -> None:
    assert (
        labor["employees"].filter(pl.col("standard_bill_rate") <= pl.col("hourly_rate")).height == 0
    )


def test_weekly_capacity_matches_employment_type(labor: dict[str, pl.DataFrame]) -> None:
    expected = {"full_time": 40, "part_time": 20, "contractor": 40}
    mismatched = labor["employees"].filter(
        pl.col("weekly_capacity_hours")
        != pl.col("employment_type").replace_strict(expected, return_dtype=pl.Int64)
    )
    assert mismatched.height == 0


@pytest.mark.parametrize(
    ("column", "allowed"),
    [
        ("industry", set(INDUSTRIES)),
        ("billing_type", set(BILLING_TYPES)),
        ("priority", set(PROJECT_PRIORITIES)),
    ],
)
def test_project_dimensions_are_from_the_catalog(
    labor: dict[str, pl.DataFrame], column: str, allowed: set[str]
) -> None:
    assert set(labor["projects"][column].to_list()) <= allowed


def test_member_bill_rate_never_exceeds_standard_rate(labor: dict[str, pl.DataFrame]) -> None:
    joined = labor["project_members"].join(
        labor["employees"].select("employee_id", "standard_bill_rate"), on="employee_id"
    )
    out_of_band = joined.filter(
        (pl.col("bill_rate") <= 0) | (pl.col("bill_rate") > pl.col("standard_bill_rate"))
    )
    assert out_of_band.height == 0


def test_member_bill_rate_is_set_exactly_for_billable_members(
    labor: dict[str, pl.DataFrame],
) -> None:
    joined = labor["project_members"].join(
        labor["employees"].select("employee_id", "is_billable"), on="employee_id"
    )
    # bill_rate is populated iff the member is client-billable; null otherwise.
    inconsistent = joined.filter(pl.col("is_billable") == pl.col("bill_rate").is_null())
    assert inconsistent.height == 0


def test_member_billed_hours_is_set_exactly_for_billable_members(
    labor: dict[str, pl.DataFrame],
) -> None:
    joined = labor["project_members"].join(
        labor["employees"].select("employee_id", "is_billable"), on="employee_id"
    )
    # billed_hours is populated iff the member is client-billable; null otherwise.
    inconsistent = joined.filter(pl.col("is_billable") == pl.col("billed_hours").is_null())
    assert inconsistent.height == 0


def test_practice_type_matches_enabling_set(labor: dict[str, pl.DataFrame]) -> None:
    expected = labor["departments"].select(
        pl.when(pl.col("name").is_in(list(ENABLING_DEPARTMENTS)))
        .then(pl.lit("enabling"))
        .otherwise(pl.lit("delivery"))
        .alias("expected")
    )["expected"]
    mismatched = labor["departments"].filter(labor["departments"]["practice_type"] != expected)
    assert mismatched.height == 0


def test_primary_skill_belongs_to_employee_department(labor: dict[str, pl.DataFrame]) -> None:
    valid = {(dept, skill) for dept, skills in SKILLS_BY_DEPARTMENT.items() for skill in skills}
    joined = labor["employees"].join(
        labor["departments"].select("department_id", "name"), on="department_id"
    )
    pairs = set(zip(joined["name"].to_list(), joined["primary_skill"].to_list(), strict=True))
    assert pairs <= valid


def test_work_mode_is_from_the_catalog(labor: dict[str, pl.DataFrame]) -> None:
    assert set(labor["employees"]["work_mode"].to_list()) <= set(WORK_MODES)


def test_hire_source_is_from_the_catalog(labor: dict[str, pl.DataFrame]) -> None:
    assert set(labor["employees"]["hire_source"].to_list()) <= set(HIRE_SOURCES)


def test_prior_experience_years_is_non_negative(labor: dict[str, pl.DataFrame]) -> None:
    assert labor["employees"].filter(pl.col("prior_experience_years") < 0).height == 0


def test_target_utilization_is_set_exactly_for_billable_staff(
    labor: dict[str, pl.DataFrame],
) -> None:
    employees = labor["employees"]
    inconsistent = employees.filter(
        pl.col("is_billable") == pl.col("target_utilization_pct").is_null()
    )
    assert inconsistent.height == 0


def test_no_show_entries_are_never_billable(labor: dict[str, pl.DataFrame]) -> None:
    entries = labor["time_entries"]
    assert entries.filter(pl.col("no_show") & pl.col("billable")).height == 0


@pytest.mark.parametrize("column", ["approval_status", "submitted_late", "entry_source"])
def test_timesheet_fields_are_set_exactly_for_worked_entries(
    labor: dict[str, pl.DataFrame], column: str
) -> None:
    inconsistent = labor["time_entries"].filter(pl.col("no_show") != pl.col(column).is_null())
    assert inconsistent.height == 0


def test_approval_status_is_from_the_allowed_set(labor: dict[str, pl.DataFrame]) -> None:
    worked = labor["time_entries"].filter(~pl.col("no_show"))
    allowed = {"approved", "pending", "rejected"}
    assert set(worked["approval_status"].unique().to_list()) <= allowed


def test_project_budgets_are_positive(labor: dict[str, pl.DataFrame]) -> None:
    assert (
        labor["projects"]
        .filter((pl.col("budget_hours") <= 0) | (pl.col("budget_amount") <= 0))
        .height
        == 0
    )


@pytest.mark.parametrize("column", ["actual_end_date", "client_satisfaction"])
def test_project_outcome_fields_are_set_exactly_for_completed(
    labor: dict[str, pl.DataFrame], column: str
) -> None:
    inconsistent = labor["projects"].filter(
        (pl.col("status") == "completed") == pl.col(column).is_null()
    )
    assert inconsistent.height == 0


def test_client_satisfaction_is_within_scale(labor: dict[str, pl.DataFrame]) -> None:
    scored = labor["projects"].filter(pl.col("client_satisfaction").is_not_null())
    out_of_range = scored.filter(
        (pl.col("client_satisfaction") < 1) | (pl.col("client_satisfaction") > 5)
    )
    assert out_of_range.height == 0


def test_manager_ids_reference_employees(labor: dict[str, pl.DataFrame]) -> None:
    employees = labor["employees"]
    emp_ids = set(employees["employee_id"].to_list())
    managers = employees.filter(pl.col("manager_id").is_not_null())["manager_id"].to_list()
    assert set(managers) <= emp_ids


def test_no_employee_is_their_own_manager(labor: dict[str, pl.DataFrame]) -> None:
    assert labor["employees"].filter(pl.col("manager_id") == pl.col("employee_id")).height == 0


def test_manager_is_a_senior_colleague_in_same_department(
    labor: dict[str, pl.DataFrame],
) -> None:
    rung = {role: i for i, role in enumerate(ROLES)}
    employees = labor["employees"].with_columns(
        pl.col("role").replace_strict(rung, return_dtype=pl.Int32).alias("rung")
    )
    joined = employees.join(
        employees.select(
            pl.col("employee_id").alias("manager_id"),
            pl.col("department_id").alias("manager_department_id"),
            pl.col("rung").alias("manager_rung"),
        ),
        on="manager_id",
        how="inner",
    )
    misplaced = joined.filter(
        (pl.col("department_id") != pl.col("manager_department_id"))
        | (pl.col("manager_rung") <= pl.col("rung"))
    )
    assert misplaced.height == 0


def test_scale_increases_employee_count() -> None:
    small = generate("labor", GenerationConfig(seed=1, scale=0.2))["employees"].height
    large = generate("labor", GenerationConfig(seed=1, scale=1.0))["employees"].height
    assert large > small


def test_employee_locations_are_from_the_catalog(labor: dict[str, pl.DataFrame]) -> None:
    assert set(labor["employees"]["location_city"].to_list()) <= set(LOCATIONS)


def test_project_locations_are_from_the_catalog(labor: dict[str, pl.DataFrame]) -> None:
    assert set(labor["projects"]["location_city"].to_list()) <= set(LOCATIONS)


def test_project_department_ids_reference_departments(labor: dict[str, pl.DataFrame]) -> None:
    dept_ids = set(labor["departments"]["department_id"].to_list())
    assert set(labor["projects"]["department_id"].to_list()) <= dept_ids


def test_project_client_ids_reference_clients(labor: dict[str, pl.DataFrame]) -> None:
    client_ids = set(labor["clients"]["client_id"].to_list())
    assert set(labor["projects"]["client_id"].to_list()) <= client_ids


def test_engagement_manager_ids_reference_employees(labor: dict[str, pl.DataFrame]) -> None:
    emp_ids = set(labor["employees"]["employee_id"].to_list())
    assert set(labor["projects"]["engagement_manager_id"].to_list()) <= emp_ids


def test_project_target_end_is_after_start(labor: dict[str, pl.DataFrame]) -> None:
    assert labor["projects"].filter(pl.col("target_end_date") <= pl.col("start_date")).height == 0


def test_completed_projects_end_within_window(labor: dict[str, pl.DataFrame]) -> None:
    # actual_end_date is right-censored at the exclusive window end (2025-01-01 on
    # the fixture): a completion that would land on/after it is unobservable at the
    # snapshot, so the project is downgraded to active with a null actual_end_date.
    # No completed project therefore ends on/after the window end.
    assert (
        labor["projects"]
        .filter((pl.col("status") == "completed") & (pl.col("actual_end_date") >= date(2025, 1, 1)))
        .height
        == 0
    )


def test_contract_signed_date_is_before_start_and_in_window(
    labor: dict[str, pl.DataFrame],
) -> None:
    # The sale closes before the project starts, and never predates the window
    # (2022-01-01 is the fixture's inclusive lower bound).
    out_of_band = labor["projects"].filter(
        (pl.col("contract_signed_date") > pl.col("start_date"))
        | (pl.col("contract_signed_date") < date(2022, 1, 1))
    )
    assert out_of_band.height == 0


def test_member_employee_ids_reference_employees(labor: dict[str, pl.DataFrame]) -> None:
    emp_ids = set(labor["employees"]["employee_id"].to_list())
    assert set(labor["project_members"]["employee_id"].to_list()) <= emp_ids


def test_member_project_ids_reference_projects(labor: dict[str, pl.DataFrame]) -> None:
    project_ids = set(labor["projects"]["project_id"].to_list())
    assert set(labor["project_members"]["project_id"].to_list()) <= project_ids


def test_membership_is_unique_per_project_and_employee(labor: dict[str, pl.DataFrame]) -> None:
    members = labor["project_members"]
    assert members.select(["project_id", "employee_id"]).n_unique() == members.height


def test_every_project_has_exactly_one_lead(labor: dict[str, pl.DataFrame]) -> None:
    leads = labor["project_members"].filter(pl.col("role_on_project") == "lead")
    projects = labor["projects"]
    assert leads.height == leads["project_id"].n_unique() == projects.height


def test_allocation_pct_is_from_the_allowed_set(labor: dict[str, pl.DataFrame]) -> None:
    assert set(labor["project_members"]["allocation_pct"].unique().to_list()) <= {25, 50, 75, 100}


def test_member_roll_on_is_within_project_window(labor: dict[str, pl.DataFrame]) -> None:
    joined = labor["project_members"].join(
        labor["projects"].select("project_id", "start_date", "target_end_date"), on="project_id"
    )
    out_of_window = joined.filter(
        pl.col("rolled_on_date").is_null()
        | (pl.col("rolled_on_date") < pl.col("start_date"))
        | (pl.col("rolled_on_date") >= pl.col("target_end_date"))
    )
    assert out_of_window.height == 0


def test_member_roll_off_is_set_when_completed_or_member_terminated(
    labor: dict[str, pl.DataFrame],
) -> None:
    joined = (
        labor["project_members"]
        .join(labor["projects"].select("project_id", "status", "target_end_date"), on="project_id")
        .join(labor["employees"].select("employee_id", "termination_date"), on="employee_id")
    )
    # rolled_off closes iff the project completed OR the member left the firm on/before
    # the project's target end (they rolled off when they left, even on an open project).
    should_close = (pl.col("status") == "completed") | (
        pl.col("termination_date").is_not_null()
        & (pl.col("termination_date") <= pl.col("target_end_date"))
    )
    inconsistent = joined.filter(should_close == pl.col("rolled_off_date").is_null())
    assert inconsistent.height == 0


def test_member_roll_off_falls_after_roll_on_and_within_window(
    labor: dict[str, pl.DataFrame],
) -> None:
    joined = labor["project_members"].join(
        labor["projects"].select("project_id", "target_end_date"), on="project_id"
    )
    present = joined.filter(pl.col("rolled_off_date").is_not_null())
    out_of_band = present.filter(
        (pl.col("rolled_off_date") <= pl.col("rolled_on_date"))
        | (pl.col("rolled_off_date") > pl.col("target_end_date"))
    )
    assert out_of_band.height == 0


def test_member_roll_dates_respect_employment(labor: dict[str, pl.DataFrame]) -> None:
    # A member never rolls on before they were hired, and a member who left the firm
    # never rolls off after their termination date.
    joined = labor["project_members"].join(
        labor["employees"].select("employee_id", "hire_date", "termination_date"),
        on="employee_id",
    )
    invalid = joined.filter(
        (pl.col("rolled_on_date") < pl.col("hire_date"))
        | (
            pl.col("termination_date").is_not_null()
            & pl.col("rolled_off_date").is_not_null()
            & (pl.col("rolled_off_date") > pl.col("termination_date"))
        )
    )
    assert invalid.height == 0


def test_project_lead_is_the_most_senior_member(labor: dict[str, pl.DataFrame]) -> None:
    rung = {role: i for i, role in enumerate(ROLES)}
    members = (
        labor["project_members"]
        .join(labor["employees"].select("employee_id", "role"), on="employee_id")
        .with_columns(pl.col("role").replace_strict(rung, return_dtype=pl.Int32).alias("rung"))
    )
    per_project = members.group_by("project_id").agg(
        pl.col("rung").filter(pl.col("role_on_project") == "lead").max().alias("lead_rung"),
        pl.col("rung").max().alias("max_rung"),
    )
    assert per_project.filter(pl.col("lead_rung") != pl.col("max_rung")).height == 0


def test_employee_skill_employee_ids_reference_employees(labor: dict[str, pl.DataFrame]) -> None:
    emp_ids = set(labor["employees"]["employee_id"].to_list())
    assert set(labor["employee_skills"]["employee_id"].to_list()) <= emp_ids


def test_performance_review_ratings_are_within_scale(labor: dict[str, pl.DataFrame]) -> None:
    reviews = labor["performance_reviews"]
    assert reviews.filter((pl.col("rating") < 1) | (pl.col("rating") > 5)).height == 0


def test_expense_project_ids_reference_projects(labor: dict[str, pl.DataFrame]) -> None:
    project_ids = set(labor["projects"]["project_id"].to_list())
    assert set(labor["expenses"]["project_id"].to_list()) <= project_ids


def test_time_off_spells_sit_within_employment(labor: dict[str, pl.DataFrame]) -> None:
    # A leave spell starts on/after hire, ends on/after it starts, and never on/after
    # the employee left the firm.
    joined = labor["time_off"].join(
        labor["employees"].select("employee_id", "hire_date", "termination_date"),
        on="employee_id",
    )
    invalid = joined.filter(
        (pl.col("start_date") < pl.col("hire_date"))
        | (pl.col("end_date") < pl.col("start_date"))
        | (
            pl.col("termination_date").is_not_null()
            & (pl.col("end_date") >= pl.col("termination_date"))
        )
    )
    assert invalid.height == 0
