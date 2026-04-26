from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asyncpg  # noqa: E402

from app.core.config import get_settings  # noqa: E402


def asyncpg_dsn(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    return database_url


async def apply_sql(path: Path) -> None:
    settings = get_settings()
    sql = path.read_text(encoding="utf-8")
    connection = await asyncpg.connect(asyncpg_dsn(settings.async_database_url))
    try:
        await connection.execute(sql)
    finally:
        await connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply a SQL file to the configured PostgreSQL database.")
    parser.add_argument("path", help="SQL file path")
    args = parser.parse_args()
    path = Path(args.path)
    if not path.is_absolute():
        path = ROOT / path
    asyncio.run(apply_sql(path))
    print(f"applied {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
