import re

from .contracts import Critique, ExecutionResult


def parse_critique(result: ExecutionResult) -> Critique:
    if result.status == "passed":
        return Critique(passed=True, category="pass", summary="All tests passed.")
    text = (result.stderr or result.stdout).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    joined = "\n".join(lines)
    if result.status == "timeout":
        category, feedback = "timeout", "Reduce complexity and avoid unbounded loops."
    elif "SyntaxError" in joined:
        category, feedback = "syntax", "Fix the syntax error at the reported location."
    elif "ModuleNotFoundError" in joined or "ImportError" in joined:
        category, feedback = "import", "Use only available imports and define the requested symbol."
    elif "AssertionError" in joined or "FAILED" in joined:
        category, feedback = "assertion", "Compare the implementation with the failing expected behavior."
    elif "Error" in joined or "Traceback" in joined:
        category, feedback = "runtime", "Handle the reported exception and rerun the tests."
    else:
        category, feedback = "unknown", "Inspect the test output and correct the implementation."
    location = re.search(r"(?P<file>[\w./\\-]+\.py):(?P<line>\d+)", joined)
    exception = next((line for line in lines if "Error" in line or "Exception" in line), None)
    signature = next((line for line in lines if "E   " in line), None)
    return Critique(
        passed=False,
        category=category,
        summary=lines[-1] if lines else result.status,
        exception=exception,
        file=location.group("file") if location else None,
        line=int(location.group("line")) if location else None,
        signature=signature,
        actionable_feedback=feedback,
        failures=lines[:10],
    )
