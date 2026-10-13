"""Quota arithmetic — estimates with the arithmetic shown, never blended with
measured vendor metering (v0.1 never talks to vendor APIs)."""
from __future__ import annotations

from .model import ManifestEntry, Plan


def quota_state(plan: Plan) -> dict:
    frac = plan.used_tokens / plan.quota_limit_tokens
    return {
        "plan": plan.plan_name,
        "period": plan.quota_period,
        "limit_tokens": plan.quota_limit_tokens,
        "used_tokens": plan.used_tokens,
        "remaining_tokens": max(0, plan.quota_limit_tokens - plan.used_tokens),
        "used_frac": round(frac, 4),
    }


def savings(manifest: list[ManifestEntry], plan: Plan) -> dict:
    """Estimated quota saved by the split.

    Arithmetic, printed in the report:
      offloaded_tokens = sum(est_tokens of entries routed local)
      premium_quota_saved_tokens = offloaded_tokens
      usd_equivalent_saved = offloaded_tokens / 1e6 * premium rate
    These are ESTIMATES from the user's own token estimates — labelled as
    such everywhere they render.
    """
    off = [m for m in manifest if m.destination == "local"]
    kept = [m for m in manifest if m.destination == "premium"]
    off_tokens = sum(m.est_tokens for m in off)
    kept_tokens = sum(m.est_tokens for m in kept)
    usd = off_tokens / 1_000_000 * plan.premium_usd_equivalent_per_mtok
    pct = (off_tokens / (off_tokens + kept_tokens)) if (off_tokens + kept_tokens) else 0.0
    return {
        "tasks_total": len(manifest),
        "tasks_offloaded": len(off),
        "tasks_kept_premium": len(kept),
        "offloaded_tokens_est": off_tokens,
        "kept_premium_tokens_est": kept_tokens,
        "share_offloaded_pct": round(pct * 100, 1),
        "usd_equivalent_saved_est": round(usd, 4),
        "rate_usd_per_mtok": plan.premium_usd_equivalent_per_mtok,
    }
