"""Shared types and config schema."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field


class UsageError(Exception):
    """User-facing CLI misuse: rendered as `usage-splitter: <msg>`, exit 2."""


TIERS = ("high", "low")
DESTINATIONS = ("premium", "local")


@dataclass
class Plan:
    """Manual usage/burn inputs — config-first, no vendor API in v0.1."""

    plan_name: str
    quota_period: str                    # e.g. "weekly"
    quota_limit_tokens: int              # plan cap, from the vendor's readout
    used_tokens: int                     # measured so far (manual input)
    premium_usd_equivalent_per_mtok: float   # what overage/credits would cost
    local_tok_per_sec: float | None = None   # spare hardware, if given


@dataclass
class Rule:
    """One stakes-classification rule. First match wins."""

    name: str
    tier: str                            # "high" | "low"
    any_keyword: list[str] = field(default_factory=list)
    path_glob: str | None = None
    notes: str = ""


@dataclass
class Task:
    id: str
    description: str
    path: str | None = None
    est_tokens: int = 0                  # user's estimate of prompt+work size
    tier: str = "undecided"
    matched_rule: str | None = None
    destination: str | None = None       # "premium" | "local"


@dataclass
class ManifestEntry:
    task_id: str
    description: str
    tier: str
    destination: str
    status: str                          # pending | offloaded | kept-premium
    est_tokens: int
    executor: str | None = None          # endpoint label, if run
    output_path: str | None = None
    review_required: bool = False


def load_config(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
    except json.JSONDecodeError as exc:
        raise UsageError(f"config is not valid JSON: {path} ({exc})") from exc
    if not isinstance(cfg, dict):
        raise UsageError(f"config must be a JSON object: {path}")

    if "plan" not in cfg or not isinstance(cfg["plan"], dict):
        raise UsageError("config missing required object: plan")
    p = cfg["plan"]
    for key, typ in (("plan_name", str), ("quota_period", str),
                     ("quota_limit_tokens", int),
                     ("used_tokens", int),
                     ("premium_usd_equivalent_per_mtok", (int, float))):
        if key not in p or not isinstance(p[key], typ) or \
                (typ in (int,) and isinstance(p[key], bool)):
            raise UsageError(f"config.plan.{key} missing or wrong type "
                             f"(expected {typ.__name__})")
    if p["quota_limit_tokens"] <= 0:
        raise UsageError("config.plan.quota_limit_tokens must be positive")
    if p["used_tokens"] < 0:
        raise UsageError("config.plan.used_tokens must be >= 0")

    rules = cfg.get("rules")
    if not isinstance(rules, list) or not rules:
        raise UsageError("config.rules must be a non-empty list")
    for r in rules:
        if not isinstance(r, dict) or not r.get("name"):
            raise UsageError("each config.rules entry needs a name")
        if r.get("tier") not in TIERS:
            raise UsageError(f"rule '{r['name']}': tier must be one of {TIERS}")
        if not r.get("any_keyword") and not r.get("path_glob"):
            raise UsageError(
                f"rule '{r['name']}': needs any_keyword or path_glob")

    if "tasks" not in cfg or not isinstance(cfg["tasks"], list) or not cfg["tasks"]:
        raise UsageError("config.tasks must be a non-empty list")
    for t in cfg["tasks"]:
        if not isinstance(t, dict) or not t.get("id") or not t.get("description"):
            raise UsageError("each config.tasks entry needs id + description")

    return cfg


def parse_plan(cfg: dict) -> Plan:
    p = cfg["plan"]
    return Plan(
        plan_name=p["plan_name"],
        quota_period=p["quota_period"],
        quota_limit_tokens=p["quota_limit_tokens"],
        used_tokens=p["used_tokens"],
        premium_usd_equivalent_per_mtok=float(
            p["premium_usd_equivalent_per_mtok"]),
        local_tok_per_sec=p.get("local_tok_per_sec"),
    )


def parse_rules(cfg: dict) -> list[Rule]:
    out = []
    for r in cfg["rules"]:
        out.append(Rule(
            name=r["name"],
            tier=r["tier"],
            any_keyword=[k.lower() for k in r.get("any_keyword", [])],
            path_glob=r.get("path_glob"),
            notes=r.get("notes", ""),
        ))
    return out


def parse_tasks(cfg: dict) -> list[Task]:
    return [Task(
        id=t["id"],
        description=t["description"],
        path=t.get("path"),
        est_tokens=int(t.get("est_tokens", 0) or 0),
    ) for t in cfg["tasks"]]


def compile_glob(glob: str):
    """Translate a simple path glob to a regex.

    `**` matches any number of path segments *including none* — `tests/**`
    matches `tests/x.py` and `tests/sub/x.py`; `**/migrations/**` matches
    `migrations/007.py` and `a/b/migrations/x.py`. A single `*` inside a
    segment matches within that segment only.
    """
    parts = glob.split("/")
    out = ""
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if part == "**":
            if last:
                out += r"(?:.*)?"      # trailing: any suffix incl. none
            else:
                # a non-final ** consumes its own trailing slash too
                out += r"(?:[^/]+/)*" if i == 0 else r"(?:[^/]+/)*"
        else:
            seg = re.escape(part).replace(r"\*", "[^/]*")
            out += seg + ("" if last else "/")
    return re.compile("^" + out + "$")
