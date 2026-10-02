import json
from pathlib import Path

from .contracts import BenchmarkTask

_PACKAGED_MANIFEST = Path(__file__).with_name("data") / "manifest.json"


def _manifest_path(root: str | Path | None) -> Path:
    if root is None:
        return _PACKAGED_MANIFEST
    candidate = Path(root) / "manifest.json"
    return candidate if candidate.exists() else _PACKAGED_MANIFEST


def load_manifest(root: str | Path | None = None, split: str | None = None) -> list[BenchmarkTask]:
    data = json.loads(_manifest_path(root).read_text(encoding="utf-8"))
    tasks = [BenchmarkTask.model_validate(item) for item in data["tasks"]]
    return [task for task in tasks if split is None or task.split == split]


def validate_splits(tasks: list[BenchmarkTask]) -> None:
    ids = [task.id for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Benchmark task IDs must be unique")
    if {task.split for task in tasks} != {"train", "validation", "test"}:
        raise ValueError("Manifest must contain train, validation, and test splits")


def load_task(task_id: str, root: str | Path | None = None) -> BenchmarkTask:
    for task in load_manifest(root):
        if task.id == task_id:
            return task
    raise KeyError(f"Unknown benchmark task: {task_id}")
