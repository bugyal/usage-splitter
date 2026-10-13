"""Rendering: human text + JSON."""
from __future__ import annotations

import json


def fmt(n: int) -> str:
    return f"{n:,}"


def render_plan(plan_state: dict, tasks: list, savings: dict) -> str:
    out = [f"# usage-splitter plan — {plan_state['plan']} "
           f"({plan_state['period']})", ""]
    out.append(f"quota: {fmt(plan_state['used_tokens'])} / "
               f"{fmt(plan_state['limit_tokens'])} tokens used "
               f"({plan_state['used_frac']:.0%}), "
               f"{fmt(plan_state['remaining_tokens'])} remaining")
    out += ["", "| task | tier | route | matched rule | est tokens |",
            "|---|---|---|---|---|"]
    for t in tasks:
        out.append(f"| {t.id} | {t.tier} | {t.destination} | "
                   f"{t.matched_rule} | {fmt(t.est_tokens)} |")
    out += ["", "## Estimated quota saved by the split (estimate, from your "
                "own token estimates)", ""]
    out.append(f"- offloaded       : {savings['tasks_offloaded']} task(s), "
               f"{fmt(savings['offloaded_tokens_est'])} tokens "
               f"({savings['share_offloaded_pct']}% of queued work)")
    out.append(f"- kept on premium : {savings['tasks_kept_premium']} task(s), "
               f"{fmt(savings['kept_premium_tokens_est'])} tokens")
    out.append(f"- USD equivalent saved (est): "
               f"${savings['usd_equivalent_saved_est']} "
               f"at ${savings['rate_usd_per_mtok']}/Mtok")
    out += ["", "Arithmetic: offloaded_tokens / 1e6 * rate = savings.",
            "This is an estimate from configuration and your token "
            "estimates, not vendor metering."]
    return "\n".join(out)


def render_report(plan_state: dict, manifest_entries: list[dict],
                  savings: dict) -> str:
    offloaded = [e for e in manifest_entries
                 if e["destination"] == "local"]
    executed = [e for e in offloaded if e["status"] == "offloaded"]
    pending = [e for e in offloaded if e["status"] == "pending"]
    out = ["# usage-splitter report", "",
           f"plan: {plan_state['plan']} ({plan_state['period']}) — "
           f"{fmt(plan_state['used_tokens'])} / "
           f"{fmt(plan_state['limit_tokens'])} tokens used "
           f"({plan_state['used_frac']:.0%})", ""]
    out.append(f"manifest: {len(manifest_entries)} entr"
               f"{'y' if len(manifest_entries) == 1 else 'ies'} — "
               f"{len(executed)} offloaded+executed, {len(pending)} "
               "offloaded+pending (no executor configured), "
               f"{len(manifest_entries) - len(offloaded)} kept on premium")
    if pending:
        out += ["", "pending tasks (recorded, NOT executed — configure an "
                    "executor to run them):"]
        out += [f"- {e['task_id']}: {e['description']}" for e in pending]
    out += ["", "## Estimated savings (estimate — arithmetic shown)", "",
            f"- offloaded (est): {fmt(savings['offloaded_tokens_est'])} "
            f"tokens across {savings['tasks_offloaded']} task(s) "
            f"({savings['share_offloaded_pct']}% of queued work)",
            f"- USD equivalent (est): ${savings['usd_equivalent_saved_est']} "
            f"at ${savings['rate_usd_per_mtok']}/Mtok",
            "- arithmetic: offloaded_tokens / 1e6 * rate",
            "- these are estimates from token estimates in config, not "
            "vendor metering"]
    return "\n".join(out)


def render_merge(packet: dict) -> str:
    out = [f"# merge-back packet — {packet['review_required_count']} "
           "offloaded task(s) await premium review", ""]
    out.append(f"outputs present : {packet['outputs_present']}")
    out.append(f"outputs missing : {len(packet['outputs_missing'])}")
    if packet["outputs_missing"]:
        out += [f"  - {t}" for t in packet["outputs_missing"]]
        out += ["", "Missing outputs are recorded as pending in the "
                    "manifest — nothing is fabricated to fill them."]
    out += ["", "review checklist:"] + [f"- {c}" for c in packet["checklist"]]
    out += ["", "| task | status | executor | output |", "|---|---|---|---|"]
    for e in packet["entries"]:
        out.append(f"| {e['task_id']} | {e['status']} | {e['executor']} | "
                   f"{e['output_path'] or '-'} |")
    return "\n".join(out)


def dumps(data) -> str:
    return json.dumps(data, indent=1)
