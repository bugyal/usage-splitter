"""usage-splitter CLI.

Commands:
  plan   --config c.json                  classify + route + savings estimate
  run    --config c.json --manifest m.json [--executor label] [--output-dir d]
                                          record the offload manifest
  merge  --manifest m.json                merge-back packet for premium review
  report --config c.json --manifest m.json  savings vs baseline from manifest

Exit codes: 0 ok, 1 nothing to do / pending work, 2 usage error (never a
traceback).
"""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .classify import classify
from .manifest import (entries_from_tasks, manifest_to_dicts, merge_packet,
                       read_manifest, write_manifest)
from .model import UsageError, load_config, parse_plan, parse_rules, parse_tasks
from .quota import quota_state, savings
from .report import dumps, render_merge, render_plan, render_report


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="usage-splitter",
        description="Subscription quota offload router: classify queued "
                    "tasks by stakes, run low-stakes work on cheap/local "
                    "capacity, merge back for premium review.")
    p.add_argument("--version", action="version",
                   version=f"usage-splitter {__version__}")
    p.add_argument("--json", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_config(sp):
        sp.add_argument("--config", required=True, help="JSON config path")

    add_config(sub.add_parser("plan", help="classify + route + savings"))

    r = sub.add_parser("run", help="record the offload manifest")
    add_config(r)
    r.add_argument("--manifest", required=True, help="manifest output path")
    r.add_argument("--executor", default=None,
                   help="executor label (e.g. 'ollama@spare-laptop'); "
                        "omitting it records tasks as pending, not executed")
    r.add_argument("--output-dir", default=None,
                   help="where offloaded outputs will land (recorded)")

    m = sub.add_parser("merge", help="merge-back packet for premium review")
    m.add_argument("--manifest", required=True)

    rep = sub.add_parser("report", help="savings vs baseline from manifest")
    add_config(rep)
    rep.add_argument("--manifest", required=True)

    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if not os.path.isfile(args.config if hasattr(args, "config") else
                              args.manifest):
            missing = getattr(args, "config", None) or args.manifest
            raise UsageError(f"no such file: {missing}")
        cfg = load_config(args.config) if hasattr(args, "config") else None

        if args.cmd == "plan":
            plan = parse_plan(cfg)
            tasks = parse_tasks(cfg)
            default_tier = cfg.get("default_tier", "high")
            classify(tasks, parse_rules(cfg), default_tier)
            sv = savings(entries_from_tasks(tasks, executor=None), plan)
            if args.json:
                print(dumps({
                    "quota": quota_state(plan),
                    "tasks": [{
                        "id": t.id, "tier": t.tier,
                        "destination": t.destination,
                        "matched_rule": t.matched_rule,
                        "est_tokens": t.est_tokens} for t in tasks],
                    "savings_est": sv,
                }))
            else:
                print(render_plan(quota_state(plan), tasks, sv))
            return 0

        if args.cmd == "run":
            plan = parse_plan(cfg)
            tasks = parse_tasks(cfg)
            default_tier = cfg.get("default_tier", "high")
            classify(tasks, parse_rules(cfg), default_tier)
            entries = entries_from_tasks(tasks, executor=args.executor)
            if args.output_dir and args.executor:
                for e in entries:
                    if e.destination == "local" and e.status == "offloaded":
                        e.output_path = os.path.join(
                            args.output_dir, f"{e.task_id}.out.md")
            write_manifest(args.manifest, entries)
            sv = savings(entries, plan)
            if args.json:
                print(dumps({"manifest": args.manifest,
                             "entries": manifest_to_dicts(entries),
                             "savings_est": sv}))
            else:
                print(f"manifest written: {args.manifest}")
                print(f"  offloaded-executed: "
                      f"{sum(1 for e in entries if e.status == 'offloaded')}")
                print(f"  offloaded-pending : "
                      f"{sum(1 for e in entries if e.status == 'pending')}")
                print(f"  kept on premium   : "
                      f"{sum(1 for e in entries if e.destination == 'premium')}")
                print(f"  savings est       : "
                      f"{sv['offloaded_tokens_est']:,} tokens "
                      f"(${sv['usd_equivalent_saved_est']})")
            return 0

        if args.cmd == "merge":
            entries = read_manifest(args.manifest)
            packet = merge_packet(entries)
            if args.json:
                print(dumps(packet))
            else:
                print(render_merge(packet))
            missing = packet["outputs_missing"]
            return 0 if not missing else 1

        if args.cmd == "report":
            plan = parse_plan(cfg)
            entries = read_manifest(args.manifest)
            dicts = manifest_to_dicts(entries)
            sv = savings(entries, plan)
            if args.json:
                print(dumps({"quota": quota_state(plan),
                             "savings_est": sv, "manifest": dicts}))
            else:
                print(render_report(quota_state(plan), dicts, sv))
            return 0

        return 2
    except UsageError as exc:
        print(f"usage-splitter: {exc}", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"usage-splitter: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
