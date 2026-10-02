import json
import os
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .benchmarks import load_task
from .clients import AnthropicClient, ConfigurationError, GeminiClient
from .contracts import RunRequest
from .executors import DockerExecutor, LocalExecutor
from .memory import SQLiteMemory
from .orchestrator import Orchestrator
from .repository import Repository
from .roles import ExecutionCritic, LLMCoder, LLMPlanner

RUN_DB = Path(os.getenv("RUN_DB_PATH", "runs.db"))
app = FastAPI(title="Verified Execution Agent", version="1.0")
_cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins,
                   allow_credentials="*" not in _cors_origins,
                   allow_methods=["*"], allow_headers=["*"])
repo = Repository(str(RUN_DB))


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


@app.get("/")
def root():
    return {"service": "verified-execution-agent", "status": "ok", "docs": "/docs"}


def _save_run(run_id, value):
    repo.save_run(run_id, value)


def _load_run(run_id):
    result = repo.get_run(run_id)
    return result


def make_orchestrator(config: str = "full_system"):
    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "60"))
    provider = os.getenv("LLM_PROVIDER", "").lower()
    if provider == "gemini" or (not provider and os.getenv("GEMINI_API_KEY")):
        llm = GeminiClient(
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            timeout_seconds=timeout_seconds,
        )
    elif provider == "anthropic" or (not provider and os.getenv("ANTHROPIC_API_KEY")):
        llm = AnthropicClient(
            model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
            timeout_seconds=timeout_seconds,
        )
    else:
        raise RuntimeError(
            "Configure GEMINI_API_KEY or ANTHROPIC_API_KEY, or set LLM_PROVIDER explicitly."
        )
    executor = DockerExecutor() if config == "full_system" and _env_flag("USE_DOCKER") else LocalExecutor()
    # Render's container filesystem is not guaranteed to be writable at the
    # project root. Keep local development persistent while using its writable
    # temporary directory when a production database is configured.
    memory_path = os.getenv(
        "MEMORY_DB_PATH",
        "/tmp/verified-agent-memory.db" if os.getenv("DATABASE_URL") else "memory.db",
    )
    memory = SQLiteMemory(memory_path) if config in {"memory", "full_system"} else None
    return Orchestrator(
        LLMPlanner(llm),
        LLMCoder(llm),
        executor,
        ExecutionCritic().critique,
        memory=memory, config=config, structured_feedback=config != "baseline",
    )


def _execute(req, run_id):
    _save_run(run_id, {"run_id": run_id, "status": "running", "task_id": req.task_id})
    try:
        orchestrator = make_orchestrator(req.config)
        orchestrator.max_attempts = max(1, req.max_attempts)
        result = orchestrator.run(load_task(req.task_id))
        provider = os.getenv("LLM_PROVIDER") or ("gemini" if os.getenv("GEMINI_API_KEY") else None)
        result.provider = provider
        result.model = (os.getenv("GEMINI_MODEL") if provider == "gemini"
                        else os.getenv("ANTHROPIC_MODEL") if provider == "anthropic" else None)
        llm = getattr(getattr(orchestrator, "planner", None), "llm", None)
        usage = getattr(llm, "usage", {}) or {}
        result.input_tokens = usage.get("input_tokens")
        result.output_tokens = usage.get("output_tokens")
        result.total_tokens = usage.get("total_tokens")
        payload = result.model_dump()
        payload["run_id"] = run_id
        _save_run(run_id, payload)
        if result.status == "passed":
            repo.add_memory(f"{req.task_id}:{run_id}", {
                "task_id": req.task_id, "prompt": load_task(req.task_id).prompt,
                "successful_code": result.attempts[-1].code,
            })
    except KeyError as exc:
        _save_run(
            run_id,
            {"run_id": run_id, "status": "error", "task_id": req.task_id, "error": str(exc)},
        )
    except (ConfigurationError, RuntimeError, ValueError) as exc:
        _save_run(
            run_id,
            {"run_id": run_id, "status": "error", "task_id": req.task_id, "error": str(exc)},
        )
    except Exception as exc:  # noqa: BLE001 - worker boundary must persist unexpected failures
        _save_run(
            run_id,
            {
                "run_id": run_id,
                "status": "error",
                "task_id": req.task_id,
                "error": f"{type(exc).__name__}: {exc}",
            },
        )


@app.post("/runs", status_code=202)
def submit(req: RunRequest, background_tasks: BackgroundTasks):
    run_id = str(uuid.uuid4())
    _save_run(run_id, {"run_id": run_id, "status": "queued", "task_id": req.task_id})
    background_tasks.add_task(_execute, req, run_id)
    return _load_run(run_id)


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    result = _load_run(run_id)
    if result is None:
        raise HTTPException(404, "run not found")
    return result


@app.get("/runs")
def list_runs(limit: int = 50, status: str | None = None):
    runs = repo.list_runs(limit, status)
    return {"runs": runs, "count": len(runs)}


@app.get("/settings")
def settings():
    """Expose safe runtime information; provider keys and secrets are never returned."""
    return {
        "api_version": app.version,
        "database": "PostgreSQL" if repo.is_postgres else "SQLite",
        "database_path": None if repo.is_postgres else str(RUN_DB),
        "llm_provider": os.getenv("LLM_PROVIDER") or (
            "gemini" if os.getenv("GEMINI_API_KEY") else
            "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "not configured"
        ),
        "docker_enabled": _env_flag("USE_DOCKER"),
    }


@app.get("/dashboard/summary")
def dashboard_summary():
    return repo.summary()


@app.get("/benchmarks/tasks")
def benchmark_tasks():
    return [task.model_dump() for task in __import__("verified_agent.benchmarks", fromlist=["load_manifest"]).load_manifest()]


@app.get("/experiments/ablations")
def ablation_results():
    saved = repo.experiments()
    if saved:
        return saved
    path = Path("results/ablations.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


@app.post("/experiments", status_code=201)
def create_experiment(payload: dict):
    repo.add_experiment(payload.get("name", "experiment"), payload.get("config", {}),
                        payload.get("result", {}))
    return payload


@app.get("/memory")
def list_memory(limit: int = 50):
    return repo.memories(min(max(limit, 1), 200))


@app.post("/memory", status_code=201)
def create_memory(payload: dict):
    key = payload.get("key") or str(uuid.uuid4())
    repo.add_memory(key, payload.get("value", payload), payload.get("successful", True))
    return {"key": key, "value": payload.get("value", payload)}


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


_frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=_frontend, html=True), name="frontend")
