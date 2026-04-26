-- First-stage whitelist view for NL2SQL Data Agent v2.
-- Run this in the talent PostgreSQL database before calling /api/bootstrap.
--
-- The Data Agent should query this view instead of raw business/system tables.

CREATE OR REPLACE VIEW public.vw_talent_ai_query AS
SELECT
    t.id,
    t.emp_id,
    t.name,
    c.company_name,
    d.dept_name,
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
    t.employee_status
FROM public.talents t
LEFT JOIN public.companies c ON c.id = t.company_id
LEFT JOIN public.departments d ON d.id = t.dept_id
LEFT JOIN public.job_catalogs jc ON jc.id = t.job_catalog_id
WHERE t.is_deleted = FALSE;

COMMENT ON VIEW public.vw_talent_ai_query IS 'Read-only whitelist view for NL2SQL talent queries.';
