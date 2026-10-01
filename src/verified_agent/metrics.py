from __future__ import annotations

import random
import statistics


def pass_at_k(outcomes: list[bool], k=1) -> float:
    n, c = len(outcomes), sum(outcomes)
    if n == 0 or k > n:
        return 0.0
    if c == 0:
        return 0.0
    return 1 - ((n - c) / n) ** k


def bootstrap_ci(values: list[float], rounds=1000, seed=0):
    if not values:
        return (0.0, 0.0)
    rng = random.Random(seed)
    samples = [statistics.mean(rng.choices(values, k=len(values))) for _ in range(rounds)]
    samples.sort()
    return (samples[int(0.025 * rounds)], samples[int(0.975 * rounds) - 1])


def summarize(outcomes, costs, latencies):
    return {
        "pass@1": pass_at_k(outcomes, 1),
        "pass@k": pass_at_k(outcomes, len(outcomes)),
        "cost_usd": sum(costs),
        "latency_ms": statistics.mean(latencies) if latencies else 0,
        "pass_ci": bootstrap_ci([float(x) for x in outcomes]),
    }
