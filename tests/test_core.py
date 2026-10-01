from verified_agent.benchmarks import load_manifest
from verified_agent.contracts import ExecutionResult
from verified_agent.critics import parse_critique
from verified_agent.metrics import pass_at_k


def test_benchmarks():
    assert len(load_manifest()) == 12


def test_critic():
    assert parse_critique(ExecutionResult(status="passed")).passed


def test_metrics():
    assert pass_at_k([True, False], 1) == 0.5
