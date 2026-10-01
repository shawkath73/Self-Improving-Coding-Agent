import argparse
import json
import os
import sys
from pathlib import Path

from .benchmarks import load_manifest
from .metrics import summarize


def evaluate(orchestrator, root="benchmarks", split="test"):
    results = [orchestrator.run(task) for task in load_manifest(root, split)]
    outcomes = [result.status == "passed" for result in results]
    costs = [result.cost_usd for result in results]
    latencies = [
        attempt.execution.duration_ms
        for result in results
        for attempt in result.attempts
        if attempt.execution
    ]
    return summarize(outcomes, costs, latencies)


def run_ablations(root="benchmarks", output="results/ablations.json"):
    """Run a deterministic, non-LLM simulation over every benchmark task."""
    from .executors import LocalExecutor
    from .memory import SQLiteMemory
    from .orchestrator import Orchestrator

    solutions = {
        "add": "def add(a,b): return a+b",
        "reverse": "def reverse_text(s): return s[::-1]",
        "fizzbuzz": "def fizzbuzz(n):\n    return 'FizzBuzz' if n % 15 == 0 else ('Fizz' if n % 3 == 0 else ('Buzz' if n % 5 == 0 else n))",
        "clamp": "def clamp(value, low, high): return max(low, min(value, high))",
        "is_palindrome": "def is_palindrome(s): return s.lower() == s.lower()[::-1]",
        "factorial": "def factorial(n):\n    result=1\n    for i in range(2,n+1): result*=i\n    return result",
        "word_count": "def word_count(text):\n    counts={}\n    for word in text.split(): counts[word]=counts.get(word,0)+1\n    return counts",
        "unique_sorted": "def unique_sorted(values): return sorted(set(values))",
        "rotate": "def rotate(values,k): return values[k % len(values):] + values[:k % len(values)]",
        "safe_divide": "def safe_divide(a,b): return None if b == 0 else a / b",
        "flatten": "def flatten(values): return [item for group in values for item in group]",
        "title_words": "def title_words(text): return ' '.join(word.title() for word in text.split())",
    }

    class Planner:
        def plan(self, task):
            return f"Implement and verify {task.id}: {task.prompt}"

    class Coder:
        def __init__(self):
            self.calls = {}

        def code(self, task, plan, feedback=""):
            self.calls[task.id] = self.calls.get(task.id, 0) + 1
            if self.calls[task.id] == 1:
                        return f"def {task.id}(*args, **kwargs): return None"
            return solutions[task.id]

    class DeterministicCritic:
        def critique(self, execution):
            from .critics import parse_critique
            return parse_critique(execution)

    # One run has a genuine execution failure, critique, repair, and memory admission.
    memory = SQLiteMemory(":memory:")
    orchestrator = Orchestrator(
        Planner(), Coder(), LocalExecutor(), DeterministicCritic().critique,
        memory=memory, config="offline_simulation", structured_feedback=True, max_attempts=2
    )
    task_results = [orchestrator.run(task) for task in load_manifest(root)]
    outcomes = [result.status == "passed" for result in task_results]
    latencies = [a.execution.duration_ms for r in task_results for a in r.attempts]
    results = {
        "mode": "offline",
        "simulation": True,
        "llm_ablation": False,
        "note": "Deterministic execution-feedback simulation; no LLM or Gemini calls.",
        "metrics": summarize(outcomes, [0.0] * len(outcomes), latencies),
        "results": [result.model_dump() for result in task_results],
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return results


def run_online(root="benchmarks", split="test", task_ids=None, output="results/online.json",
               max_attempts=3, retries=3, llm=None):
    """Run the real provider-backed orchestrator, with an injectable fake for tests."""
    from .clients import ConfigurationError, GeminiClient
    from .executors import LocalExecutor
    from .orchestrator import Orchestrator
    from .roles import ExecutionCritic, LLMCoder, LLMPlanner

    if llm is None:
        if not os.getenv("GEMINI_API_KEY"):
            raise ConfigurationError("GEMINI_API_KEY is required for online mode.")
        llm = GeminiClient(
            model=os.getenv("GEMINI_MODEL", "gemini-3.6-flash"),
            retries=retries,
            timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        )
    tasks = load_manifest(root, split if split != "all" else None)
    if task_ids:
        wanted = set(task_ids)
        tasks = [task for task in tasks if task.id in wanted]
    if not tasks:
        raise ValueError("No benchmark tasks selected.")
    orchestrator = Orchestrator(
        LLMPlanner(llm), LLMCoder(llm), LocalExecutor(),
        ExecutionCritic().critique, max_attempts=max_attempts,
        config="gemini_online", structured_feedback=True,
    )
    task_results = [orchestrator.run(task) for task in tasks]
    usage = getattr(llm, "usage", {})
    for result in task_results:
        result.provider = "gemini"
        result.model = getattr(llm, "model", None)
        result.input_tokens = usage.get("input_tokens")
        result.output_tokens = usage.get("output_tokens")
        result.total_tokens = usage.get("total_tokens")
    outcomes = [result.status == "passed" for result in task_results]
    latencies = [a.execution.duration_ms for r in task_results for a in r.attempts]
    payload = {
        "mode": "online",
        "provider": "gemini",
        "split": split,
        "task_ids": [task.id for task in tasks],
        "metrics": summarize(outcomes, [r.cost_usd for r in task_results], latencies),
        "results": [result.model_dump() for result in task_results],
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Run offline simulation or Gemini benchmark")
    sub = parser.add_subparsers(dest="mode")
    offline = sub.add_parser("offline", help="deterministic local simulation (no LLM)")
    online = sub.add_parser("online", help="real Gemini-backed orchestrator")
    for command in (offline, online):
        command.add_argument("--root", default=None)
        command.add_argument("--output", default=None)
    online.add_argument("--split", choices=("train", "validation", "test", "all"), default="test")
    online.add_argument("--tasks", default="", help="comma-separated task IDs")
    online.add_argument("--max-attempts", type=int, default=3)
    online.add_argument("--retries", type=int, default=3)
    argv = sys.argv[1:]
    if not argv or argv[0] not in {"offline", "online", "-h", "--help"}:
        argv = ["offline", *argv]
    args = parser.parse_args(argv)
    # Preserve the original `--output ...` invocation as offline mode.
    mode = args.mode or "offline"
    root = args.root or str(Path(__file__).resolve().parents[2] / "benchmarks")
    output = args.output or ("results/online.json" if mode == "online" else "results/offline.json")
    if mode == "online":
        value = run_online(root, args.split, [x for x in args.tasks.split(",") if x],
                           output, args.max_attempts, args.retries)
    else:
        value = run_ablations(root, output)
    print(json.dumps(value, indent=2, default=str))


if __name__ == "__main__":
    main()
