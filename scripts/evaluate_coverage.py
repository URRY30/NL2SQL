from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.query_planner import TalentQueryPlanner  # noqa: E402
from app.services.rule_sql_generator import TalentRuleSqlGenerator  # noqa: E402


def load_cases(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate_case(case: dict[str, str]) -> dict[str, Any]:
    planner = TalentQueryPlanner()
    generator = TalentRuleSqlGenerator()
    question = case["question"]
    plan = planner.plan(question, {})
    candidates = generator.generate(question, {"plan": plan})
    selected = next((item for item in candidates if item.get("sql")), candidates[0] if candidates else {})
    sql = selected.get("sql", "")

    expected_view = case.get("expected_view", "")
    required_terms = [item.strip() for item in case.get("required_sql_terms", "").split("|") if item.strip()]

    view_ok = True
    if expected_view:
        view_ok = expected_view in plan.get("target_views", []) or expected_view in sql
    else:
        view_ok = not sql and plan.get("intent") == "unsupported_sensitive"

    term_results = [
        {
            "term": term,
            "ok": term.lower() in sql.lower() or term.lower() in json.dumps(plan, ensure_ascii=False).lower(),
        }
        for term in required_terms
    ]
    terms_ok = all(item["ok"] for item in term_results)

    return {
        "case_id": case["case_id"],
        "question": question,
        "intent_expected": case.get("intent", ""),
        "intent_actual": plan.get("intent", ""),
        "expected_view": expected_view,
        "target_views": plan.get("target_views", []),
        "route": selected.get("route", ""),
        "sql": sql,
        "view_ok": view_ok,
        "terms_ok": terms_ok,
        "term_results": term_results,
        "passed": view_ok and terms_ok,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for item in results if item["passed"])
    by_intent: dict[str, dict[str, int]] = {}
    for item in results:
        intent = item["intent_expected"]
        bucket = by_intent.setdefault(intent, {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += 1 if item["passed"] else 0
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed * 100.0 / total, 2) if total else 0,
        "by_intent": by_intent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate NL2SQL coverage testset with deterministic planner/rules.")
    parser.add_argument(
        "--testset",
        default=str(ROOT / "data" / "testsets" / "talent_coverage_v1.csv"),
        help="CSV testset path",
    )
    parser.add_argument(
        "--report",
        default=str(ROOT / "runtime" / "coverage_report.json"),
        help="JSON report output path",
    )
    parser.add_argument("--fail-under", type=float, default=90.0, help="minimum pass rate")
    args = parser.parse_args()

    cases = load_cases(Path(args.testset))
    results = [evaluate_case(case) for case in cases]
    summary = summarize(results)
    report = {"summary": summary, "results": results}

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["pass_rate"] < args.fail_under:
        failed = [item for item in results if not item["passed"]][:10]
        print(json.dumps({"first_failures": failed}, ensure_ascii=False, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
