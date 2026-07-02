"""Collection: labor assignment and utilization.

Models a workforce being scheduled onto shifts and how actual attendance compares
to what was planned — the raw material for utilization and overtime analysis.

Tables
------
- ``departments``   : cost centres that own shifts and staff.
- ``employees``     : the workforce, tied to a home department.
- ``shifts``        : planned shifts with a required headcount and a time window.
- ``assignments``   : employees rostered onto shifts (the plan).
- ``time_entries``  : actual clock-in / clock-out per assignment (the reality),
                      including no-shows, late starts and overtime.

Table builders live in ``tables/``, the domain catalogs in ``constants.py``, and
the intended analytical signals in ``scenarios/``.
"""

from __future__ import annotations

from potato_tornado.collections.labor.tables import (
    build_assignments,
    build_departments,
    build_employees,
    build_shifts,
    build_time_entries,
)
from potato_tornado.core.collection import Collection, TableSpec
from potato_tornado.core.registry import register


def build() -> Collection:
    return Collection(
        name="labor",
        description="Labor assignment and utilization: staff, planned shifts, "
        "rosters, and actual attendance vs. plan.",
        tables=(
            TableSpec("departments", build_departments, description="Cost centres."),
            TableSpec(
                "employees",
                build_employees,
                depends_on=("departments",),
                description="Workforce with roles and pay rates.",
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
        ),
    )


register("labor", build)
