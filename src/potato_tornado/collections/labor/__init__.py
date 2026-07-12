"""Collection: labor assignment and utilization.

Models the workforce of a **technology consulting firm** — organised into practice
areas (Strategy & Advisory, Cybersecurity, Software Engineering, …) — being
scheduled onto shifts and staffed onto projects, and how actual attendance
compares to what was planned. The raw material for utilization and overtime
analysis.

Tables
------
- ``departments``     : cost centres that own shifts and staff.
- ``employees``       : the workforce, tied to a home department and location.
- ``shifts``          : planned shifts with a required headcount and a time window.
- ``assignments``     : employees rostered onto shifts (the plan).
- ``time_entries``    : actual clock-in / clock-out per assignment (the reality),
                        including no-shows, late starts and overtime.
- ``projects``        : cross-functional initiatives, each run from a location.
- ``project_members`` : employees staffed onto projects (many-to-many), with a
                        share working off-site from the project's location.

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.labor.tables import (
    build_assignments,
    build_clients,
    build_departments,
    build_employee_skills,
    build_employees,
    build_expenses,
    build_performance_reviews,
    build_project_members,
    build_projects,
    build_shifts,
    build_time_entries,
    build_time_off,
)
from potato_tornado.core.collection import Collection, TableSpec
from potato_tornado.core.registry import register


def build() -> Collection:
    return Collection(
        name="labor",
        description="Labor assignment and utilization for a technology consulting firm: "
        "staff by practice area, planned shifts, rosters, project staffing, and actual "
        "attendance vs. plan.",
        tables=(
            TableSpec("departments", build_departments, description="Cost centres."),
            TableSpec(
                "employees",
                build_employees,
                depends_on=("departments",),
                description="Workforce with roles, pay rates and home location.",
            ),
            TableSpec(
                "shifts",
                build_shifts,
                depends_on=("departments",),
                description="Planned shifts and required headcount.",
            ),
            TableSpec(
                "assignments",
                build_assignments,
                depends_on=("shifts", "employees"),
                description="Employees rostered onto shifts.",
            ),
            TableSpec(
                "time_entries",
                build_time_entries,
                depends_on=("assignments", "shifts", "departments"),
                description="Actual clock-in/out, no-shows and overtime.",
            ),
            TableSpec("clients", build_clients, description="Client accounts (the client master)."),
            TableSpec(
                "projects",
                build_projects,
                depends_on=("departments", "employees", "clients"),
                description="Cross-functional initiatives, each run from a location.",
            ),
            TableSpec(
                "project_members",
                build_project_members,
                depends_on=("projects", "employees"),
                description="Employees staffed onto projects (many-to-many).",
            ),
            TableSpec(
                "employee_skills",
                build_employee_skills,
                depends_on=("employees", "departments"),
                description="Many-to-many bridge of employees to their skills.",
            ),
            TableSpec(
                "performance_reviews",
                build_performance_reviews,
                depends_on=("employees", "departments"),
                description="Periodic review events per employee per half-year cycle.",
            ),
            TableSpec(
                "expenses",
                build_expenses,
                depends_on=("projects", "project_members"),
                description="Project expense lines beyond labor (T&E, subcontractor, software).",
            ),
            TableSpec(
                "time_off",
                build_time_off,
                depends_on=("employees",),
                description="Per-employee leave spells (vacation/sick/holiday/unpaid/parental).",
            ),
        ),
    )


register("labor", build)
