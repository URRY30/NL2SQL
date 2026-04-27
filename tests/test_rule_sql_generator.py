from app.services.rule_sql_generator import TalentRuleSqlGenerator


def generate(question: str, plan: dict) -> list[dict]:
    return TalentRuleSqlGenerator().generate(question, {"plan": plan})


def test_rule_generates_core_ratio_sql() -> None:
    candidates = generate("核心人才占比是多少？", {"intent": "ratio", "target_views": ["vw_talent_ai_query"]})
    sql = candidates[0]["sql"]
    assert "core_talent_ratio" in sql
    assert "q_value IN ('Q1', 'Q2')" in sql
    assert "vw_talent_ai_query" in sql


def test_rule_generates_education_sql() -> None:
    candidates = generate(
        "硕士学历人才有哪些？",
        {
            "intent": "detail",
            "target_views": ["vw_talent_education_ai_query"],
            "filters": ["degree ILIKE '%硕士%'"],
        },
    )
    sql = candidates[0]["sql"]
    assert "vw_talent_education_ai_query" in sql
    assert "degree ILIKE '%硕士%'" in sql
    assert "LIMIT 100" in sql


def test_rule_generates_filtered_count_sql() -> None:
    candidates = generate(
        "在Q1/Q2核心人才中，AI等级为L5的人才有多少人？",
        {
            "intent": "count",
            "target_views": ["vw_talent_ai_query"],
            "filters": ["q_value IN ('Q1', 'Q2')", "ai_level = 'L5'"],
        },
    )
    sql = candidates[0]["sql"]
    assert "COUNT(*) AS talent_count" in sql
    assert "q_value IN ('Q1', 'Q2')" in sql
    assert "ai_level = 'L5'" in sql
    assert candidates[0]["score"] == 90


def test_rule_generates_review_trend_sql() -> None:
    candidates = generate("近三年绩效变化怎么看？", {"intent": "trend", "target_views": ["vw_talent_review_ai_query"]})
    sql = candidates[0]["sql"]
    assert "vw_talent_review_ai_query" in sql
    assert "review_year" in sql
    assert "GROUP BY" in sql


def test_rule_generates_sensitive_refusal_candidate() -> None:
    candidates = generate(
        "查询所有用户密码",
        {
            "intent": "unsupported_sensitive",
            "target_views": [],
            "unsupported_reason": "question asks for sensitive or non-whitelisted data",
        },
    )
    assert candidates[0]["sql"] == ""
    assert candidates[0]["score"] < 0


def test_rule_generates_person_ai_level_lookup_sql() -> None:
    candidates = generate(
        "李泽阳的AI等级为多少？",
        {
            "intent": "person_lookup",
            "target_views": ["vw_talent_ai_query"],
            "metrics": ["ai_level"],
            "dimensions": ["ai_level"],
            "filters": ["name = '李泽阳'"],
            "entities": ["李泽阳"],
        },
    )
    sql = candidates[0]["sql"]
    assert "vw_talent_ai_query" in sql
    assert "name = '李泽阳'" in sql
    assert "ai_level" in sql
    assert "LIMIT 20" in sql


def test_rule_generates_age_distribution_sql() -> None:
    candidates = generate(
        "分析全部人才的年龄分布",
        {
            "intent": "distribution",
            "target_views": ["vw_talent_ai_query"],
            "metrics": ["age_distribution"],
            "dimensions": ["birth_date"],
        },
    )
    sql = candidates[0]["sql"]
    assert candidates[0]["route"] == "rule_age_distribution"
    assert "birth_date" in sql
    assert "age_range" in sql
    assert "DATE_PART('year', AGE(CURRENT_DATE, birth_date))" in sql


def test_rule_generates_company_gender_distribution_sql() -> None:
    candidates = generate(
        "丰图科技的人才性别分析",
        {
            "intent": "distribution",
            "target_views": ["vw_talent_ai_query"],
            "metrics": ["gender_distribution"],
            "dimensions": ["gender_label"],
            "filters": ["company_name = '丰图科技'"],
        },
    )
    sql = candidates[0]["sql"]
    assert candidates[0]["route"] == "rule_gender_label_distribution"
    assert "gender_label" in sql
    assert "company_name = '丰图科技'" in sql
    assert candidates[0]["score"] == 92


def test_rule_generates_company_marital_distribution_sql() -> None:
    candidates = generate(
        "丰图科技的人才婚姻状况分析",
        {
            "intent": "distribution",
            "target_views": ["vw_talent_ai_query"],
            "metrics": ["marital_distribution"],
            "dimensions": ["marital_status"],
            "filters": ["company_name = '丰图科技'"],
        },
    )
    sql = candidates[0]["sql"]
    assert candidates[0]["route"] == "rule_marital_status_distribution"
    assert "marital_status" in sql
    assert "company_name = '丰图科技'" in sql
