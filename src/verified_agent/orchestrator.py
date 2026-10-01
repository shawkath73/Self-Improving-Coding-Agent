from __future__ import annotations

import json
import uuid

from .contracts import Attempt, BenchmarkTask, RunResult
from .critics import parse_critique


class Orchestrator:
    def __init__(self, planner, coder, executor, critic=parse_critique, max_attempts=3,
                 memory=None, config="baseline", structured_feedback=True):
        self.planner, self.coder, self.executor, self.critic, self.max_attempts = (
            planner,
            coder,
            executor,
            critic,
            max_attempts,
        )
        self.memory = memory
        self.config, self.structured_feedback = config, structured_feedback

    def run(self, task: BenchmarkTask) -> RunResult:
        run_id, trajectory, attempts, feedback = str(uuid.uuid4()), [], [], ""
        plan = self.planner.plan(task)
        if self.memory is not None:
            memories = self.memory.search(task.prompt, limit=3)
            if memories:
                feedback = "Relevant prior fixes:\n" + "\n".join(
                    json.dumps(item, sort_keys=True) for item in memories
                )
        for number in range(1, self.max_attempts + 1):
            code = self.coder.code(task, plan, feedback)
            execution = self.executor.run(task, code)
            critique = self.critic(execution)
            attempts.append(
                Attempt(number=number, code=code, execution=execution, critique=critique)
            )
            trajectory.append(
                {
                    "event": "attempt",
                    "number": number,
                    "status": execution.status,
                    "critique": critique.model_dump(),
                }
            )
            if critique.passed:
                if self.memory is not None:
                    self.memory.admit(
                        f"{task.id}:{run_id}",
                        {
                            "task_id": task.id,
                            "prompt": task.prompt,
                            "plan": plan,
                            "successful_code": code,
                            "failures": [a.critique.summary for a in attempts[:-1]],
                        },
                    )
                return RunResult(
                    run_id=run_id,
                    task_id=task.id,
                    status="passed",
                    attempts=attempts,
                    trajectory=trajectory, config=self.config,
                )
            feedback = (critique.actionable_feedback + "\n" + critique.summary
                        if self.structured_feedback else critique.summary)
        return RunResult(
            run_id=run_id,
            task_id=task.id,
            status="failed",
            attempts=attempts,
            trajectory=trajectory, config=self.config,
        )

    @staticmethod
    def trajectory_json(result):
        return json.dumps(result.trajectory, sort_keys=True)
