import json
from pathlib import Path

from .contracts import BenchmarkTask


def load_manifest(root: str | Path = "benchmarks", split: str | None = None) -> list[BenchmarkTask]:
    data = json.loads((Path(root) / "manifest.json").read_text(encoding="utf-8"))
    tasks = [BenchmarkTask.model_validate(item) for item in data["tasks"]]
    return [task for task in tasks if split is None or task.split == split]


def validate_splits(tasks: list[BenchmarkTask]) -> None:
    ids = [task.id for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("Benchmark task IDs must be unique")
    if {task.split for task in tasks} != {"train", "validation", "test"}:
        raise ValueError("Manifest must contain train, validation, and test splits")


def load_task(task_id: str, root: str | Path = "benchmarks") -> BenchmarkTask:
    for task in load_manifest(root):
        if task.id == task_id:
            return task
    raise KeyError(f"Unknown benchmark task: {task_id}")
