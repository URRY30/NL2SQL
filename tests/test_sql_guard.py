from app.services.sql_guard import SqlGuard


PROFILES = [
    {
        "table_name": "vw_talent_ai_query",
        "columns": [
            {"name": "dept_name"},
            {"name": "q_value"},
            {"name": "risk_level"},
            {"name": "talent_count"},
        ],
    }
]


def test_guard_allows_whitelisted_select() -> None:
    guard = SqlGuard(["vw_talent_ai_query"], 100)
    result = guard.validate(
        "SELECT dept_name, COUNT(*) AS talent_count FROM vw_talent_ai_query GROUP BY dept_name LIMIT 100;",
        PROFILES,
    )
    assert result["status"] == "passed"


def test_guard_allows_schema_qualified_view() -> None:
    guard = SqlGuard(["vw_talent_ai_query"], 100)
    result = guard.validate(
        "SELECT public.vw_talent_ai_query.dept_name, COUNT(*) AS talent_count "
        "FROM public.vw_talent_ai_query "
        "GROUP BY public.vw_talent_ai_query.dept_name LIMIT 100;",
        PROFILES,
    )
    assert result["status"] == "passed"


def test_guard_blocks_write_keyword() -> None:
    guard = SqlGuard(["vw_talent_ai_query"], 100)
    result = guard.validate("DELETE FROM vw_talent_ai_query;", PROFILES)
    assert result["status"] == "blocked"


def test_guard_blocks_non_whitelisted_table() -> None:
    guard = SqlGuard(["vw_talent_ai_query"], 100)
    result = guard.validate("SELECT id FROM users LIMIT 100;", PROFILES)
    assert result["status"] == "blocked"


def test_guard_requires_limit_for_grouped_query() -> None:
    guard = SqlGuard(["vw_talent_ai_query"], 100)
    result = guard.validate(
        "SELECT dept_name, COUNT(*) AS talent_count FROM vw_talent_ai_query GROUP BY dept_name;",
        PROFILES,
    )
    assert result["status"] == "blocked"
