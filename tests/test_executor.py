from verified_agent.contracts import BenchmarkTask
from verified_agent.executors import LocalExecutor


def test_timeout():
    t = BenchmarkTask(
        id="x", prompt="", tests="import time\ndef test_x(): time.sleep(1)", timeout_seconds=0.01
    )
    assert LocalExecutor().run(t, "").status == "timeout"
