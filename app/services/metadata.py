from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.identifier import quote_ident


TEXT_TYPES = {"text", "character varying", "character", "varchar", "char", "USER-DEFINED"}
NUMERIC_TYPES = {
    "smallint",
    "integer",
    "bigint",
    "numeric",
    "real",
    "double precision",
    "decimal",
}
TIME_TYPES = {"date", "timestamp without time zone", "timestamp with time zone", "time without time zone"}


def semantic_type(column_name: str, data_type: str, samples: list[Any]) -> str:
    lower_name = column_name.lower()
    lower_type = data_type.lower()
    if lower_type == "boolean" or lower_name.startswith("is_") or lower_name.startswith("has_"):
        return "boolean"
    if lower_type in TIME_TYPES or "date" in lower_name or "time" in lower_name:
        return "time"
    if lower_type in NUMERIC_TYPES:
        return "numeric"
    if samples and len(samples) <= 20:
        return "enum"
    return "text"


class MetadataService:
    def __init__(self, schema: str, allowed_views: list[str]):
        self.schema = schema
        self.allowed_views = allowed_views
        self._cache: dict[str, dict[str, Any]] = {}

    async def refresh(self, session: AsyncSession) -> dict[str, Any]:
        datasets: list[dict[str, Any]] = []
        for view_name in self.allowed_views:
            profile = await self.profile_view(session, view_name, use_cache=False)
            datasets.append(profile)
        return {"schema": self.schema, "datasets": datasets}

    async def profile_view(self, session: AsyncSession, view_name: str, *, use_cache: bool = True) -> dict[str, Any]:
        if use_cache and view_name in self._cache:
            return self._cache[view_name]

        exists = await session.execute(
            text(
                """
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = :schema
                  AND table_name = :view_name
                LIMIT 1
                """
            ),
            {"schema": self.schema, "view_name": view_name},
        )
        table_row = exists.mappings().first()
        if not table_row:
            raise ValueError(f"registered view not found: {self.schema}.{view_name}")

        column_rows = (
            await session.execute(
                text(
                    """
                    SELECT
                        c.column_name,
                        c.data_type,
                        c.ordinal_position,
                        pg_catalog.col_description((quote_ident(c.table_schema) || '.' || quote_ident(c.table_name))::regclass, c.ordinal_position) AS comment
                    FROM information_schema.columns c
                    WHERE c.table_schema = :schema
                      AND c.table_name = :view_name
                    ORDER BY c.ordinal_position
                    """
                ),
                {"schema": self.schema, "view_name": view_name},
            )
        ).mappings().all()

        row_count = await self._safe_count(session, view_name)
        columns = []
        for row in column_rows:
            column_name = str(row["column_name"])
            data_type = str(row["data_type"])
            samples = await self._sample_values(session, view_name, column_name, data_type)
            columns.append(
                {
                    "name": column_name,
                    "data_type": data_type,
                    "semantic_type": semantic_type(column_name, data_type, samples),
                    "sample_values": samples,
                    "description": row.get("comment") or "",
                    "nullable": True,
                }
            )

        profile = {
            "table_name": view_name,
            "source_type": "postgresql",
            "schema": self.schema,
            "table_type": table_row["table_type"],
            "row_count": row_count,
            "columns": columns,
        }
        self._cache[view_name] = profile
        return profile

    async def _safe_count(self, session: AsyncSession, view_name: str) -> int | None:
        try:
            result = await session.execute(text(f"SELECT COUNT(1) AS total FROM {quote_ident(view_name)}"))
            return int(result.scalar() or 0)
        except Exception:
            return None

    async def _sample_values(
        self,
        session: AsyncSession,
        view_name: str,
        column_name: str,
        data_type: str,
    ) -> list[Any]:
        if data_type.lower() not in TEXT_TYPES and data_type.lower() != "boolean":
            return []
        try:
            result = await session.execute(
                text(
                    f"""
                    SELECT DISTINCT {quote_ident(column_name)} AS value
                    FROM {quote_ident(view_name)}
                    WHERE {quote_ident(column_name)} IS NOT NULL
                    LIMIT 20
                    """
                )
            )
            values = [row["value"] for row in result.mappings().all()]
            return [value for value in values if value not in ("", None)][:20]
        except Exception:
            return []
