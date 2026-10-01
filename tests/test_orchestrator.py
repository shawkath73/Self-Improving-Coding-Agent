from verified_agent.contracts import BenchmarkTask, ExecutionResult
from verified_agent.orchestrator import Orchestrator


class Planner:
    def plan(self, task):
        return "plan"


class Coder:
    def code(self, task, plan, feedback=""):
        return "answer"


class Executor:
    def run(self, task, code):
        return ExecutionResult(status="passed", stdout="1 passed")


def test_orchestrator_with_fake_llm():
    task = BenchmarkTask(id="fake", prompt="x", tests="def test_x(): pass")
    result = Orchestrator(Planner(), Coder(), Executor()).run(task)
    assert result.status == "passed"
    assert len(result.attempts) == 1
