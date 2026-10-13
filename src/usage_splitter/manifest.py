"""Manifest: what ran where, and the merge-back packet."""
from __future__ import annotations

import json

from .model import ManifestEntry, Task


def entries_from_tasks(tasks: list[Task], executor: str | None,
                       offload_status: str = "pending") -> list[ManifestEntry]:
    """Build manifest entries. Tasks must be classified first (plan/run do
    this); an unclassified task is a programming error, not a silent
    premium-route.

    status semantics:
      kept-premium  -- high-stakes task, stays on the premium model
      offloaded     -- low-stakes task executed against the configured executor
      pending       -- low-stakes task with no executor configured: recorded,
                       NOT executed, not pretended
    """
    for t in tasks:
        if t.tier not in ("high", "low") or t.destination not in (
                "premium", "local"):
            raise ValueError(
                f"task {t.id!r} is not classified (tier={t.tier!r}); "
                "run classify() first")
    out = []
    for t in tasks:
        if t.destination == "premium":
            out.append(ManifestEntry(
                task_id=t.id, description=t.description, tier=t.tier,
                destination=t.destination, status="kept-premium",
                est_tokens=t.est_tokens, review_required=False))
        else:
            executed = executor is not None
            out.append(ManifestEntry(
                task_id=t.id, description=t.description, tier=t.tier,
                destination=t.destination,
                status="offloaded" if executed else offload_status,
                est_tokens=t.est_tokens, executor=executor,
                review_required=True))
    return out


def manifest_to_dicts(entries: list[ManifestEntry]) -> list[dict]:
    return [{
        "task_id": e.task_id,
        "description": e.description,
        "tier": e.tier,
        "destination": e.destination,
        "status": e.status,
        "est_tokens": e.est_tokens,
        "executor": e.executor,
        "output_path": e.output_path,
        "review_required": e.review_required,
    } for e in entries]


def write_manifest(path: str, entries: list[ManifestEntry]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"manifest_version": 1,
                   "entries": manifest_to_dicts(entries)}, fh, indent=1)
        fh.write("\n")


def read_manifest(path: str) -> list[ManifestEntry]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"not a usage-splitter manifest: {path}")
    return [ManifestEntry(**e) for e in data["entries"]]


def merge_packet(entries: list[ManifestEntry]) -> dict:
    """The merge-back packet for premium-model review.

    The exact workflow from the evidence post: low-stakes outputs come back
    and the premium model reviews/approves them. v0.1 produces the packet
    (what to review, from where, review checklist); it does not fabricate
    outputs that do not exist.
    """
    off = [e for e in entries if e.destination == "local"]
    missing = [e for e in off if not e.output_path]
    return {
        "review_required_count": len(off),
        "outputs_present": len(off) - len(missing),
        "outputs_missing": [e.task_id for e in missing],
        "checklist": [
            "Verify each offloaded output compiles/tests before merge.",
            "Spot-check that no offloaded output silently changed scope.",
            "High-stakes context (security, auth, data handling) never went "
            "off-plan: confirm by the manifest tiers.",
        ],
        "entries": manifest_to_dicts(off),
    }
