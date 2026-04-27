-- Second-stage whitelist views for NL2SQL Data Agent v2.
-- Run this script in the talent PostgreSQL database after the base schema is ready.
--
-- The Data Agent should query these views instead of raw business/system tables.

DROP VIEW IF EXISTS public.vw_org_position_ai_query;
DROP VIEW IF EXISTS public.vw_succession_ai_query;
DROP VIEW IF EXISTS public.vw_talent_tag_ai_query;
DROP VIEW IF EXISTS public.vw_talent_project_ai_query;
DROP VIEW IF EXISTS public.vw_talent_career_ai_query;
DROP VIEW IF EXISTS public.vw_talent_education_ai_query;
DROP VIEW IF EXISTS public.vw_talent_review_ai_query;
DROP VIEW IF EXISTS public.vw_talent_ai_query;

CREATE OR REPLACE VIEW public.vw_talent_ai_query AS
SELECT
    t.id,
    t.emp_id,
    t.name,
    c.company_name,
    d.dept_name,
    d.path AS dept_path,
    jc.full_path AS job_path,
    t.job_title,
    t.job_level,
    t.q_value,
    t.ai_level,
    t.performance_level,
    t.potential_level,
    t.stability_level,
    t.risk_level,
    t.is_key_talent,
    t.is_succession_candidate,
    t.employee_status,
    t.hire_date,
    t.highest_degree,
    t.school_name,
    t.major_name,
    t.birth_date,
    t.gender,
    CASE
        WHEN t.gender = 'male' THEN U&'\7537'
        WHEN t.gender = 'female' THEN U&'\5973'
        WHEN t.gender = 'other' THEN U&'\5176\4ED6'
        ELSE U&'\672A\77E5'
    END AS gender_label,
    t.marital_status,
    t.nationality_native_place,
    t.job_grade_track,
    t.job_grade_level,
    t.manager_id,
    t.dotted_manager_id,
    tp.basic_info_jsonb ->> 'location' AS location
FROM public.talents t
LEFT JOIN public.companies c ON c.id = t.company_id
LEFT JOIN public.departments d ON d.id = t.dept_id
LEFT JOIN public.job_catalogs jc ON jc.id = t.job_catalog_id
LEFT JOIN public.talent_profiles tp ON tp.talent_id = t.id
WHERE t.is_deleted = FALSE;

COMMENT ON VIEW public.vw_talent_ai_query IS 'Read-only whitelist view for basic talent NL2SQL queries.';

CREATE OR REPLACE VIEW public.vw_talent_review_ai_query AS
SELECT
    r.id AS review_id,
    t.id AS talent_id,
    t.emp_id,
    t.name,
    c.company_name,
    d.dept_name,
    t.job_title,
    r.review_period,
    r.review_year,
    r.performance_level,
    r.potential_level,
    r.q_value,
    r.ai_level,
    r.potential_score,
    r.stability_level,
    NULL::numeric AS stability_score,
    NULL::numeric AS nine_box_x,
    NULL::numeric AS nine_box_y,
    NULL::varchar AS review_source,
    t.employee_status
FROM public.talent_reviews r
JOIN public.talents t ON t.id = r.talent_id
LEFT JOIN public.companies c ON c.id = t.company_id
LEFT JOIN public.departments d ON d.id = t.dept_id
WHERE t.is_deleted = FALSE;

COMMENT ON VIEW public.vw_talent_review_ai_query IS 'Read-only whitelist view for review, trend, performance and potential NL2SQL queries.';

CREATE OR REPLACE VIEW public.vw_talent_education_ai_query AS
SELECT
    e.id AS education_id,
    t.id AS talent_id,
    t.emp_id,
    t.name,
    c.company_name,
    d.dept_name,
    t.job_title,
    t.q_value,
    t.ai_level,
    t.employee_status,
    e.school_name,
    e.degree,
    e.major,
    e.start_date,
    e.end_date,
    e.period_text,
    e.learning_mode,
    e.is_highest
FROM public.talent_educations e
JOIN public.talents t ON t.id = e.talent_id
LEFT JOIN public.companies c ON c.id = t.company_id
LEFT JOIN public.departments d ON d.id = t.dept_id
WHERE t.is_deleted = FALSE;

COMMENT ON VIEW public.vw_talent_education_ai_query IS 'Read-only whitelist view for education, degree, school and major NL2SQL queries.';

CREATE OR REPLACE VIEW public.vw_talent_career_ai_query AS
SELECT
    ca.id AS career_id,
    t.id AS talent_id,
    t.emp_id,
    t.name,
    c.company_name,
    d.dept_name,
    t.job_title,
    t.q_value,
    t.ai_level,
    t.employee_status,
    ca.company_name AS career_company_name,
    ca.dept_name AS career_dept_name,
    ca.position_name AS career_position_name,
    ca.start_date,
    ca.end_date,
    ca.period_text,
    ca.is_internal
FROM public.talent_careers ca
JOIN public.talents t ON t.id = ca.talent_id
LEFT JOIN public.companies c ON c.id = t.company_id
LEFT JOIN public.departments d ON d.id = t.dept_id
WHERE t.is_deleted = FALSE;

COMMENT ON VIEW public.vw_talent_career_ai_query IS 'Read-only whitelist view for career and work-history NL2SQL queries.';

CREATE OR REPLACE VIEW public.vw_talent_project_ai_query AS
SELECT
    p.id AS project_id,
    t.id AS talent_id,
    t.emp_id,
    t.name,
    c.company_name,
    d.dept_name,
    t.job_title,
    t.q_value,
    t.ai_level,
    t.employee_status,
    p.project_name,
    p.role_name,
    NULL::varchar AS industry,
    p.start_date,
    p.end_date,
    p.period_text,
    NULL::jsonb AS keywords_jsonb
FROM public.talent_projects p
JOIN public.talents t ON t.id = p.talent_id
LEFT JOIN public.companies c ON c.id = t.company_id
LEFT JOIN public.departments d ON d.id = t.dept_id
WHERE t.is_deleted = FALSE;

COMMENT ON VIEW public.vw_talent_project_ai_query IS 'Read-only whitelist view for project and experience NL2SQL queries.';

CREATE OR REPLACE VIEW public.vw_talent_tag_ai_query AS
SELECT
    tt.id AS talent_tag_id,
    t.id AS talent_id,
    t.emp_id,
    t.name,
    c.company_name,
    d.dept_name,
    t.job_title,
    t.q_value,
    t.ai_level,
    t.employee_status,
    tg.tag_name,
    tg.tag_type,
    tg.category_l1,
    tg.category_l2,
    tg.source AS tag_source,
    NULL::numeric AS score
FROM public.talent_tags tt
JOIN public.talents t ON t.id = tt.talent_id
JOIN public.tags tg ON tg.id = tt.tag_id
LEFT JOIN public.companies c ON c.id = t.company_id
LEFT JOIN public.departments d ON d.id = t.dept_id
WHERE t.is_deleted = FALSE
  AND tg.status = 'active';

COMMENT ON VIEW public.vw_talent_tag_ai_query IS 'Read-only whitelist view for tag, skill and capability NL2SQL queries.';

DO $$
BEGIN
    IF to_regclass('public.succession_plans') IS NOT NULL
       AND to_regclass('public.positions') IS NOT NULL THEN
        EXECUTE $view$
            CREATE OR REPLACE VIEW public.vw_succession_ai_query AS
            SELECT
                sp.id AS succession_plan_id,
                pos.id AS position_id,
                pos.position_name,
                pos.position_code,
                pos.job_level,
                t.id AS talent_id,
                t.emp_id,
                t.name,
                c.company_name,
                d.dept_name,
                t.job_title,
                t.q_value,
                t.ai_level,
                t.employee_status,
                sp.review_period,
                sp.readiness_level,
                sp.risk_level,
                sp.note
            FROM public.succession_plans sp
            JOIN public.positions pos ON pos.id = sp.position_id
            JOIN public.talents t ON t.id = sp.talent_id
            LEFT JOIN public.companies c ON c.id = t.company_id
            LEFT JOIN public.departments d ON d.id = t.dept_id
            WHERE t.is_deleted = FALSE
        $view$;
    ELSE
        EXECUTE $view$
            CREATE OR REPLACE VIEW public.vw_succession_ai_query AS
            SELECT
                NULL::uuid AS succession_plan_id,
                NULL::uuid AS position_id,
                NULL::varchar AS position_name,
                NULL::varchar AS position_code,
                NULL::varchar AS job_level,
                NULL::uuid AS talent_id,
                NULL::varchar AS emp_id,
                NULL::varchar AS name,
                NULL::varchar AS company_name,
                NULL::varchar AS dept_name,
                NULL::varchar AS job_title,
                NULL::varchar AS q_value,
                NULL::varchar AS ai_level,
                NULL::varchar AS employee_status,
                NULL::varchar AS review_period,
                NULL::varchar AS readiness_level,
                NULL::varchar AS risk_level,
                NULL::text AS note
            WHERE FALSE
        $view$;
    END IF;
END $$;

COMMENT ON VIEW public.vw_succession_ai_query IS 'Read-only whitelist view for succession planning NL2SQL queries.';

DO $$
BEGIN
    IF to_regclass('public.positions') IS NOT NULL THEN
        EXECUTE $view$
            CREATE OR REPLACE VIEW public.vw_org_position_ai_query AS
            SELECT
                pos.id AS position_id,
                c.company_name,
                d.dept_name,
                d.path AS dept_path,
                jc.full_path AS job_path,
                pos.position_code,
                pos.position_name,
                pos.job_level,
                pos.is_manager,
                pos.headcount,
                pos.status
            FROM public.positions pos
            LEFT JOIN public.companies c ON c.id = pos.company_id
            LEFT JOIN public.departments d ON d.id = pos.dept_id
            LEFT JOIN public.job_catalogs jc ON jc.id = pos.job_catalog_id
        $view$;
    ELSE
        EXECUTE $view$
            CREATE OR REPLACE VIEW public.vw_org_position_ai_query AS
            SELECT
                NULL::uuid AS position_id,
                NULL::varchar AS company_name,
                NULL::varchar AS dept_name,
                NULL::text AS dept_path,
                NULL::varchar AS job_path,
                NULL::varchar AS position_code,
                NULL::varchar AS position_name,
                NULL::varchar AS job_level,
                NULL::boolean AS is_manager,
                NULL::integer AS headcount,
                NULL::varchar AS status
            WHERE FALSE
        $view$;
    END IF;
END $$;

COMMENT ON VIEW public.vw_org_position_ai_query IS 'Read-only whitelist view for organization, position and headcount NL2SQL queries.';
