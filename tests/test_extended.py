from verified_agent.benchmarks import load_manifest, validate_splits
from verified_agent.contracts import ExecutionResult
from verified_agent.critics import parse_critique
from verified_agent.memory import SQLiteMemory
from verified_agent.metrics import bootstrap_ci


def test_manifest_splits_are_disjoint_and_complete():
    tasks = load_manifest()
    validate_splits(tasks)
    assert len(tasks) == 12
    assert {task.split for task in tasks} == {"train", "validation", "test"}


def test_structured_critic_extracts_failure():
    result = ExecutionResult(
        status="failed", stderr="E AssertionError: expected 2\nsolution.py:7"
    )
    critique = parse_critique(result)
    assert critique.category == "assertion"
    assert critique.line == 7
    assert critique.actionable_feedback


def test_memory_admission_and_keyword_retrieval(tmp_path):
    memory = SQLiteMemory(tmp_path / "memory.db")
    assert not memory.admit("bad", {"task_id": "x", "prompt": "sorting"}, successful=False)
    assert memory.admit("good", {"task_id": "x", "prompt": "sorting lists", "successful_code": "x"})
    assert memory.search("sorting")


def test_bootstrap_ci_is_deterministic():
    assert bootstrap_ci([0.0, 1.0], rounds=100, seed=3) == bootstrap_ci(
        [0.0, 1.0], rounds=100, seed=3
    )
