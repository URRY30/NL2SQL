from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.knowledge_store import KnowledgeStore
from app.services.llm_client import create_sql_client
from app.services.metadata import MetadataService
from app.services.query_planner import TalentQueryPlanner
from app.services.rule_sql_generator import TalentRuleSqlGenerator
from app.services.sql_executor import SqlExecutor
from app.services.sql_guard import SqlGuard


class NL2SQLAgent:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.metadata = MetadataService(settings.db_schema, settings.allowed_views)
        self.knowledge = KnowledgeStore()
        self.llm = create_sql_client(settings)
        self.planner = TalentQueryPlanner()
        self.rule_generator = TalentRuleSqlGenerator()
        self.guard = SqlGuard(settings.allowed_views, settings.sql_max_limit)
        self.executor = SqlExecutor(settings.sql_timeout_seconds)

    async def health(self, session: AsyncSession | None = None) -> dict[str, Any]:
        return {
            "service": self.settings.app_name,
            "status": "ok",
            "default_topic_id": self.settings.default_topic_id,
            "allowed_views": self.settings.allowed_views,
            "llm_provider": self.settings.llm_provider,
            "llm_model": getattr(self.llm, "model", ""),
            "llm_configured": self.llm.configured,
        }

    async def bootstrap(self, session: AsyncSession) -> dict[str, Any]:
        profiles = []
        for view in self.settings.allowed_views:
            try:
                profiles.append(await self.metadata.profile_view(session, view))
            except Exception as exc:
                profiles.append({"table_name": view, "status": "error", "error": str(exc)})
        return {
            "topics": self.knowledge.list_topics(),
            "datasets": profiles,
            "guard": {
                "allowed_views": self.settings.allowed_views,
                "max_limit": self.settings.sql_max_limit,
            },
        }

    async def dataset_profile(self, session: AsyncSession, dataset_id: str) -> dict[str, Any]:
        view_name = dataset_id.removeprefix("ds_")
        return await self.metadata.profile_view(session, view_name, use_cache=False)

    async def generate_sql(self, session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        question = str(payload.get("question") or "").strip()
        if not question:
            raise ValueError("question is required")
        topic_id = payload.get("topic_id") or self.settings.default_topic_id
        profiles = await self._load_profiles(session)
        context = self.knowledge.build_context(topic_id, question, profiles)
        context["plan"] = self.planner.plan(question, context)

        candidates: list[dict[str, Any]] = []
        rule_candidates = [
            {"candidate_id": self._new_id("sql"), **item}
            for item in self.rule_generator.generate(question, context)
        ]
        evaluated_rules = [self._evaluate_candidate(candidate, profiles) for candidate in rule_candidates]
        confident_rules = []
        llm_skipped = context["plan"].get("intent") == "unsupported_sensitive"
        llm_result: dict[str, Any] = {
            "ok": False,
            "error": "skipped for sensitive question",
        }

        if not llm_skipped:
            llm_result = await self.llm.generate_sql(question, context)
            if llm_result["ok"]:
                candidates.append(
                    {
                        "candidate_id": self._new_id("sql"),
                        "route": "llm_direct",
                        "source": "llm",
                        "score": 120,
                        "sql": llm_result["sql"],
                        "notes": "LLM generated SQL",
                    }
                )
            else:
                candidates.append(
                    {
                        "candidate_id": self._new_id("sql"),
                        "route": "llm_direct",
                        "source": "llm",
                        "score": -100,
                        "sql": "",
                        "notes": f"LLM failed: {llm_result.get('error', 'unknown error')}",
                        "guard": {
                            "status": "blocked",
                            "checks": [
                                {
                                    "name": "llm_generation",
                                    "status": "failed",
                                    "message": llm_result.get("error", "unknown error"),
                                }
                            ],
                            "referenced_tables": [],
                        },
                        "selected": False,
                        "raw": llm_result.get("raw", ""),
                    }
                )

        evaluated = [self._evaluate_candidate(candidate, profiles) for candidate in candidates]
        evaluated.extend(evaluated_rules)
        passed = [candidate for candidate in evaluated if candidate["guard"]["status"] == "passed"]
        selected = max(passed or evaluated, key=lambda item: item["score"])
        selected["selected"] = True

        return {
            "session_id": self._new_id("qs"),
            "topic": context["topic"],
            "plan": context["plan"],
            "question": question,
            "candidates": evaluated,
            "knowledge_hits": self._knowledge_hits(context),
            "trace": [
                {"step": "topic_detect", "status": "completed", "summary": f"topic={topic_id}"},
                {
                    "step": "query_plan",
                    "status": "completed",
                    "summary": f"intent={context['plan']['intent']}, views={','.join(context['plan']['target_views'])}",
                },
                {"step": "metadata_profile", "status": "completed", "summary": f"{len(profiles)} profiles loaded"},
                {
                    "step": "llm_generation",
                    "status": "skipped" if llm_skipped else ("completed" if llm_result["ok"] else "failed"),
                    "summary": "sensitive question skipped LLM" if llm_skipped else ("LLM SQL candidate generated" if llm_result["ok"] else llm_result.get("error", "unknown error")),
                },
                {"step": "sql_generation", "status": "completed", "summary": f"{len(evaluated)} candidates generated"},
            ],
        }

    async def execute_sql(self, session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        sql = str(payload.get("sql") or "").strip()
        if not sql:
            raise ValueError("sql is required")
        profiles = await self._load_profiles(session)
        sql = self.guard.ensure_limit(sql)
        guard = self.guard.validate(sql, profiles)
        result: dict[str, Any] | None = None
        if guard["status"] == "passed":
            result = await self.executor.execute(session, sql)
        return {
            "sql": sql,
            "guard": guard,
            "execution": result,
            "trace": [
                {"step": "sql_guard", "status": guard["status"], "summary": guard["checks"][-1]["message"]},
                {"step": "sql_execute", "status": "completed" if result else "skipped", "summary": "PostgreSQL execution"},
            ],
        }

    async def service_query(self, session: AsyncSession, payload: dict[str, Any]) -> dict[str, Any]:
        generated = await self.generate_sql(session, payload)
        selected = next(candidate for candidate in generated["candidates"] if candidate["selected"])
        return_mode = payload.get("return_mode", "sql_result_trace")
        execute = bool(payload.get("execute", True))

        execution = None
        guard = selected["guard"]
        if execute and return_mode in {"sql_result", "sql_result_trace"} and guard["status"] == "passed":
            executed = await self.execute_sql(session, {"sql": selected["sql"]})
            guard = executed["guard"]
            execution = executed["execution"]

        response: dict[str, Any] = {
            "session_id": generated["session_id"],
            "topic": generated["topic"],
            "plan": generated["plan"],
            "question": generated["question"],
            "sql": selected["sql"],
            "risk": {
                "guard_status": guard["status"],
                "warnings": [check for check in guard["checks"] if check["status"] != "passed"],
            },
        }
        if return_mode in {"sql_result", "sql_result_trace"}:
            response["result"] = execution
        if return_mode == "sql_result_trace":
            response["trace"] = generated["trace"]
            response["knowledge_hits"] = generated["knowledge_hits"]
            response["candidates"] = generated["candidates"]
        return response

    def _evaluate_candidate(self, candidate: dict[str, Any], profiles: list[dict[str, Any]]) -> dict[str, Any]:
        if not candidate.get("sql"):
            return candidate
        sql = self.guard.ensure_limit(candidate["sql"])
        guard = self.guard.validate(sql, profiles)
        return {
            **candidate,
            "sql": sql,
            "guard": guard,
            "selected": False,
            "score": candidate["score"] + (20 if guard["status"] == "passed" else -50),
        }

    def _knowledge_hits(self, context: dict[str, Any]) -> list[dict[str, Any]]:
        hits = []
        for key in ["metrics", "enum_mappings", "column_aliases", "business_rules"]:
            for item in context.get(key, [])[:8]:
                hits.append({"type": key.rstrip("s"), "name": item.get("name") or item.get("column_name") or key})
        return hits

    async def _load_profiles(self, session: AsyncSession) -> list[dict[str, Any]]:
        profiles = []
        for view in self.settings.allowed_views:
            try:
                profiles.append(await self.metadata.profile_view(session, view))
            except Exception:
                continue
        if not profiles:
            raise ValueError("no registered query views are available")
        return profiles

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"
