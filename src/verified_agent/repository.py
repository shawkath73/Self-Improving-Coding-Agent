"""Persistence layer for the dashboard API.

SQLite remains the default for local development.  Set ``DATABASE_URL`` to a
PostgreSQL URL in deployed environments (the optional ``postgres`` extra
provides the driver).
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Repository:
    def __init__(self, path: str | None = None):
        self.path = path or os.getenv("RUN_DB_PATH", "runs.db")
        self.database_url = os.getenv("DATABASE_URL")
        self.is_postgres = bool(self.database_url and
                                self.database_url.startswith(("postgres://", "postgresql://")))
        self._init()

    def _connect(self):
        if self.is_postgres:
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise RuntimeError(
                    "DATABASE_URL is PostgreSQL but psycopg is not installed; "
                    "install the 'postgres' extra"
                ) from exc
            return psycopg.connect(self.database_url, row_factory=dict_row)
        db = sqlite3.connect(self.path, check_same_thread=False)
        db.row_factory = sqlite3.Row
        return db

    def _init(self):
        with self._connect() as db:
            schema = (
                """CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, task_id TEXT, status TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS metrics (
                    id BIGSERIAL PRIMARY KEY, run_id TEXT, name TEXT NOT NULL,
                    value DOUBLE PRECISION NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL,
                    config TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id BIGSERIAL PRIMARY KEY, key TEXT UNIQUE NOT NULL,
                    task_id TEXT, prompt TEXT, value TEXT NOT NULL, successful INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );"""
                if self.is_postgres else
                """CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, task_id TEXT, status TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, name TEXT NOT NULL,
                    value REAL NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                    config TEXT NOT NULL, result TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE NOT NULL,
                    task_id TEXT, prompt TEXT, value TEXT NOT NULL, successful INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );"""
            )
            if self.is_postgres:
                db.execute(schema)
            else:
                db.executescript(schema)
                columns = {row["name"] for row in db.execute("PRAGMA table_info(runs)")}
                # Migrate the original MVP's (run_id, payload) table in place.
                for column, definition in (
                    ("task_id", "TEXT"), ("status", "TEXT NOT NULL DEFAULT 'unknown'"),
                    ("created_at", "TEXT"), ("updated_at", "TEXT"),
                ):
                    if column not in columns:
                        db.execute(f"ALTER TABLE runs ADD COLUMN {column} {definition}")
                now = _now()
                db.execute("UPDATE runs SET status=CASE WHEN status='unknown' THEN COALESCE(json_extract(payload, '$.status'), status) ELSE status END, "
                           "task_id=COALESCE(task_id, json_extract(payload, '$.task_id')), "
                           "created_at=COALESCE(created_at, ?), updated_at=COALESCE(updated_at, ?)",
                           (now, now))

    def _sql(self, query):
        return query.replace("?", "%s") if self.is_postgres else query

    def save_run(self, run_id: str, payload: dict[str, Any]):
        now = _now()
        with self._connect() as db:
            db.execute(self._sql("""INSERT INTO runs(run_id,task_id,status,payload,created_at,updated_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET
                task_id=excluded.task_id,status=excluded.status,payload=excluded.payload,
                updated_at=excluded.updated_at"""), (run_id, payload.get("task_id"), payload.get("status", "unknown"),
                 json.dumps(payload), now, now),
            )
            if payload.get("status") in {"passed", "failed"}:
                db.execute(self._sql("DELETE FROM metrics WHERE run_id=?"), (run_id,))
                attempts = payload.get("attempts", [])
                latencies = [a.get("execution", {}).get("duration_ms", 0)
                             for a in attempts if a.get("execution")]
                for name, value in (
                    ("passed", int(payload.get("status") == "passed")),
                    ("latency_ms", sum(latencies) / len(latencies) if latencies else 0),
                    ("attempts", len(attempts)),
                    ("cost_usd", payload.get("cost_usd", 0) or 0),
                    ("total_tokens", payload.get("total_tokens", 0) or 0),
                ):
                    db.execute(self._sql("INSERT INTO metrics(run_id,name,value,created_at) VALUES(?,?,?,?)"),
                               (run_id, name, value, now))

    def get_run(self, run_id):
        with self._connect() as db:
            row = db.execute(self._sql("SELECT payload FROM runs WHERE run_id=?"), (run_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_runs(self, limit=50, status=None):
        with self._connect() as db:
            query = "SELECT payload,created_at FROM runs"
            args = []
            if status:
                query += " WHERE status=?"
                args.append(status)
            query += " ORDER BY created_at DESC LIMIT ?"
            args.append(min(max(limit, 1), 200))
            rows = db.execute(self._sql(query), args).fetchall()
        return [json.loads(row["payload"]) | {"created_at": row["created_at"]} for row in rows]

    def summary(self):
        with self._connect() as db:
            total = db.execute(self._sql("SELECT COUNT(*) AS n FROM runs WHERE status IN ('passed','failed')")).fetchone()["n"]
            passed = db.execute(self._sql("SELECT COUNT(*) AS n FROM runs WHERE status='passed'")).fetchone()["n"]
            tokens = db.execute(self._sql("SELECT COALESCE(SUM(value),0) AS n FROM metrics WHERE name='total_tokens'")).fetchone()["n"]
            cost = db.execute(self._sql("SELECT COALESCE(SUM(value),0) AS n FROM metrics WHERE name='cost_usd'")).fetchone()["n"]
            latency = db.execute(self._sql("SELECT COALESCE(AVG(value),0) AS n FROM metrics WHERE name='latency_ms'")).fetchone()["n"]
            points = db.execute(self._sql("SELECT created_at,value FROM metrics WHERE name='passed' ORDER BY created_at LIMIT 100")).fetchall()
        return {"runs": total, "passed": passed, "pass_rate": (passed / total if total else 0),
                "total_tokens": tokens, "cost_usd": cost, "avg_latency_ms": latency,
                "pass_rate_series": [{"date": p["created_at"], "value": p["value"]} for p in points]}

    def add_memory(self, key, value, successful=True):
        now = _now()
        with self._connect() as db:
            db.execute(self._sql("""INSERT INTO memory_entries(key,task_id,prompt,value,successful,created_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value"""),
                       (key, value.get("task_id"), value.get("prompt", ""), json.dumps(value),
                        int(successful), now))

    def memories(self, limit=50):
        with self._connect() as db:
            rows = db.execute(self._sql("SELECT id,key,task_id,prompt,value,successful,created_at FROM memory_entries ORDER BY id DESC LIMIT ?"), (limit,)).fetchall()
        return [{**dict(row), "value": json.loads(row["value"]), "successful": bool(row["successful"])} for row in rows]

    def add_experiment(self, name, config, result):
        with self._connect() as db:
            db.execute(self._sql("INSERT INTO experiments(name,config,result,created_at) VALUES(?,?,?,?)"),
                       (name, json.dumps(config), json.dumps(result), _now()))

    def experiments(self):
        with self._connect() as db:
            rows = db.execute(self._sql("SELECT id,name,config,result,created_at FROM experiments ORDER BY id DESC")).fetchall()
        return [{**dict(row), "config": json.loads(row["config"]), "result": json.loads(row["result"])} for row in rows]
