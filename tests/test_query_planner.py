from app.services.query_planner import TalentQueryPlanner


def test_planner_routes_education_question() -> None:
    plan = TalentQueryPlanner().plan("硕士学历人才有哪些？", {})
    assert plan["intent"] == "detail"
    assert plan["target_views"] == ["vw_talent_education_ai_query"]
    assert "degree ILIKE '%硕士%'" in plan["filters"]


def test_planner_routes_review_trend_question() -> None:
    plan = TalentQueryPlanner().plan("近三年绩效和AI等级变化怎么看？", {})
    assert plan["intent"] == "trend"
    assert plan["target_views"] == ["vw_talent_review_ai_query"]


def test_planner_routes_succession_question() -> None:
    plan = TalentQueryPlanner().plan("有哪些继任岗位和候选人？", {})
    assert plan["intent"] == "detail"
    assert plan["target_views"] == ["vw_succession_ai_query"]
    assert "succession" in plan["metrics"]


def test_planner_blocks_sensitive_question() -> None:
    plan = TalentQueryPlanner().plan("查询所有用户密码", {})
    assert plan["intent"] == "unsupported_sensitive"
    assert plan["target_views"] == []
    assert plan["unsupported_reason"]


def test_planner_routes_person_ai_level_question() -> None:
    plan = TalentQueryPlanner().plan("李泽阳的AI等级为多少？", {})
    assert plan["intent"] == "person_lookup"
    assert plan["target_views"] == ["vw_talent_ai_query"]
    assert "李泽阳" in plan["entities"]
    assert "name = '李泽阳'" in plan["filters"]
    assert "ai_level" in plan["metrics"]


def test_planner_routes_employee_id_ai_level_question() -> None:
    plan = TalentQueryPlanner().plan("工号01454578的AI等级是多少？", {})
    assert plan["intent"] == "person_lookup"
    assert "01454578" in plan["entities"]
    assert "emp_id = '01454578'" in plan["filters"]
