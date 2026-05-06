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
        "org_department": "departments",
    }

    SENSITIVE_TERMS = ("密码", "password", "token", "密钥", "身份证", "手机号", "电话", "薪资", "工资")
    PERSON_ATTRIBUTE_TERMS = {
        "AI等级": "ai_level",
        "AI级别": "ai_level",
        "ai等级": "ai_level",
        "AI值": "ai_level",
        "ai值": "ai_level",
        "AI 值": "ai_level",
        "ai 值": "ai_level",
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
        "年龄": "birth_date",
        "出生日期": "birth_date",
        "司龄": "hire_date",
        "工龄": "hire_date",
        "入职日期": "hire_date",
        "性别": "gender_label",
        "男女": "gender_label",
        "婚姻": "marital_status",
        "婚姻状况": "marital_status",
        "籍贯": "nationality_native_place",
        "户籍": "nationality_native_place",
        "地域": "location",
        "地区": "location",
        "城市": "location",
        "工作地": "location",
        "职级序列": "job_grade_track",
        "岗位序列": "job_grade_track",
        "序列": "job_grade_track",
        "职等": "job_grade_level",
        "职级等级": "job_grade_level",
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
            ("org_department", ("一级部门", "二级部门", "三级部门", "部门层级", "部门架构", "组织架构", "组织结构", "多少个部门", "几个部门")),
            ("org", ("编制", "职位", "部门负责人", "管理岗位", "空缺岗位")),
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
        if any(term in text for term in ("一级部门", "二级部门", "三级部门", "部门层级", "部门架构", "组织架构", "组织结构")):
            if any(term in text for term in ("多少", "几个", "多少个", "数量", "总数")):
                return "org_department_count"
            return "org_department_detail"
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
        if "分析" in text and any(
            term in text
            for term in (
                "性别",
                "婚姻",
                "年龄",
                "司龄",
                "学历",
                "地域",
                "地区",
                "城市",
                "工作地",
                "籍贯",
                "户籍",
                "职级",
                "职等",
                "序列",
                "岗位",
                "风险",
                "绩效",
                "潜力",
                "AI",
                "Q值",
            )
        ):
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
        if any(term in text for term in ("年龄", "年龄段", "年龄结构", "年龄分布")):
            metrics.append("age_distribution")
        if any(term in text for term in ("司龄", "工龄", "入职年限")):
            metrics.append("tenure_distribution")
        if any(term in text for term in ("性别", "男女")):
            metrics.append("gender_distribution")
        if any(term in text for term in ("婚姻", "婚育")):
            metrics.append("marital_distribution")
        if any(term in text for term in ("地域", "地区", "城市", "工作地", "籍贯", "户籍")):
            metrics.append("location_distribution")
        if any(term in text for term in ("职级", "职等", "序列", "岗位序列")):
            metrics.append("job_grade_distribution")
        return metrics

    def _dimensions(self, text: str, lower: str) -> list[str]:
        dimensions = []
        attribute = self._person_attribute(text)
        if attribute:
            dimensions.append(attribute)
        if any(term in text for term in ("一级部门", "二级部门", "三级部门", "部门层级", "部门架构", "组织架构", "组织结构")):
            dimensions.append("dept_level")
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
        if "年龄" in text:
            dimensions.append("birth_date")
        if "司龄" in text or "工龄" in text or "入职年限" in text:
            dimensions.append("hire_date")
        if "性别" in text or "男女" in text:
            dimensions.append("gender_label")
        if "婚姻" in text or "婚育" in text:
            dimensions.append("marital_status")
        if "籍贯" in text or "户籍" in text:
            dimensions.append("nationality_native_place")
        if "地域" in text or "地区" in text or "城市" in text or "工作地" in text:
            dimensions.append("location")
        if "职级序列" in text or "岗位序列" in text or "序列" in text:
            dimensions.append("job_grade_track")
        if "职等" in text or "职级等级" in text:
            dimensions.append("job_grade_level")
        return dimensions

    def _filters(self, text: str, lower: str) -> list[str]:
        filters = []
        person_name = self._person_name(text)
        employee_id = self._employee_id(text)
        if person_name:
            filters.append(f"name = '{person_name}'")
        if employee_id:
            filters.append(f"emp_id = '{employee_id}'")
        company_filter = self._company_filter(text)
        if company_filter:
            filters.append(company_filter)
        dept_filter = self._dept_filter(text)
        if dept_filter:
            filters.append(dept_filter)
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
        company = self._company_entity(text)
        if company:
            entities.append(company)
        dept = self._dept_entity(text)
        if dept:
            entities.append(dept)
        for marker in ("研发部", "销售部", "市场部", "产品部", "人力资源部"):
            if marker in text:
                entities.append(marker)
        return entities

    def _needs_clarification(self, text: str, intent: str) -> bool:
        return intent == "general" and len(text) <= 4

    def _person_name(self, text: str) -> str:
        attribute_terms = (
            "AI等级|AI级别|ai等级|AI值|ai值|AI 值|ai 值|Q值|Q等级|所在部门|所属部门|部门|所属公司|公司|岗位|职位|职级|"
            "绩效等级|绩效|潜力等级|潜力|稳定性|风险等级|风险|最高学历|学历|毕业学校|学校|专业"
        )
        prefixes = r"(?:帮我|请|麻烦)?(?:查一下|查询一下|看一下|查询|查看|看看|告诉我)?"
        patterns = [
            rf"{prefixes}(?P<name>[\u4e00-\u9fa5]{{2,4}})的(?:{attribute_terms})",
            rf"{prefixes}(?P<name>[\u4e00-\u9fa5]{{2,4}})(?:这个人)?(?:的)?(?:信息|画像|详情)",
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

    def _company_entity(self, text: str) -> str:
        if "丰图" in text or "图元" in text:
            return "丰图科技"
        if "丰行" in text or "慧运" in text:
            return "丰行慧运"
        return ""

    def _company_filter(self, text: str) -> str:
        company = self._company_entity(text)
        return f"company_name = '{company}'" if company else ""

    def _dept_entity(self, text: str) -> str:
        if self._company_entity(text):
            text = text.replace("丰图科技", "").replace("丰图公司", "").replace("丰图", "")
            text = text.replace("丰行慧运", "").replace("丰行公司", "").replace("丰行", "")
        if any(term in text for term in ("人事", "人力", "人力行政")):
            return "人力行政"
        patterns = [
            r"([\u4e00-\u9fa5A-Za-z0-9]+(?:部|处|组|中心|区|办|办公室|研发组|财务组|行政组|营销组|交付组|产品组))的?人才",
            r"([\u4e00-\u9fa5A-Za-z0-9]+(?:部|处|组|中心|区|办|办公室|研发组|财务组|行政组|营销组|交付组|产品组))(?:性别|婚姻|年龄|司龄|学历|职级|岗位|风险|绩效|AI|Q值)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                entity = match.group(1).strip("的在中 ")
                if entity and entity not in {"全部人才", "所有人才"}:
                    return entity
        return ""

    def _dept_filter(self, text: str) -> str:
        dept = self._dept_entity(text)
        if not dept:
            return ""
        escaped = dept.replace("'", "''")
        return f"(dept_name ILIKE '%{escaped}%' OR dept_path ILIKE '%{escaped}%')"

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
