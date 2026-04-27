from __future__ import annotations

from typing import Any


class TalentRuleSqlGenerator:
    """Deterministic SQL candidates for common talent questions.

    These rules are not a replacement for the LLM. They are a safety net and a
    regression target for the coverage testset.
    """

    base_view = "vw_talent_ai_query"

    def generate(self, question: str, context: dict[str, Any]) -> list[dict[str, Any]]:
        plan = context.get("plan") or {}
        intent = plan.get("intent", "general")
        views = plan.get("target_views") or [self.base_view]
        primary_view = views[0]
        q = question.lower()
        candidates: list[dict[str, Any]] = []

        if intent == "unsupported_sensitive":
            return [
                self._candidate(
                    "rule_sensitive_refusal",
                    "",
                    score=-100,
                    notes=plan.get("unsupported_reason", "unsupported question"),
                )
            ]
        if intent == "person_lookup":
            return [self._person_lookup_candidate(question, plan)]

        if primary_view == "vw_talent_education_ai_query":
            return [self._education_candidate(question, plan)]
        if primary_view == "vw_talent_career_ai_query":
            return [self._career_candidate(question, plan)]
        if primary_view == "vw_talent_project_ai_query":
            return [self._project_candidate(question, plan)]
        if primary_view == "vw_talent_tag_ai_query":
            return [self._tag_candidate(question, plan)]
        if primary_view == "vw_talent_review_ai_query":
            return [self._review_candidate(question, plan)]
        if primary_view == "vw_succession_ai_query":
            return [self._succession_candidate(question, plan)]
        if primary_view == "vw_org_position_ai_query":
            return [self._org_candidate(question, plan)]

        filtered_count = self._filtered_count_candidate(plan)
        if filtered_count:
            candidates.append(filtered_count)

        if intent == "detail" and any(term in question for term in ["名单", "列出", "有哪些", "是谁", "明细"]):
            candidates.append(self._detail_candidate(question))

        if intent == "ratio" or any(term in question for term in ["占比", "比例", "率"]):
            candidates.extend(self._ratio_candidates(question))

        if any(term in question for term in ["分布", "结构", "统计", "排名", "最多", "最少", "各部门", "各公司", "按"]):
            dimension_candidate = self._dimension_distribution_candidate(question)
            if dimension_candidate:
                candidates.append(dimension_candidate)

        if any(term in question for term in ["核心", "关键人才", "q1", "q2", "Q1", "Q2"]):
            candidates.append(
                self._candidate(
                    "rule_core_talent_total",
                    "SELECT q_value, COUNT(*) AS talent_count "
                    f"FROM {self.base_view} "
                    "WHERE q_value IN ('Q1', 'Q2') "
                    "GROUP BY q_value "
                    "ORDER BY q_value "
                    "LIMIT 100;",
                )
            )

        if "ai" in q or "AI" in question or "等级" in question:
            if any(term in question for term in ["L4以上", "L4/L5", "AI高等级", "高等级"]):
                candidates.append(
                    self._candidate(
                        "rule_high_ai_level_total",
                        "SELECT ai_level, COUNT(*) AS talent_count "
                        f"FROM {self.base_view} "
                        "WHERE ai_level IN ('L4', 'L5') "
                        "GROUP BY ai_level "
                        "ORDER BY ai_level "
                        "LIMIT 100;",
                    )
                )
            else:
                candidates.append(
                    self._candidate(
                        "rule_ai_level_distribution",
                        "SELECT ai_level, COUNT(*) AS talent_count "
                        f"FROM {self.base_view} "
                        "GROUP BY ai_level "
                        "ORDER BY ai_level "
                        "LIMIT 100;",
                    )
                )

        if any(term in question for term in ["高风险", "风险"]):
            candidates.append(
                self._candidate(
                    "rule_risk_distribution",
                    "SELECT risk_level, COUNT(*) AS talent_count "
                    f"FROM {self.base_view} "
                    "GROUP BY risk_level "
                    "ORDER BY talent_count DESC "
                    "LIMIT 100;",
                )
            )

        if any(term in question for term in ["继任", "候选", "接班", "梯队"]):
            candidates.append(
                self._candidate(
                    "rule_succession_total",
                    "SELECT COUNT(*) AS succession_candidate_count "
                    f"FROM {self.base_view} "
                    "WHERE is_succession_candidate = TRUE;",
                )
            )

        if any(term in question for term in ["名单", "列出", "有哪些", "是谁", "明细"]) and not candidates:
            candidates.append(self._detail_candidate(question))

        if any(term in question for term in ["总数", "多少人", "人数", "人才数", "数量"]) and not candidates:
            candidates.append(
                self._candidate(
                    "rule_total_talent",
                    f"SELECT COUNT(*) AS talent_count FROM {self.base_view};",
                )
            )

        if not candidates:
            candidates.append(
                self._candidate(
                    "rule_default_preview",
                    "SELECT emp_id, name, company_name, dept_name, job_title, q_value, ai_level "
                    f"FROM {self.base_view} "
                    "LIMIT 100;",
                )
            )
        return candidates

    def _dimension_distribution_candidate(self, question: str) -> dict[str, Any] | None:
        dimension = ""
        if "公司" in question:
            dimension = "company_name"
        elif "岗位" in question or "职位" in question:
            dimension = "job_title"
        elif "Q值" in question or "Q等级" in question:
            dimension = "q_value"
        elif "AI" in question or "ai" in question:
            dimension = "ai_level"
        elif "部门" in question or "组织" in question or "分布" in question:
            dimension = "dept_name"
        if not dimension:
            return None
        where = self._base_filters(question)
        return self._candidate(
            f"rule_{dimension}_distribution",
            f"SELECT {dimension}, COUNT(*) AS talent_count "
            f"FROM {self.base_view} "
            f"{where}"
            f"GROUP BY {dimension} "
            "ORDER BY talent_count DESC "
            "LIMIT 100;",
        )

    def _ratio_candidates(self, question: str) -> list[dict[str, Any]]:
        if any(term in question for term in ["核心", "Q1", "Q2"]):
            return [
                self._candidate(
                    "rule_core_talent_ratio",
                    "SELECT "
                    "COUNT(*) FILTER (WHERE q_value IN ('Q1', 'Q2')) AS core_talent_count, "
                    "COUNT(*) AS total_count, "
                    "ROUND(COUNT(*) FILTER (WHERE q_value IN ('Q1', 'Q2')) * 100.0 / NULLIF(COUNT(*), 0), 2) AS core_talent_ratio "
                    f"FROM {self.base_view};",
                )
            ]
        if any(term in question for term in ["高风险", "风险"]):
            return [
                self._candidate(
                    "rule_high_risk_ratio",
                    "SELECT "
                    "COUNT(*) FILTER (WHERE risk_level = 'high') AS high_risk_count, "
                    "COUNT(*) AS total_count, "
                    "ROUND(COUNT(*) FILTER (WHERE risk_level = 'high') * 100.0 / NULLIF(COUNT(*), 0), 2) AS high_risk_ratio "
                    f"FROM {self.base_view};",
                )
            ]
        return []

    def _detail_candidate(self, question: str) -> dict[str, Any]:
        where = self._base_filters(question)
        return self._candidate(
            "rule_talent_detail",
            "SELECT emp_id, name, company_name, dept_name, job_title, q_value, ai_level, risk_level "
            f"FROM {self.base_view} "
            f"{where}"
            "ORDER BY dept_name, name "
            "LIMIT 100;",
        )

    def _filtered_count_candidate(self, plan: dict[str, Any]) -> dict[str, Any] | None:
        intent = plan.get("intent")
        filters = [item for item in plan.get("filters", []) if self._is_safe_filter(item)]
        if intent != "count" or not filters:
            return None
        return self._candidate(
            "rule_filtered_talent_count",
            "SELECT COUNT(*) AS talent_count "
            f"FROM {self.base_view} "
            f"WHERE {' AND '.join(filters)};",
            score=90,
            notes="deterministic filtered talent count",
        )

    def _person_lookup_candidate(self, question: str, plan: dict[str, Any]) -> dict[str, Any]:
        fields = self._person_fields(plan)
        where = self._where_from_plan(plan)
        return self._candidate(
            "rule_person_lookup",
            f"SELECT emp_id, name, dept_name, job_title, {', '.join(fields)} "
            f"FROM {self.base_view} "
            f"{where}"
            "ORDER BY emp_id "
            "LIMIT 20;",
            score=85,
            notes="deterministic person attribute lookup",
        )

    def _education_candidate(self, question: str, plan: dict[str, Any]) -> dict[str, Any]:
        where = self._where_from_plan(plan)
        return self._candidate(
            "rule_education_detail",
            "SELECT emp_id, name, dept_name, school_name, degree, major, is_highest "
            "FROM vw_talent_education_ai_query "
            f"{where}"
            "ORDER BY dept_name, name "
            "LIMIT 100;",
        )

    def _career_candidate(self, question: str, plan: dict[str, Any]) -> dict[str, Any]:
        where = self._where_from_plan(plan)
        return self._candidate(
            "rule_career_detail",
            "SELECT emp_id, name, dept_name, career_company_name, career_position_name, start_date, end_date, is_internal "
            "FROM vw_talent_career_ai_query "
            f"{where}"
            "ORDER BY name, start_date DESC "
            "LIMIT 100;",
        )

    def _project_candidate(self, question: str, plan: dict[str, Any]) -> dict[str, Any]:
        where = self._where_from_plan(plan)
        return self._candidate(
            "rule_project_detail",
            "SELECT emp_id, name, dept_name, project_name, role_name, industry, start_date, end_date "
            "FROM vw_talent_project_ai_query "
            f"{where}"
            "ORDER BY name, start_date DESC "
            "LIMIT 100;",
        )

    def _tag_candidate(self, question: str, plan: dict[str, Any]) -> dict[str, Any]:
        where = self._where_from_plan(plan)
        if where:
            return self._candidate(
                "rule_tag_detail",
                "SELECT emp_id, name, dept_name, tag_name, tag_type, category_l1, category_l2, score "
                "FROM vw_talent_tag_ai_query "
                f"{where}"
                "ORDER BY name, tag_type, tag_name "
                "LIMIT 100;",
            )
        return self._candidate(
            "rule_tag_distribution",
            "SELECT tag_name, tag_type, COUNT(*) AS talent_count "
            "FROM vw_talent_tag_ai_query "
            "GROUP BY tag_name, tag_type "
            "ORDER BY talent_count DESC, tag_name "
            "LIMIT 100;",
        )

    def _review_candidate(self, question: str, plan: dict[str, Any]) -> dict[str, Any]:
        if plan.get("intent") == "trend":
            return self._candidate(
                "rule_review_trend",
                "SELECT review_year, performance_level, q_value, ai_level, COUNT(*) AS talent_count "
                "FROM vw_talent_review_ai_query "
                "GROUP BY review_year, performance_level, q_value, ai_level "
                "ORDER BY review_year DESC, performance_level, q_value, ai_level "
                "LIMIT 100;",
            )
        if "Q" in question or "AI" in question or "ai" in question:
            return self._candidate(
                "rule_review_q_ai_distribution",
                "SELECT review_year, q_value, ai_level, COUNT(*) AS talent_count "
                "FROM vw_talent_review_ai_query "
                "GROUP BY review_year, q_value, ai_level "
                "ORDER BY review_year DESC, q_value, ai_level "
                "LIMIT 100;",
            )
        return self._candidate(
            "rule_review_distribution",
            "SELECT review_year, performance_level, potential_level, COUNT(*) AS talent_count "
            "FROM vw_talent_review_ai_query "
            "GROUP BY review_year, performance_level, potential_level "
            "ORDER BY review_year DESC, talent_count DESC "
            "LIMIT 100;",
        )

    def _succession_candidate(self, question: str, plan: dict[str, Any]) -> dict[str, Any]:
        return self._candidate(
            "rule_succession_detail",
            "SELECT position_name, emp_id, name, dept_name, readiness_level, risk_level, review_period "
            "FROM vw_succession_ai_query "
            "ORDER BY position_name, readiness_level, name "
            "LIMIT 100;",
        )

    def _org_candidate(self, question: str, plan: dict[str, Any]) -> dict[str, Any]:
        where = "WHERE is_manager = TRUE " if "管理岗位" in question else ""
        return self._candidate(
            "rule_org_position_distribution",
            "SELECT company_name, dept_name, COUNT(*) AS position_count, SUM(headcount) AS total_headcount "
            "FROM vw_org_position_ai_query "
            f"{where}"
            "GROUP BY company_name, dept_name "
            "ORDER BY position_count DESC, company_name, dept_name "
            "LIMIT 100;",
        )

    def _base_filters(self, question: str) -> str:
        filters = []
        if any(term in question for term in ["核心", "关键人才", "Q1", "Q2"]):
            filters.append("q_value IN ('Q1', 'Q2')")
        if any(term in question for term in ["高风险", "风险高", "高流失"]):
            filters.append("risk_level = 'high'")
        if any(term in question for term in ["继任", "候选", "接班", "梯队"]):
            filters.append("is_succession_candidate = TRUE")
        if any(term in question for term in ["L4以上", "L4/L5", "AI高等级"]):
            filters.append("ai_level IN ('L4', 'L5')")
        if "L4" in question and "L4以上" not in question and "L4/L5" not in question:
            filters.append("ai_level = 'L4'")
        if "L5" in question and "L4/L5" not in question:
            filters.append("ai_level = 'L5'")
        return f"WHERE {' AND '.join(filters)} " if filters else ""

    def _where_from_plan(self, plan: dict[str, Any]) -> str:
        filters = [item for item in plan.get("filters", []) if self._is_safe_filter(item)]
        return f"WHERE {' AND '.join(filters)} " if filters else ""

    def _is_safe_filter(self, filter_sql: str) -> bool:
        return all(keyword not in filter_sql.upper() for keyword in (";", "DROP", "DELETE", "UPDATE", "INSERT"))

    def _person_fields(self, plan: dict[str, Any]) -> list[str]:
        allowed = {
            "ai_level",
            "q_value",
            "dept_name",
            "company_name",
            "job_title",
            "job_level",
            "performance_level",
            "potential_level",
            "stability_level",
            "risk_level",
            "highest_degree",
            "school_name",
            "major_name",
        }
        fields = []
        for item in [*plan.get("metrics", []), *plan.get("dimensions", [])]:
            if item in allowed and item not in {"dept_name", "job_title"} and item not in fields:
                fields.append(item)
        return fields or ["q_value", "ai_level", "performance_level", "potential_level", "risk_level"]

    def _candidate(self, route: str, sql: str, *, score: int = 70, notes: str = "deterministic talent fallback") -> dict[str, Any]:
        return {
            "route": route,
            "sql": sql,
            "source": "rule",
            "score": score,
            "notes": notes,
        }
