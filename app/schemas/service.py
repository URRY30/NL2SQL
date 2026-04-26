from typing import Any, Literal

from pydantic import BaseModel, Field


class ServiceUser(BaseModel):
    id: str | None = None
    name: str | None = None
    org: str | None = None
    data_scope: dict[str, Any] | None = None


class ServiceQueryRequest(BaseModel):
    client_id: str | None = None
    topic_id: str | None = None
    question: str = Field(min_length=1, max_length=2000)
    user: ServiceUser | None = None
    return_mode: Literal["sql_only", "sql_result", "sql_result_trace"] = "sql_result_trace"
    execute: bool = True


class GenerateSqlRequest(BaseModel):
    topic_id: str | None = None
    question: str = Field(min_length=1, max_length=2000)


class ExecuteSqlRequest(BaseModel):
    topic_id: str | None = None
    sql: str = Field(min_length=1, max_length=10000)
    return_mode: Literal["sql_result", "sql_result_trace"] = "sql_result_trace"
