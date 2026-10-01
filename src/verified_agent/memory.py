import json
import sqlite3
from typing import Any


class MemoryRepository:
    def admit(self, key: str, value: dict[str, Any], *, successful: bool = True) -> bool:
        raise NotImplementedError

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        raise NotImplementedError


class SQLiteMemory(MemoryRepository):
    """Offline keyword retrieval; admissions default to successful trajectories only."""

    def __init__(self, path="memory.db"):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, task_id TEXT, "
            "prompt TEXT, value TEXT NOT NULL, successful INTEGER NOT NULL)"
        )
        self.db.commit()

    def admit(self, key, value, *, successful=True):
        if not successful:
            return False
        self.db.execute(
            "INSERT OR REPLACE INTO memory VALUES (?,?,?,?,?)",
            (key, value.get("task_id"), value.get("prompt", ""), json.dumps(value), 1),
        )
        self.db.commit()
        return True

    def put(self, key, value):
        return self.admit(key, value)

    def search(self, query, limit=5):
        terms = [term.lower() for term in query.split() if len(term) > 2]
        if not terms:
            return []
        where = " OR ".join(["lower(prompt) LIKE ?"] * len(terms))
        rows = self.db.execute(
            f"SELECT value FROM memory WHERE successful=1 AND ({where}) LIMIT ?",
            tuple(f"%{term}%" for term in terms) + (limit,),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]


class PgVectorMemory(MemoryRepository):
    """Optional integration placeholder for deployments with pgvector."""

    def admit(self, key, value, *, successful=True):
        raise NotImplementedError("Configure PostgreSQL/pgvector integration.")

    def search(self, query, limit=5):
        raise NotImplementedError("Configure PostgreSQL/pgvector integration.")
