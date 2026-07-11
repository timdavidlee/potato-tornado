"""The ``employee_skills`` table: the many-to-many skills bridge behind the
single-valued ``employees.primary_skill``.

One row per (employee, skill). Each employee carries 1-4 skills drawn from their
own practice's ``SKILLS_BY_DEPARTMENT`` set, and the set always includes their
`primary_skill` so the bridge stays consistent with the scalar column. Skills are
sampled without replacement (no duplicate skill per employee), with a proficiency
level and a certification flag on their own child streams.
"""

from __future__ import annotations

import polars as pl

from potato_tornado.collections.labor.constants import SKILLS_BY_DEPARTMENT
from potato_tornado.core.collection import GenContext

# Proficiency ladder and its flat org-wide mix; certification is a flat rate. Both
# realism enrichment (no per-practice depth signal planted).
_PROFICIENCY = ("beginner", "intermediate", "expert")
_PROFICIENCY_WEIGHTS = (0.35, 0.45, 0.20)
_CERTIFIED_P = 0.30


def build_employee_skills(ctx: GenContext) -> pl.DataFrame:
    employees = ctx.table("employees")
    departments = ctx.table("departments")
    dept_name = dict(
        zip(
            departments["department_id"].to_list(),
            departments["name"].to_list(),
            strict=True,
        )
    )

    emp_ids = employees["employee_id"].to_list()
    emp_dept = employees["department_id"].to_list()
    emp_primary = employees["primary_skill"].to_list()

    # One draw per employee for the skill count and the extra-skill picks. Own child
    # stream so this table is independent of every other table's draws.
    skills_rng = ctx.rng.child("skills").numpy

    rows_emp: list[str] = []
    rows_skill: list[str] = []
    for emp_id, dept_id, primary in zip(emp_ids, emp_dept, emp_primary, strict=True):
        catalog = SKILLS_BY_DEPARTMENT[dept_name[dept_id]]
        others = [s for s in catalog if s != primary]
        k = int(skills_rng.integers(1, 5))  # 1..4 skills
        n_extra = min(k - 1, len(others))
        extra = (
            skills_rng.choice(others, size=n_extra, replace=False).tolist() if n_extra > 0 else []
        )
        skills = [primary, *extra]  # always includes the primary skill
        rows_emp.extend([emp_id] * len(skills))
        rows_skill.extend(skills)

    n = len(rows_emp)
    proficiency = ctx.rng.child("proficiency").numpy.choice(
        _PROFICIENCY, size=n, p=_PROFICIENCY_WEIGHTS
    )
    certified = ctx.rng.child("certified").numpy.random(n) < _CERTIFIED_P

    return pl.DataFrame(
        {
            "employee_skill_id": [f"ESK-{i:06d}" for i in range(1, n + 1)],
            "employee_id": rows_emp,
            "skill": rows_skill,
            "proficiency": proficiency,
            "certified": pl.Series(certified, dtype=pl.Boolean),
        }
    )
