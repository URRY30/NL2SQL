from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="NL2SQL Data Agent v2", alias="APP_NAME")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8010, alias="APP_PORT")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:1234@localhost:5432/postgres",
        alias="DATABASE_URL",
    )
    db_schema: str = Field(default="public", alias="DB_SCHEMA")
    default_topic_id: str = Field(default="talent", alias="DEFAULT_TOPIC_ID")
    allowed_query_views: str = Field(default="vw_talent_ai_query", alias="ALLOWED_QUERY_VIEWS")
    sql_max_limit: int = Field(default=100, alias="SQL_MAX_LIMIT")
    sql_timeout_seconds: int = Field(default=20, alias="SQL_TIMEOUT_SECONDS")

    llm_provider: str = Field(default="bigmodel", alias="LLM_PROVIDER")
    bigmodel_api_key: str = Field(default="", alias="BIGMODEL_API_KEY")
    bigmodel_base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        alias="BIGMODEL_BASE_URL",
    )
    bigmodel_model: str = Field(default="glm-5.1", alias="BIGMODEL_MODEL")
    bigmodel_timeout: float = Field(default=30, alias="BIGMODEL_TIMEOUT")
    bigmodel_temperature: float = Field(default=0.1, alias="BIGMODEL_TEMPERATURE")
    ollama_base_url: str = Field(default="http://127.0.0.1:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen3:8b", alias="OLLAMA_MODEL")
    ollama_timeout: float = Field(default=60, alias="OLLAMA_TIMEOUT")
    ollama_temperature: float = Field(default=0.1, alias="OLLAMA_TEMPERATURE")
    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="DASHSCOPE_BASE_URL",
    )
    dashscope_model: str = Field(default="qwen3.6-plus", alias="DASHSCOPE_MODEL")
    dashscope_timeout: float = Field(default=60, alias="DASHSCOPE_TIMEOUT")
    dashscope_temperature: float = Field(default=0.1, alias="DASHSCOPE_TEMPERATURE")
    dashscope_enable_thinking: bool = Field(default=True, alias="DASHSCOPE_ENABLE_THINKING")

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url

    @property
    def allowed_views(self) -> list[str]:
        return [item.strip() for item in self.allowed_query_views.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
