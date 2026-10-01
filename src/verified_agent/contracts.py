from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BenchmarkTask(BaseModel):
    id: str
    prompt: str
    split: Literal["train", "validation", "test"] = "train"
    category: str = "general"
    language: str = "python"
    tests: str
    timeout_seconds: float = 5
    tags: list[str] = Field(default_factory=list)


class Critique(BaseModel):
    passed: bool
    summary: str
    category: Literal[
        "pass", "assertion", "syntax", "import", "timeout", "runtime", "unknown"
    ] = "unknown"
    exception: str | None = None
    file: str | None = None
    line: int | None = None
    signature: str | None = None
    actionable_feedback: str = ""
    failures: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    status: Literal["passed", "failed", "timeout", "error"]
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_ms: float = 0
    truncated: bool = False


class Attempt(BaseModel):
    number: int
    code: str
    execution: ExecutionResult | None = None
    critique: Critique | None = None


class RunRequest(BaseModel):
    task_id: str
    config: str = "full_system"
    max_attempts: int = 3


class RunResult(BaseModel):
    run_id: str
    task_id: str
    status: Literal["passed", "failed"]
    attempts: list[Attempt]
    trajectory: list[dict[str, Any]] = Field(default_factory=list)
    cost_usd: float = 0
    config: str = "baseline"
    provider: str | None = None
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
