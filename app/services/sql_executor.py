from __future__ import annotations

import asyncio
import time
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SqlExecutor:
    def __init__(self, timeout_seconds: int):
        self.timeout_seconds = timeout_seconds

    async def execute(self, session: AsyncSession, sql: str) -> dict[str, Any]:
        started = time.perf_counter()
        result = await asyncio.wait_for(session.execute(text(sql)), timeout=self.timeout_seconds)
        rows = [dict(row) for row in result.mappings().all()]
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        columns = list(rows[0].keys()) if rows else list(result.keys())
        return {
            "engine": "postgresql",
            "elapsed_ms": elapsed_ms,
            "row_count": len(rows),
            "columns": columns,
            "rows": rows,
        }
