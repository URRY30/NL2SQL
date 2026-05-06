from __future__ import annotations

import re
from typing import Any

from app.services.identifier import normalize_identifier


BLOCKED_KEYWORDS = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "CREATE",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
    "COPY",
    "CALL",
    "DO",
    "EXECUTE",
}


class SqlGuard:
    def __init__(self, allowed_views: list[str], max_limit: int):
        self.allowed_views = {self._table_key(view) for view in allowed_views}
        self.max_limit = max_limit

    def validate(self, sql: str, profiles: list[dict[str, Any]]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        normalized = self._strip_comments(sql).strip()
        upper = normalized.upper()

        checks.append(self._check("not_empty", bool(normalized), "SQL is present"))
        checks.append(
            self._check(
                "single_statement",
                normalized.count(";") <= 1 and not normalized.rstrip(";").count(";"),
                "single statement only",
            )
        )
        checks.append(
            self._check(
                "readonly_select",
                upper.startswith("SELECT"),
                "only SELECT statements are allowed",
            )
        )
        found_blocked = sorted(keyword for keyword in BLOCKED_KEYWORDS if re.search(rf"\b{keyword}\b", upper))
        checks.append(
            self._check(
                "blocked_keywords",
                not found_blocked,
                "no blocked keywords" if not found_blocked else f"blocked keywords: {', '.join(found_blocked)}",
            )
        )
        checks.append(
            self._check(
                "select_star_blocked",
                not re.search(r"SELECT\s+\*", upper),
                "SELECT * is not allowed",
            )
        )

        referenced_tables = self.extract_tables(normalized)
        disallowed = [table for table in referenced_tables if self._table_key(table) not in self.allowed_views]
        checks.append(
            self._check(
                "allowed_views_only",
                bool(referenced_tables) and not disallowed,
                "all referenced tables are whitelisted"
                if referenced_tables and not disallowed
                else f"disallowed or missing table refs: {', '.join(disallowed) or 'none'}",
            )
        )

        missing_columns = self._missing_qualified_columns(normalized, profiles)
        checks.append(
            self._check(
                "qualified_columns_exist",
                not missing_columns,
                "qualified columns exist" if not missing_columns else f"missing columns: {', '.join(missing_columns)}",
            )
        )

        limit_value = self._limit_value(normalized)
        is_aggregate_only = bool(re.search(r"\bCOUNT\s*\(|\bSUM\s*\(|\bAVG\s*\(|\bMIN\s*\(|\bMAX\s*\(", upper))
        has_group_by = " GROUP BY " in upper
        limit_ok = (
            limit_value is not None and 1 <= limit_value <= self.max_limit
        ) or (is_aggregate_only and not has_group_by)
        checks.append(
            self._check(
                "limit_required",
                limit_ok,
                f"LIMIT is required and must be <= {self.max_limit}, except scalar aggregate queries",
            )
        )

        status = "passed" if all(check["status"] == "passed" for check in checks) else "blocked"
        return {
            "status": status,
            "checks": checks,
            "referenced_tables": referenced_tables,
        }

    def ensure_limit(self, sql: str) -> str:
        normalized = sql.strip().rstrip(";")
        if self._limit_value(normalized) is not None:
            return f"{normalized};"
        return f"{normalized} LIMIT {self.max_limit};"

    def extract_tables(self, sql: str) -> list[str]:
        tables = []
        table_ref = r"(?:[a-zA-Z_][\w]*\.)?[a-zA-Z_][\w]*"
        for match in re.finditer(rf"\b(?:FROM|JOIN)\s+({table_ref})(?:\s+(?:AS\s+)?[a-zA-Z_][\w]*)?", sql, re.I):
            tables.append(match.group(1))
        return tables

    def _table_key(self, table: str) -> str:
        return normalize_identifier(table).split(".")[-1]

    def _strip_comments(self, sql: str) -> str:
        sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
        return re.sub(r"--.*?$", " ", sql, flags=re.M)

    def _limit_value(self, sql: str) -> int | None:
        match = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.I)
        return int(match.group(1)) if match else None

    def _missing_qualified_columns(self, sql: str, profiles: list[dict[str, Any]]) -> list[str]:
        known_by_table = {
            self._table_key(profile["table_name"]): {normalize_identifier(column["name"]) for column in profile["columns"]}
            for profile in profiles
        }
        aliases = self._table_aliases(sql)
        missing = []
        three_part_ref = r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b"
        for schema, table, column in re.findall(three_part_ref, sql):
            table_key = self._table_key(table)
            if table_key in known_by_table and normalize_identifier(column) not in known_by_table.get(table_key, set()):
                missing.append(f"{schema}.{table}.{column}")

        sql_without_three_part = re.sub(three_part_ref, " ", sql)
        for alias, column in re.findall(r"\b([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)\b", sql_without_three_part):
            table = aliases.get(normalize_identifier(alias))
            if table and normalize_identifier(column) not in known_by_table.get(table, set()):
                missing.append(f"{alias}.{column}")
        return missing

    def _table_aliases(self, sql: str) -> dict[str, str]:
        aliases: dict[str, str] = {}
        table_ref = r"(?:[a-zA-Z_][\w]*\.)?[a-zA-Z_][\w]*"
        for match in re.finditer(
            rf"\b(?:FROM|JOIN)\s+({table_ref})(?:\s+(?:AS\s+)?([a-zA-Z_][\w]*))?",
            sql,
            re.I,
        ):
            raw_table = normalize_identifier(match.group(1))
            table = self._table_key(raw_table)
            alias = normalize_identifier(match.group(2) or table)
            if alias.upper() not in {"ON", "WHERE", "GROUP", "ORDER", "LIMIT", "LEFT", "INNER", "RIGHT", "FULL"}:
                aliases[alias] = table
            aliases[table] = table
            aliases[raw_table] = table
        return aliases

    def _check(self, name: str, passed: bool, message: str) -> dict[str, str]:
        return {
            "name": name,
            "status": "passed" if passed else "failed",
            "message": message,
        }
