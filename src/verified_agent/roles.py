from importlib.resources import files
from typing import Protocol

from .contracts import BenchmarkTask, Critique, ExecutionResult
from .critics import parse_critique


class Planner(Protocol):
    def plan(self, task: BenchmarkTask) -> str: ...


class Coder(Protocol):
    def code(self, task: BenchmarkTask, plan: str, feedback: str = "") -> str: ...


class Critic(Protocol):
    def critique(self, result: ExecutionResult) -> Critique: ...


def _prompt(name: str) -> str:
    packaged = files("verified_agent").joinpath("prompts", name)
    if packaged.is_file():
        return packaged.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Packaged prompt not found: {name}")


class LLMPlanner:
    def __init__(self, llm):
        self.llm = llm

    def plan(self, task):
        return self.llm.complete(_prompt("planner.txt") + "\n" + task.prompt)


class LLMCoder:
    def __init__(self, llm):
        self.llm = llm

    def code(self, task, plan, feedback=""):
        text = self.llm.complete(
            _prompt("coder.txt") + f"\nTask:{task.prompt}\nPlan:{plan}\nFeedback:{feedback}"
        )
        return text.replace("```python", "").replace("```", "").strip()


class ExecutionCritic:
    def critique(self, result):
        return parse_critique(result)
