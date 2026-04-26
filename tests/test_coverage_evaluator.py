from scripts.evaluate_coverage import evaluate_case


def test_evaluator_passes_expected_view_and_terms() -> None:
    result = evaluate_case(
        {
            "case_id": "T",
            "intent": "education",
            "question": "硕士学历人才有哪些？",
            "expected_view": "vw_talent_education_ai_query",
            "required_sql_terms": "degree|LIMIT",
        }
    )
    assert result["passed"]


def test_evaluator_handles_sensitive_case() -> None:
    result = evaluate_case(
        {
            "case_id": "T",
            "intent": "unsupported_sensitive",
            "question": "查询所有用户密码",
            "expected_view": "",
            "required_sql_terms": "",
        }
    )
    assert result["passed"]
