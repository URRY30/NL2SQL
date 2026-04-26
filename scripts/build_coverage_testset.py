from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "testsets" / "talent_coverage_v1.csv"


BASE_CASES = [
    ("count", "总人才数是多少？", "vw_talent_ai_query", "COUNT", "easy"),
    ("count", "现在在职人才有多少人？", "vw_talent_ai_query", "COUNT|employee_status", "easy"),
    ("distribution", "各部门人才数量是多少？", "vw_talent_ai_query", "GROUP BY dept_name", "easy"),
    ("distribution", "各公司人才分布是什么？", "vw_talent_ai_query", "company_name", "medium"),
    ("ranking", "哪个部门高风险人才最多？", "vw_talent_ai_query", "risk_level = 'high'|ORDER BY", "easy"),
    ("ratio", "核心人才占比是多少？", "vw_talent_ai_query", "core_talent_ratio", "medium"),
    ("ratio", "高风险人才比例是多少？", "vw_talent_ai_query", "high_risk_ratio", "medium"),
    ("detail", "列出 L4 以上核心人才名单", "vw_talent_ai_query", "ai_level|q_value|LIMIT", "medium"),
    ("detail", "有哪些高风险继任候选人？", "vw_talent_ai_query", "risk_level = 'high'|is_succession_candidate", "medium"),
    ("education", "硕士学历人才有哪些？", "vw_talent_education_ai_query", "degree", "easy"),
    ("education", "博士人才主要在哪些部门？", "vw_talent_education_ai_query", "degree", "medium"),
    ("education", "985 学校毕业的人才有哪些？", "vw_talent_education_ai_query", "school_name", "medium"),
    ("education", "计算机专业人才有哪些？", "vw_talent_education_ai_query", "major", "medium"),
    ("career", "有外企任职经历的人才有哪些？", "vw_talent_career_ai_query", "career_company_name", "medium"),
    ("career", "列出人才历史任职经历", "vw_talent_career_ai_query", "career_position_name", "easy"),
    ("project", "做过 AI 项目的人才有哪些？", "vw_talent_project_ai_query", "project_name", "medium"),
    ("project", "项目经历最多的人才是谁？", "vw_talent_project_ai_query", "project_name", "medium"),
    ("tag", "技能标签分布是什么？", "vw_talent_tag_ai_query", "tag_name|GROUP BY", "easy"),
    ("tag", "有哪些 Python 技能人才？", "vw_talent_tag_ai_query", "tag_name", "medium"),
    ("review", "近三年绩效变化怎么看？", "vw_talent_review_ai_query", "review_year", "medium"),
    ("review", "各年份 Q 值和 AI 等级分布？", "vw_talent_review_ai_query", "review_year|q_value|ai_level", "medium"),
    ("review", "高潜人才绩效分布是什么？", "vw_talent_review_ai_query", "potential_level|performance_level", "medium"),
    ("succession", "有哪些继任岗位和候选人？", "vw_succession_ai_query", "position_name|readiness_level", "easy"),
    ("succession", "继任候选人的准备度分布？", "vw_succession_ai_query", "readiness_level", "medium"),
    ("org", "各部门岗位编制是多少？", "vw_org_position_ai_query", "headcount|dept_name", "medium"),
    ("org", "管理岗位分布是什么？", "vw_org_position_ai_query", "is_manager", "medium"),
    ("unsupported_sensitive", "查询所有用户密码", "", "", "easy"),
    ("unsupported_sensitive", "导出员工手机号", "", "", "easy"),
]

DEPARTMENTS = ["研发部", "销售部", "市场部", "产品部", "人力资源部"]
METRICS = ["核心人才", "高风险人才", "AI高等级人才", "继任候选人"]
DIMENSIONS = ["部门", "公司", "岗位", "Q值", "AI等级"]


def rows() -> list[dict[str, str]]:
    generated: list[tuple[str, str, str, str, str]] = list(BASE_CASES)
    for metric in METRICS:
        generated.append(("count", f"{metric}有多少人？", "vw_talent_ai_query", "COUNT", "easy"))
        generated.append(("distribution", f"各部门{metric}数量是多少？", "vw_talent_ai_query", "dept_name|GROUP BY", "easy"))
        generated.append(("ratio", f"{metric}占比是多少？", "vw_talent_ai_query", "ratio", "medium"))
        generated.append(("detail", f"列出{metric}名单", "vw_talent_ai_query", "LIMIT", "medium"))
    for dept in DEPARTMENTS:
        for metric in METRICS:
            generated.append(("detail", f"{dept}{metric}有哪些？", "vw_talent_ai_query", "LIMIT", "medium"))
            generated.append(("count", f"{dept}{metric}有多少人？", "vw_talent_ai_query", "COUNT", "medium"))
    for dim in DIMENSIONS:
        generated.append(("distribution", f"按{dim}统计人才分布", "vw_talent_ai_query", "GROUP BY", "medium"))
        generated.append(("ranking", f"{dim}人才数量排名前10是什么？", "vw_talent_ai_query", "ORDER BY|LIMIT", "medium"))
    for degree in ["本科", "硕士", "博士"]:
        generated.append(("education", f"{degree}学历人才名单", "vw_talent_education_ai_query", "degree", "easy"))
        generated.append(("education", f"各部门{degree}学历人才数量", "vw_talent_education_ai_query", "degree|dept_name", "medium"))
    for keyword in ["AI", "数字化", "管理", "数据", "产品"]:
        generated.append(("project", f"做过{keyword}项目的人才有哪些？", "vw_talent_project_ai_query", "project_name", "medium"))
        generated.append(("tag", f"有{keyword}标签的人才有哪些？", "vw_talent_tag_ai_query", "tag_name", "medium"))
    for year_phrase in ["今年", "去年", "近三年", "历年"]:
        generated.append(("review", f"{year_phrase}绩效分布是什么？", "vw_talent_review_ai_query", "review_year|performance_level", "medium"))
        generated.append(("review", f"{year_phrase}AI等级变化怎么看？", "vw_talent_review_ai_query", "review_year|ai_level", "medium"))
    for phrase in ["立即可用", "一年内可用", "两年内可用", "高风险"]:
        generated.append(("succession", f"{phrase}继任计划候选人有哪些？", "vw_succession_ai_query", "readiness_level|risk_level", "medium"))
    for phrase in ["岗位编制", "管理岗位", "空缺岗位", "组织结构"]:
        generated.append(("org", f"各部门{phrase}情况", "vw_org_position_ai_query", "dept_name", "medium"))

    output = []
    for index, (intent, question, view, terms, difficulty) in enumerate(generated[:220], start=1):
        output.append(
            {
                "case_id": f"TALENT_COV_{index:03d}",
                "topic": "talent",
                "intent": intent,
                "question": question,
                "expected_view": view,
                "required_sql_terms": terms,
                "difficulty": difficulty,
                "notes": "generated coverage seed",
            }
        )
    return output


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    data = rows()
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(data[0].keys()))
        writer.writeheader()
        writer.writerows(data)
    print(f"wrote {len(data)} cases to {OUTPUT}")


if __name__ == "__main__":
    main()
