"""Stakes classification + routing decision.

First matching rule wins; rules are evaluated in config order so the user
controls precedence. A task matching nothing falls to the default_tier from
config (which must itself be a valid tier) — and the plan names that
explicitly, because silent defaults are how high-stakes work ends up on a
local model.
"""
from __future__ import annotations

import fnmatch

from .model import Rule, Task, compile_glob


def classify(tasks: list[Task], rules: list[Rule],
             default_tier: str) -> list[Task]:
    # validate default up front
    if default_tier not in ("high", "low"):
        raise ValueError(f"default_tier must be 'high' or 'low', "
                         f"got {default_tier!r}")
    compiled = [(r, compile_glob(r.path_glob) if r.path_glob else None)
                for r in rules]
    for t in tasks:
        t.tier = "undecided"
        t.matched_rule = None
        for rule, rx in compiled:
            kw_hit = False
            if rule.any_keyword:
                blob = (t.description + " " + (t.path or "")).lower()
                kw_hit = any(k in blob for k in rule.any_keyword)
            glob_hit = bool(rx and t.path and rx.match(t.path))
            if kw_hit or glob_hit:
                t.tier = rule.tier
                t.matched_rule = rule.name
                break
        if t.tier == "undecided":
            t.tier = default_tier
            t.matched_rule = f"default ({default_tier})"
        t.destination = "local" if t.tier == "low" else "premium"
    return tasks
