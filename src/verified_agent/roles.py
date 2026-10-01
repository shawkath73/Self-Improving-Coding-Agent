from pathlib import Path
from typing import Protocol

from .contracts import BenchmarkTask, Critique, ExecutionResult
from .critics import parse_critique


class Planner(Protocol):
    def plan(self, task: BenchmarkTask) -> str: ...


class Coder(Protocol):
    def code(self, task: BenchmarkTask, plan: str, feedback: str = "") -> str: ...


class Critic(Protocol):
    def critique(self, result: ExecutionResult) -> Critique: ...


class LLMPlanner:
    def __init__(self, llm):
        self.llm = llm

    def plan(self, task):
        prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "planner.txt"
        with prompt_path.open(encoding="utf8") as prompt:
            return self.llm.complete(prompt.read() + "\n" + task.prompt)


class LLMCoder:
    def __init__(self, llm):
        self.llm = llm

    def code(self, task, plan, feedback=""):
        prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "coder.txt"
        with prompt_path.open(encoding="utf8") as prompt:
            text = self.llm.complete(
                prompt.read() + f"\nTask:{task.prompt}\nPlan:{plan}\nFeedback:{feedback}"
            )
        return text.replace("```python", "").replace("```", "").strip()


class ExecutionCritic:
    def critique(self, result):
        return parse_critique(result)
