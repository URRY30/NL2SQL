from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class QueryPlan:
    intent: str
    target_views: list[str]
    metrics: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    filters: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    unsupported_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "target_views": self.target_views,
            "metrics": self.metrics,
            "dimensions": self.dimensions,
            "filters": self.filters,
            "entities": self.entities,
            "needs_clarification": self.needs_clarification,
            "unsupported_reason": self.unsupported_reason,
        }


class TalentQueryPlanner:
    """Classifies talent-domain questions before SQL generation.

    The planner is intentionally deterministic. It gives the LLM and rule
    fallback a stable business frame instead of asking the model to infer the
    whole problem from raw natural language.
    """

    DEFAULT_VIEW = "vw_talent_ai_query"
    VIEW_BY_DOMAIN = {
        "education": "vw_talent_education_ai_query",
        "career": "vw_talent_career_ai_query",
        "project": "vw_talent_project_ai_query",
        "review": "vw_talent_review_ai_query",
        "tag": "vw_talent_tag_ai_query",
        "succession": "vw_succession_ai_query",
        "org": "vw_org_position_ai_query",
    }

    SENSITIVE_TERMS = ("密码", "password", "token", "密钥", "身份证", "手机号", "电话", "薪资", "工资")
    PERSON_ATTRIBUTE_TERMS = {
        "AI等级": "ai_level",
        "AI级别": "ai_level",
        "ai等级": "ai_level",
        "Q值": "q_value",
        "Q等级": "q_value",
        "部门": "dept_name",
        "所在部门": "dept_name",
        "所属部门": "dept_name",
        "公司": "company_name",
        "所属公司": "company_name",
        "岗位": "job_title",
        "职位": "job_title",
        "职级": "job_level",
        "绩效": "performance_level",
        "绩效等级": "performance_level",
        "潜力": "potential_level",
        "潜力等级": "potential_level",
        "稳定性": "stability_level",
        "风险": "risk_level",
        "风险等级": "risk_level",
        "学历": "highest_degree",
        "最高学历": "highest_degree",
        "学校": "school_name",
        "毕业学校": "school_name",
        "专业": "major_name",
    }

    def plan(self, question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        text = str(question or "").strip()
        lower = text.lower()
        if not text:
            return QueryPlan(
                intent="empty",
                target_views=[],
                needs_clarification=True,
                unsupported_reason="question is empty",
            ).as_dict()

        if any(term in lower or term in text for term in self.SENSITIVE_TERMS):
            return QueryPlan(
                intent="unsupported_sensitive",
                target_views=[],
                needs_clarification=False,
                unsupported_reason="question asks for sensitive or non-whitelisted data",
            ).as_dict()

        person_name = self._person_name(text)
        employee_id = self._employee_id(text)
        domains = self._domains(text, lower)
        views = [self.VIEW_BY_DOMAIN[domain] for domain in domains] or [self.DEFAULT_VIEW]
        intent = self._intent(text, lower)
        if (person_name or employee_id) and self._person_attribute(text):
            intent = "person_lookup"
            views = [self.DEFAULT_VIEW]

        if "succession" in domains and self.VIEW_BY_DOMAIN["succession"] not in views:
            views.append(self.VIEW_BY_DOMAIN["succession"])

        return QueryPlan(
            intent=intent,
            target_views=views,
            metrics=self._metrics(text, lower),
            dimensions=self._dimensions(text, lower),
            filters=self._filters(text, lower),
            entities=self._entities(text),
            needs_clarification=self._needs_clarification(text, intent),
        ).as_dict()

    def _domains(self, text: str, lower: str) -> list[str]:
        domains: list[str] = []
        checks = [
            ("education", ("学历", "学位", "学校", "毕业", "专业", "985", "211", "硕士", "博士", "本科")),
            ("project", ("项目", "课题", "经验", "做过", "参与过")),
            ("career", ("履历", "任职", "外企", "工作过", "曾经", "上一家公司")),
            ("review", ("绩效", "潜力", "评审", "九宫格", "雷达", "评分", "近三年", "去年", "今年", "历年", "年份")),
            ("tag", ("标签", "技能", "能力", "python", "java", "ai标签", "风险标签")),
            ("org", ("编制", "职位", "部门负责人", "组织结构", "管理岗位", "空缺岗位")),
        ]
        for domain, terms in checks:
            if any(term in lower or term in text for term in terms):
                domains.append(domain)
        if "经历" in text and "项目" not in text and "project" not in domains:
            domains.append("career")
        if any(
            term in text or term in lower
            for term in ("继任计划", "继任岗位", "接班", "梯队", "ready", "readiness", "储备干部", "准备度", "成熟度", "可用", "一年内", "两年内", "立即")
        ):
            domains.append("succession")
        if "succession" in domains and "review" in domains:
            domains = [domain for domain in domains if domain != "review"]
        if "project" in domains and "career" in domains:
            domains = [domain for domain in domains if domain != "career"]
        return domains

    def _intent(self, text: str, lower: str) -> str:
        if any(term in text for term in ("占比", "比例", "率")):
            return "ratio"
        if any(term in text for term in ("对比", "比较", "相比")):
            return "compare"
        if any(term in text for term in ("趋势", "变化", "近三年", "历年", "去年", "今年")):
            return "trend"
        if any(term in text for term in ("排名", "最多", "最少", "前", "top")) or "top" in lower:
            return "ranking"
        if any(term in text for term in ("分布", "各", "按", "结构")):
            return "distribution"
        if any(term in text for term in ("列出", "名单", "有哪些", "是谁", "明细", "详情")):
            return "detail"
        if any(term in text for term in ("多少", "几人", "人数", "数量", "总数")):
            return "count"
        return "general"

    def _metrics(self, text: str, lower: str) -> list[str]:
        metrics = []
        attribute = self._person_attribute(text)
        if attribute:
            metrics.append(attribute)
        if any(term in text for term in ("核心人才", "关键人才", "Q1", "Q2")):
            metrics.append("core_talent")
        if any(term in lower or term in text for term in ("ai", "AI", "L4", "L5")):
            metrics.append("ai_level")
        if any(term in text for term in ("高风险", "风险", "流失")):
            metrics.append("risk")
        if any(term in text for term in ("继任", "接班", "梯队", "储备")):
            metrics.append("succession")
        if any(term in text for term in ("绩效", "潜力", "九宫格", "雷达")):
            metrics.append("review")
        return metrics

    def _dimensions(self, text: str, lower: str) -> list[str]:
        dimensions = []
        attribute = self._person_attribute(text)
        if attribute:
            dimensions.append(attribute)
        if "部门" in text or "组织" in text:
            dimensions.append("dept_name")
        if "公司" in text:
            dimensions.append("company_name")
        if "岗位" in text or "职位" in text:
            dimensions.append("job_title")
        if "Q值" in text or "Q等级" in text or "q" in lower:
            dimensions.append("q_value")
        if "AI" in text or "ai" in lower:
            dimensions.append("ai_level")
        if "学校" in text or "学历" in text or "学位" in text:
            dimensions.append("education")
        return dimensions

    def _filters(self, text: str, lower: str) -> list[str]:
        filters = []
        person_name = self._person_name(text)
        employee_id = self._employee_id(text)
        if person_name:
            filters.append(f"name = '{person_name}'")
        if employee_id:
            filters.append(f"emp_id = '{employee_id}'")
        if any(term in text for term in ("核心人才", "关键人才", "Q1", "Q2")):
            filters.append("q_value IN ('Q1', 'Q2')")
        if any(term in text for term in ("L4以上", "L4/L5", "AI高等级", "AI高潜")):
            filters.append("ai_level IN ('L4', 'L5')")
        elif "L4" in text:
            filters.append("ai_level = 'L4'")
        elif "L5" in text:
            filters.append("ai_level = 'L5'")
        if any(term in text for term in ("高风险", "风险高", "高流失")):
            filters.append("risk_level = 'high'")
        if any(term in text for term in ("在职", "当前在岗")):
            filters.append("employee_status = 'active'")
        if "985" in text:
            filters.append("school_name ILIKE '%985%'")
        if "211" in text:
            filters.append("school_name ILIKE '%211%'")
        for degree in ("博士", "硕士", "本科"):
            if degree in text:
                filters.append(f"degree ILIKE '%{degree}%'")
        return filters

    def _entities(self, text: str) -> list[str]:
        entities = []
        person_name = self._person_name(text)
        employee_id = self._employee_id(text)
        if person_name:
            entities.append(person_name)
        if employee_id:
            entities.append(employee_id)
        for marker in ("研发部", "销售部", "市场部", "产品部", "人力资源部"):
            if marker in text:
                entities.append(marker)
        return entities

    def _needs_clarification(self, text: str, intent: str) -> bool:
        return intent == "general" and len(text) <= 4

    def _person_name(self, text: str) -> str:
        patterns = [
            r"(?P<name>[\u4e00-\u9fa5]{2,4})的(?:AI等级|AI级别|ai等级|Q值|Q等级|所在部门|所属部门|部门|所属公司|公司|岗位|职位|职级|绩效等级|绩效|潜力等级|潜力|稳定性|风险等级|风险|最高学历|学历|毕业学校|学校|专业)",
            r"(?:查询|查看|看看|告诉我)?(?P<name>[\u4e00-\u9fa5]{2,4})(?:这个人)?(?:的)?(?:信息|画像|详情)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group("name")
                if name not in {"各部门", "各公司", "核心人才", "高风险", "继任候选", "人才"}:
                    return name
        return ""

    def _person_attribute(self, text: str) -> str:
        for term, column in self.PERSON_ATTRIBUTE_TERMS.items():
            if term in text:
                return column
        if re.search(r"\bai\b", text, re.I):
            return "ai_level"
        return ""

    def _employee_id(self, text: str) -> str:
        if not self._person_attribute(text):
            return ""
        patterns = [
            r"(?:工号|员工编号|员工号|编号)\s*(?P<emp>[A-Za-z0-9_-]{3,32})",
            r"(?P<emp>EMP\d{3,}|[0-9]{6,})\s*的",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.I)
            if match:
                return match.group("emp")
        return ""
