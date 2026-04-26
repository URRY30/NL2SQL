from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import PROJECT_ROOT


class KnowledgeStore:
    def __init__(self, root: Path | None = None):
        self.root = root or PROJECT_ROOT
        self.topics_dir = self.root / "configs" / "topics"

    def load_topic(self, topic_id: str) -> dict[str, Any]:
        path = self.topics_dir / f"{topic_id}.json"
        if not path.exists():
            raise ValueError(f"topic config not found: {topic_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_topics(self) -> list[dict[str, Any]]:
        topics = []
        for path in sorted(self.topics_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            topics.append(
                {
                    "id": payload["id"],
                    "name": payload.get("name", payload["id"]),
                    "description": payload.get("description", ""),
                    "allowed_views": payload.get("allowed_views", []),
                }
            )
        return topics

    def build_context(self, topic_id: str, question: str, profiles: list[dict[str, Any]]) -> dict[str, Any]:
        topic = self.load_topic(topic_id)
        return {
            "topic": {
                "id": topic["id"],
                "name": topic.get("name", topic["id"]),
                "description": topic.get("description", ""),
            },
            "question": question,
            "tables": [
                {
                    "table_name": profile["table_name"],
                    "description": self._table_description(topic, profile["table_name"]),
                    "columns": [
                        {
                            "name": column["name"],
                            "data_type": column["data_type"],
                            "semantic_type": column["semantic_type"],
                            "description": column.get("description", ""),
                            "sample_values": column.get("sample_values", []),
                        }
                        for column in profile["columns"]
                    ],
                }
                for profile in profiles
            ],
            "metrics": topic.get("metrics", []),
            "column_aliases": topic.get("column_aliases", []),
            "enum_mappings": topic.get("enum_mappings", []),
            "business_rules": topic.get("business_rules", []),
            "sql_cases": topic.get("sql_cases", []),
        }

    def _table_description(self, topic: dict[str, Any], table_name: str) -> str:
        for item in topic.get("table_profiles", []):
            if item.get("table_name") == table_name:
                return item.get("description", "")
        return ""
