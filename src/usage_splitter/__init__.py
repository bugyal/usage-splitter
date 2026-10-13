"""usage-splitter — subscription quota offload router.

A CLI for capped-subscription users (Max 5x/20x, API credits) with idle local
hardware. It does not talk to vendor APIs. It plans and records the split:

1. `plan`   — read config (manual usage inputs + stakes policy), classify a
              queued task list into stakes tiers, decide where each task runs.
2. `run`    — execute the offload for low-stakes tasks against a configured
              local/free endpoint (v0.1: records intent + manifest; the HTTP
              call is delegated to whatever the endpoint is), and record what
              ran where in a merge-back manifest.
3. `merge`  — produce the merge-back packet: low-stakes outputs plus the
              review checklist a premium model needs to approve them.
4. `report` — quota saved vs baseline, from the manifest, labelled as an
              estimate with its arithmetic shown.

Honesty rules:

- **Savings are estimates and are printed as arithmetic**, not outcomes: the
  manifest records intent and configuration, not verified vendor metering
  (that would need vendor APIs, which v0.1 deliberately never touches).
- **Classification is auditable**: every task's tier comes from named rules
  over explicit config (path patterns, keywords, declared stakes), and the
  plan shows which rule fired.
- **Execution is pluggable and safe by default**: `run` never invents a
  network call; if no executor is configured, it records `pending` in the
  manifest rather than pretending.
- `main` returns exit codes and never leaks a traceback: usage problems
  render as `usage-splitter: <message>` on stderr, exit 2.
"""

__version__ = "0.1.0"
