# usage-splitter — subscription quota offload router

You are on a capped plan (Max 5x/20x, API credits) with a spare laptop
gathering dust. Some of your queued work is mechanical — tests, docs,
boilerplate — and some of it touches auth, migrations, production.
`usage-splitter` splits the queue by stakes, so premium quota goes to the
work that needs it and the mechanical work runs on cheap/local capacity —
with a manifest of what ran where, and a merge-back packet so the premium
model reviews what came back.

This is the workflow from the first splitting-evidence post: offload "extra
work" to a free/local model, submit results back for merge/approval, spend
premium quota "more on important things".

## What it does

1. **`plan`** — classifies a queued task list into stakes tiers from named,
   ordered rules in your config (keywords, path globs; first match wins;
   unmatched tasks fall to an explicit `default_tier`). Every task shows
   which rule fired.
2. **`run`** — records the offload manifest: what ran where, at what status.
   With `--executor` it records tasks as offloaded; without one it records
   them as **pending — recorded, not executed, not pretended**.
3. **`merge`** — the merge-back packet for premium-model review: what to
   review, from where, the checklist, and which outputs are still missing.
   Missing outputs are never fabricated.
4. **`report`** — quota saved vs baseline, from the manifest, with the
   arithmetic printed and labelled as an estimate from your own token
   estimates — not vendor metering (v0.1 never touches vendor APIs; there is
   nothing to scrape and no credentials to hold).

## Usage

```
$ usage-splitter plan --config examples/sample_config.json
# usage-splitter plan — Claude Max 5x (sample) (weekly)

quota: 1,450,000 / 2,000,000 tokens used (72%), 550,000 remaining

| task | tier | route | matched rule | est tokens |
|---|---|---|---|---|
| T1 | low | local | mechanical-tests | 12,000 |
| T3 | high | premium | security-and-auth | 18,000 |
...

## Estimated quota saved by the split (estimate, from your own token estimates)

- offloaded       : 4 task(s), 25,000 tokens (38.5% of queued work)
- kept on premium : 2 task(s), 40,000 tokens
- USD equivalent saved (est): $0.375 at $15.0/Mtok

$ usage-splitter run --config c.json --manifest m.json \
    --executor ollama@spare-laptop --output-dir out/
$ usage-splitter merge --manifest m.json
$ usage-splitter report --config c.json --manifest m.json
```

Exit codes: `0` ok, `1` merge not yet possible (outputs missing) / pending
work, `2` usage error — never a traceback. Every command takes `--json`.

## Config shape

```
{
  "plan": {"plan_name": "...", "quota_period": "weekly",
           "quota_limit_tokens": 2000000, "used_tokens": 1450000,
           "premium_usd_equivalent_per_mtok": 15.0,
           "local_tok_per_sec": 40.0},
  "default_tier": "high",
  "rules": [
    {"name": "security-and-auth", "tier": "high",
     "any_keyword": ["auth", "security", "credential"]},
    {"name": "mechanical-tests", "tier": "low",
     "any_keyword": ["unit test"], "path_glob": "tests/**"}
  ],
  "tasks": [{"id": "T1", "description": "...", "path": "tests/x.py",
             "est_tokens": 12000}]
}
```

Rules: put high-stakes rules FIRST — first match wins. `default_tier` is
what unmatched tasks get; `"high"` is the safe default (unclassified work
stays on the premium model).

## Design rules

- **Estimates are estimates.** Savings print with their arithmetic and a
  provenance label; nothing claims vendor-measured truth.
- **Classification is auditable.** Named rules, config order, the fired rule
  shown per task, explicit default.
- **Execution is honest.** No executor configured → tasks are `pending`,
  never `offloaded`; missing merge outputs are flagged, never fabricated.
- **Trust boundaries stay premium.** Security/auth/migration tasks belong to
  high-stakes rules; `default_tier: "high"` keeps unknown work off the
  local model.
- `main` never leaks a traceback: bad config renders as
  `usage-splitter: <message>`, exit 2.

## Scope and limitations

- v0.1 does not call any executor: it plans, records, and reports. Wiring an
  actual Ollama endpoint is the next step and the manifest schema already
  carries the fields for it.
- Savings use your `est_tokens` inputs; the tool's honesty about that is the
  feature — a wrong estimate is visible in the arithmetic, not buried.
- `local_tok_per_sec` is recorded for throughput maths in later versions.
