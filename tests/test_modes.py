import json
from typing import ClassVar

from verified_agent.evaluation import run_ablations, run_online


def test_offline_mode_is_deterministic_and_repairs_failures(tmp_path):
    output = tmp_path / "offline.json"
    payload = run_ablations("benchmarks", output)

    assert payload["simulation"] is True
    assert payload["llm_ablation"] is False
    assert len(payload["results"]) == 12
    assert all(item["status"] == "passed" for item in payload["results"])
    assert all(len(item["attempts"]) == 2 for item in payload["results"])
    assert all(item["attempts"][0]["execution"]["status"] == "failed"
               for item in payload["results"])
    assert json.loads(output.read_text())["mode"] == "offline"


class FakeProvider:
    model: ClassVar[str] = "fake-gemini"
    usage: ClassVar[dict[str, int]] = {"input_tokens": 10, "output_tokens": 8, "total_tokens": 18}

    def complete(self, prompt):
        if "Task:Implement rotate" in prompt:
            return "def rotate(values,k): return values[k % len(values):] + values[:k % len(values)]"
        return "A valid implementation plan."


def test_online_mode_accepts_fake_provider_without_network(tmp_path):
    payload = run_online(
        "benchmarks", "test", ["rotate"], tmp_path / "online.json", llm=FakeProvider()
    )

    assert payload["mode"] == "online"
    assert payload["task_ids"] == ["rotate"]
    result = payload["results"][0]
    assert result["status"] == "passed"
    assert result["total_tokens"] == 18
