from __future__ import annotations

import asyncio
import csv
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asyncpg  # noqa: E402

from app.core.config import get_settings  # noqa: E402


OUTPUT = ROOT / "data" / "testsets" / "talent_grounded_qa_1000.csv"

ATTRIBUTE_CASES = [
    ("AI等级", "ai_level"),
    ("Q值", "q_value"),
    ("所在部门", "dept_name"),
    ("所属公司", "company_name"),
    ("岗位", "job_title"),
    ("职级", "job_level"),
    ("绩效等级", "performance_level"),
    ("潜力等级", "potential_level"),
    ("稳定性", "stability_level"),
    ("风险等级", "risk_level"),
    ("最高学历", "highest_degree"),
    ("毕业学校", "school_name"),
    ("专业", "major_name"),
]

QUESTION_TEMPLATES = [
    "工号{emp_id}的{label}是多少？",
    "员工编号{emp_id}的{label}是什么？",
    "查询工号{emp_id}的{label}",
    "{name}的{label}是多少？",
]


def asyncpg_dsn(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


def sql_literal(value: Any) -> str:
    return str(value).replace("'", "''")


async def fetch_rows() -> list[dict[str, Any]]:
    settings = get_settings()
    conn = await asyncpg.connect(asyncpg_dsn(settings.async_database_url))
    try:
        rows = await conn.fetch(
            """
            SELECT
                emp_id,
                name,
                company_name,
                dept_name,
                job_title,
                job_level,
                q_value,
                ai_level,
                performance_level,
                potential_level,
                stability_level,
                risk_level,
                highest_degree,
                school_name,
                major_name
            FROM vw_talent_ai_query
            WHERE emp_id IS NOT NULL
              AND name IS NOT NULL
            ORDER BY id
            """
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


def expected_sql(row: dict[str, Any], column: str, *, by_name: bool) -> str:
    if by_name:
        predicate = f"name = '{sql_literal(row['name'])}'"
    else:
        predicate = f"emp_id = '{sql_literal(row['emp_id'])}'"
    return (
        f"SELECT emp_id, name, dept_name, job_title, {column} "
        "FROM vw_talent_ai_query "
        f"WHERE {predicate} "
        "ORDER BY emp_id "
        "LIMIT 20;"
    )


def build_cases(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    counter = 1

    li_zeyang = next((row for row in rows if row["name"] == "李泽阳"), None)
    if li_zeyang and li_zeyang.get("ai_level"):
        cases.append(
            {
                "case_id": "TALENT_GROUNDED_0001",
                "topic": "talent",
                "intent": "person_lookup",
                "question": "李泽阳的AI等级为多少？",
                "expected_view": "vw_talent_ai_query",
                "required_sql_terms": "name = '李泽阳'|ai_level|LIMIT 20",
                "expected_sql": expected_sql(li_zeyang, "ai_level", by_name=True),
                "expected_answer": str(li_zeyang["ai_level"]),
                "source_emp_id": str(li_zeyang["emp_id"]),
                "source_name": str(li_zeyang["name"]),
                "difficulty": "easy",
                "notes": "user reported regression case",
            }
        )
        counter = 2

    for row in rows:
        for label, column in ATTRIBUTE_CASES:
            value = row.get(column)
            if value in (None, ""):
                continue
            for template in QUESTION_TEMPLATES:
                if len(cases) >= 1000:
                    return cases
                by_name = template.startswith("{name}")
                question = template.format(emp_id=row["emp_id"], name=row["name"], label=label)
                cases.append(
                    {
                        "case_id": f"TALENT_GROUNDED_{counter:04d}",
                        "topic": "talent",
                        "intent": "person_lookup",
                        "question": question,
                        "expected_view": "vw_talent_ai_query",
                        "required_sql_terms": f"{'name' if by_name else 'emp_id'} = '{sql_literal(row['name'] if by_name else row['emp_id'])}'|{column}|LIMIT 20",
                        "expected_sql": expected_sql(row, column, by_name=by_name),
                        "expected_answer": str(value),
                        "source_emp_id": str(row["emp_id"]),
                        "source_name": str(row["name"]),
                        "difficulty": "easy" if not by_name else "medium",
                        "notes": "db-grounded person attribute case",
                    }
                )
                counter += 1
    return cases


async def main_async() -> None:
    rows = await fetch_rows()
    cases = build_cases(rows)
    if len(cases) < 1000:
        raise RuntimeError(f"not enough grounded cases generated: {len(cases)}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cases[0].keys()))
        writer.writeheader()
        writer.writerows(cases)
    print(f"wrote {len(cases)} cases to {OUTPUT}")


if __name__ == "__main__":
    asyncio.run(main_async())
