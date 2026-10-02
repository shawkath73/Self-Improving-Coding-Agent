from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .contracts import BenchmarkTask, ExecutionResult


class LocalExecutor:
    def __init__(self, max_output=12000):
        self.max_output = max_output

    def run(self, task: BenchmarkTask, code: str) -> ExecutionResult:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "solution.py").write_text(code)
            (p / "test_solution.py").write_text(task.tests)
            start = time.perf_counter()
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", "test_solution.py"],
                    cwd=p,
                    env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
                    capture_output=True,
                    text=True,
                    timeout=task.timeout_seconds,
                    check=False,
                )
                status = "passed" if proc.returncode == 0 else "failed"
                out = proc.stdout + proc.stderr
                trunc = len(out) > self.max_output
                return ExecutionResult(
                    status=status,
                    stdout=out[: self.max_output],
                    stderr=proc.stderr[: self.max_output],
                    exit_code=proc.returncode,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    truncated=trunc,
                )
            except subprocess.TimeoutExpired as exc:
                return ExecutionResult(
                    status="timeout",
                    stdout=str(exc.stdout or "")[: self.max_output],
                    stderr=str(exc.stderr or "")[: self.max_output],
                    duration_ms=(time.perf_counter() - start) * 1000,
                )


class DockerExecutor:
    def __init__(self, image="python:3.11-slim", max_output=12000, **kwargs):
        self.image, self.max_output, self.kwargs = image, max_output, kwargs

    def run(self, task, code):
        try:
            import docker
        except ImportError as exc:
            raise RuntimeError("Install [docker] extra for DockerExecutor") from exc
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "solution.py").write_text(code)
            (p / "test_solution.py").write_text(task.tests)
            start = time.perf_counter()
            client = docker.from_env()
            try:
                output = client.containers.run(
                    self.image,
                    ["python", "-m", "pytest", "-q", "/work/test_solution.py"],
                    volumes={str(p): {"bind": "/work", "mode": "ro"}},
                    network_disabled=True,
                    mem_limit=self.kwargs.get("mem_limit", "256m"),
                    nano_cpus=self.kwargs.get("nano_cpus", 1_000_000_000),
                    remove=True,
                    stdout=True,
                    stderr=True,
                    timeout=task.timeout_seconds,
                )
                text = output.decode(errors="replace")
                truncated = len(text) > self.max_output
                return ExecutionResult(
                    status="passed" if " passed" in text else "failed",
                    stdout=text[: self.max_output],
                    exit_code=0,
                    duration_ms=(time.perf_counter() - start) * 1000,
                    truncated=truncated,
                )
            except (
                docker.errors.APIError,
                docker.errors.ContainerError,
                docker.errors.DockerException,
                TypeError,
            ) as exc:
                # Docker SDK exceptions vary by version; preserve a stable contract.
                timed_out = "timeout" in str(exc).lower()
                return ExecutionResult(
                    status="timeout" if timed_out else "error",
                    stderr=str(exc)[: self.max_output],
                    duration_ms=(time.perf_counter() - start) * 1000,
                )
            finally:
                client.close()
