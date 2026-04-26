from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asyncpg  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.query_planner import TalentQueryPlanner  # noqa: E402
from app.services.rule_sql_generator import TalentRuleSqlGenerator  # noqa: E402
from app.services.sql_guard import SqlGuard  # noqa: E402


def asyncpg_dsn(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


def load_cases(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def generated_sql(question: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    planner = TalentQueryPlanner()
    generator = TalentRuleSqlGenerator()
    plan = planner.plan(question, {})
    candidates = generator.generate(question, {"plan": plan})
    selected = next((item for item in candidates if item.get("sql")), candidates[0] if candidates else {})
    return plan, selected, selected.get("sql", "")


def term_passed(sql: str, plan: dict[str, Any], required_terms: str) -> tuple[bool, list[dict[str, Any]]]:
    haystack = f"{sql}\n{json.dumps(plan, ensure_ascii=False)}".lower()
    results = []
    for term in [item.strip() for item in required_terms.split("|") if item.strip()]:
        ok = term.lower() in haystack
        results.append({"term": term, "ok": ok})
    return all(item["ok"] for item in results), results


async def evaluate_case(conn: asyncpg.Connection, guard: SqlGuard, case: dict[str, str]) -> dict[str, Any]:
    plan, selected, sql = generated_sql(case["question"])
    terms_ok, term_results = term_passed(sql, plan, case.get("required_sql_terms", ""))
    view_ok = case.get("expected_view", "") in sql
    guard_result = guard.validate(sql, [])
    guard_ok = guard_result["status"] == "passed"
    answer_ok = False
    rows: list[dict[str, Any]] = []
    error = ""

    if guard_ok:
        try:
            records = await conn.fetch(sql)
            rows = [dict(record) for record in records]
            result_text = json.dumps(rows, ensure_ascii=False, default=str)
            answer_ok = str(case.get("expected_answer", "")) in result_text
        except Exception as exc:
            error = str(exc)

    return {
        "case_id": case["case_id"],
        "question": case["question"],
        "expected_answer": case.get("expected_answer", ""),
        "plan": plan,
        "route": selected.get("route", ""),
        "sql": sql,
        "view_ok": view_ok,
        "terms_ok": terms_ok,
        "term_results": term_results,
        "guard_ok": guard_ok,
        "answer_ok": answer_ok,
        "row_count": len(rows),
        "error": error,
        "passed": view_ok and terms_ok and guard_ok and answer_ok,
    }


async def main_async() -> int:
    parser = argparse.ArgumentParser(description="Evaluate db-grounded talent QA cases.")
    parser.add_argument(
        "--testset",
        default=str(ROOT / "data" / "testsets" / "talent_grounded_qa_1000.csv"),
    )
    parser.add_argument(
        "--report",
        default=str(ROOT / "runtime" / "grounded_qa_report.json"),
    )
    parser.add_argument("--fail-under", type=float, default=95.0)
    args = parser.parse_args()

    cases = load_cases(Path(args.testset))
    settings = get_settings()
    guard = SqlGuard(["vw_talent_ai_query"], settings.sql_max_limit)
    conn = await asyncpg.connect(asyncpg_dsn(settings.async_database_url))
    try:
        results = [await evaluate_case(conn, guard, case) for case in cases]
    finally:
        await conn.close()

    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    summary = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed * 100.0 / total, 2) if total else 0,
    }
    report = {"summary": summary, "results": results}
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if summary["pass_rate"] < args.fail_under:
        print(json.dumps({"first_failures": [item for item in results if not item["passed"]][:10]}, ensure_ascii=False, indent=2, default=str))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
