# Threat model
Generated code is untrusted. Local execution is a convenience mode, not a security boundary. Use Docker with a locked-down daemon, CPU/memory limits, no network, and a non-root user in production.
