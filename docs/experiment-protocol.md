# Experiment protocol
Pin the manifest and configuration, run held-out test tasks with fixed seeds, and
record pass@1/pass@k, cost, latency, and bootstrap confidence intervals. Use
`python -m verified_agent.evaluation --output results\ablations.json` for the four
offline ablations.
