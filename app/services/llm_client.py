from __future__ import annotations

import asyncio
import json
import re
import urllib.error
import urllib.request
from typing import Any

from app.core.config import Settings


class BigModelSqlClient:
    def __init__(self, settings: Settings):
        self.api_key = settings.bigmodel_api_key
        self.base_url = settings.bigmodel_base_url
        self.model = settings.bigmodel_model
        self.timeout = settings.bigmodel_timeout
        self.temperature = settings.bigmodel_temperature
        self.last_error = ""

    @property
    def configured(self) -> bool:
        invalid = {
            "",
            "REPLACE_ME",
            "YOUR_API_KEY",
            "<token>",
            "changeme",
            "replace-with-your-key",
            "replace-with-your-dashscope-key",
        }
        return self.api_key not in invalid and bool(self.base_url and self.model)

    async def generate_sql(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._generate_sql_sync, question, context)

    def _generate_sql_sync(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        self.last_error = ""
        if not self.configured:
            self.last_error = "BIGMODEL_API_KEY is not configured"
            return {"ok": False, "sql": "", "error": self.last_error, "raw": ""}

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(question, context)},
            ],
            "stream": False,
            "temperature": self.temperature,
        }
        request = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            self.last_error = str(exc)
            return {"ok": False, "sql": "", "error": self.last_error, "raw": ""}
        except Exception as exc:
            self.last_error = str(exc)
            return {"ok": False, "sql": "", "error": self.last_error, "raw": ""}

        try:
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            self.last_error = f"unexpected model response: {exc}"
            return {"ok": False, "sql": "", "error": self.last_error, "raw": body}

        sql = extract_sql(content)
        if not sql:
            self.last_error = "model did not return SELECT SQL"
            return {"ok": False, "sql": "", "error": self.last_error, "raw": content}
        return {"ok": True, "sql": sql, "error": "", "raw": content}

    def _system_prompt(self) -> str:
        return (
            "你是企业 NL2SQL Data Agent 的 SQL 生成器。"
            "只能输出一条 PostgreSQL 兼容的只读 SELECT SQL。"
            "必须只使用给定表/视图和字段，不要编造字段。"
            "不要输出解释，不要输出 Markdown。"
            "除非用户明确要求汇总且 SQL 返回聚合结果，否则必须添加 LIMIT。"
        )

    def _user_prompt(self, question: str, context: dict[str, Any]) -> str:
        compact_context = {
            "topic": context.get("topic"),
            "tables": context.get("tables", []),
            "metrics": context.get("metrics", []),
            "column_aliases": context.get("column_aliases", []),
            "enum_mappings": context.get("enum_mappings", []),
            "business_rules": context.get("business_rules", []),
            "query_plan": context.get("plan", {}),
            "sql_cases": context.get("sql_cases", [])[:8],
        }
        return (
            f"用户问题：{question}\n\n"
            "可用知识资产如下，请严格遵守：\n"
            f"{json.dumps(compact_context, ensure_ascii=False, indent=2)}\n\n"
            "输出要求：只输出 SQL。"
        )


class OllamaSqlClient:
    def __init__(self, settings: Any):
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_model
        self.timeout = settings.ollama_timeout
        self.temperature = settings.ollama_temperature
        self.last_error = ""

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model)

    async def generate_sql(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._generate_sql_sync, question, context)

    def _generate_sql_sync(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        self.last_error = ""
        if not self.configured:
            self.last_error = "OLLAMA_BASE_URL or OLLAMA_MODEL is not configured"
            return {"ok": False, "sql": "", "error": self.last_error, "raw": ""}

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(question, context)},
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 1024,
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            self.last_error = str(exc)
            return {"ok": False, "sql": "", "error": self.last_error, "raw": ""}
        except Exception as exc:
            self.last_error = str(exc)
            return {"ok": False, "sql": "", "error": self.last_error, "raw": ""}

        try:
            data = json.loads(body)
            content = data["message"]["content"]
        except Exception as exc:
            self.last_error = f"unexpected Ollama response: {exc}"
            return {"ok": False, "sql": "", "error": self.last_error, "raw": body}

        sql = extract_sql(content)
        if not sql:
            self.last_error = "Ollama did not return SELECT SQL"
            return {"ok": False, "sql": "", "error": self.last_error, "raw": content}
        return {"ok": True, "sql": sql, "error": "", "raw": content}

    def _system_prompt(self) -> str:
        return (
            "你是企业 NL2SQL Data Agent 的 PostgreSQL SQL 生成器。\n"
            "你必须只输出一条只读 SELECT SQL，不要输出解释，不要输出 Markdown，不要输出思考过程。\n"
            "只能使用用户上下文中给定的表/视图和字段，禁止编造字段。\n"
            "禁止 INSERT、UPDATE、DELETE、DROP、ALTER、CREATE、TRUNCATE。\n"
            "禁止 SELECT *。\n"
            "非标量聚合查询必须添加 LIMIT 100。\n"
            "如果问题涉及核心人才，默认使用 q_value IN ('Q1', 'Q2')。\n"
            "如果问题涉及高风险，默认使用 risk_level = 'high'。\n"
            "如果问题涉及继任候选，默认使用 is_succession_candidate = TRUE。"
        )

    def _user_prompt(self, question: str, context: dict[str, Any]) -> str:
        compact_context = {
            "topic": context.get("topic"),
            "tables": context.get("tables", []),
            "metrics": context.get("metrics", []),
            "column_aliases": context.get("column_aliases", []),
            "enum_mappings": context.get("enum_mappings", []),
            "business_rules": context.get("business_rules", []),
            "query_plan": context.get("plan", {}),
            "sql_cases": context.get("sql_cases", [])[:8],
        }
        return (
            f"用户问题：{question}\n\n"
            "可用知识资产如下，请严格遵守：\n"
            f"{json.dumps(compact_context, ensure_ascii=False, indent=2)}\n\n"
            "现在只输出 SQL，不要解释。"
        )


class DashScopeSqlClient:
    def __init__(self, settings: Any):
        self.api_key = settings.dashscope_api_key
        self.base_url = settings.dashscope_base_url.rstrip("/")
        self.model = settings.dashscope_model
        self.timeout = settings.dashscope_timeout
        self.temperature = settings.dashscope_temperature
        self.enable_thinking = settings.dashscope_enable_thinking
        self.last_error = ""

    @property
    def configured(self) -> bool:
        invalid = {
            "",
            "REPLACE_ME",
            "YOUR_API_KEY",
            "<token>",
            "changeme",
            "replace-with-your-key",
            "replace-with-your-dashscope-key",
        }
        return self.api_key not in invalid and bool(self.base_url and self.model)

    async def generate_sql(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        return await asyncio.to_thread(self._generate_sql_sync, question, context)

    def _generate_sql_sync(self, question: str, context: dict[str, Any]) -> dict[str, Any]:
        self.last_error = ""
        if not self.configured:
            self.last_error = "DASHSCOPE_API_KEY is not configured"
            return {"ok": False, "sql": "", "error": self.last_error, "raw": ""}

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_prompt(question, context)},
            ],
            "stream": False,
            "temperature": self.temperature,
            "enable_thinking": self.enable_thinking,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.URLError as exc:
            self.last_error = str(exc)
            return {"ok": False, "sql": "", "error": self.last_error, "raw": ""}
        except Exception as exc:
            self.last_error = str(exc)
            return {"ok": False, "sql": "", "error": self.last_error, "raw": ""}

        try:
            data = json.loads(body)
            message = data["choices"][0]["message"]
            content = message.get("content") or ""
        except Exception as exc:
            self.last_error = f"unexpected DashScope response: {exc}"
            return {"ok": False, "sql": "", "error": self.last_error, "raw": body}

        sql = extract_sql(content)
        if not sql:
            self.last_error = "DashScope did not return SELECT SQL"
            return {"ok": False, "sql": "", "error": self.last_error, "raw": content}
        return {"ok": True, "sql": sql, "error": "", "raw": content}

    def _system_prompt(self) -> str:
        return (
            "你是人才管理系统 NL2SQL Data Agent 的 PostgreSQL SQL 生成器。\n"
            "你必须只输出一条只读 SELECT SQL，不要输出解释，不要输出 Markdown，不要输出思考过程。\n"
            "只能使用用户上下文中给定的表/视图和字段，禁止编造字段。\n"
            "禁止 INSERT、UPDATE、DELETE、DROP、ALTER、CREATE、TRUNCATE。\n"
            "禁止 SELECT *。\n"
            "非标量聚合查询必须添加 LIMIT 100。\n"
            "如果问题涉及核心人才，默认使用 q_value IN ('Q1', 'Q2')。\n"
            "如果问题涉及高风险，默认使用 risk_level = 'high'。\n"
            "如果问题涉及继任候选，默认使用 is_succession_candidate = TRUE。"
        )

    def _user_prompt(self, question: str, context: dict[str, Any]) -> str:
        compact_context = {
            "topic": context.get("topic"),
            "tables": context.get("tables", []),
            "metrics": context.get("metrics", []),
            "column_aliases": context.get("column_aliases", []),
            "enum_mappings": context.get("enum_mappings", []),
            "business_rules": context.get("business_rules", []),
            "query_plan": context.get("plan", {}),
            "sql_cases": context.get("sql_cases", [])[:8],
        }
        return (
            f"用户问题：{question}\n\n"
            "可用知识资产如下，请严格遵守：\n"
            f"{json.dumps(compact_context, ensure_ascii=False, indent=2)}\n\n"
            "现在只输出 SQL，不要解释。"
        )


def create_sql_client(settings: Any) -> Any:
    provider = (settings.llm_provider or "").strip().lower()
    if provider == "ollama":
        return OllamaSqlClient(settings)
    if provider in {"dashscope", "aliyun", "aliyun_dashscope"}:
        return DashScopeSqlClient(settings)
    return BigModelSqlClient(settings)


def extract_sql(content: str) -> str:
    stripped = content.strip()
    stripped = re.sub(r"<think>.*?</think>", "", stripped, flags=re.IGNORECASE | re.DOTALL).strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    select = re.search(r"\bSELECT\b.+", stripped, flags=re.IGNORECASE | re.DOTALL)
    if select:
        stripped = select.group(0).strip()
    stripped = stripped.rstrip(";").strip()
    return f"{stripped};" if stripped.upper().startswith("SELECT") else ""
