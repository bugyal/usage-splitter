"""Quota arithmetic: estimates with visible arithmetic, provenance labelled."""
from usage_splitter.model import ManifestEntry, Plan
from usage_splitter.quota import quota_state, savings


def mk_plan():
    return Plan(plan_name="Max 5x", quota_period="weekly",
                quota_limit_tokens=2_000_000, used_tokens=1_450_000,
                premium_usd_equivalent_per_mtok=15.0)


def entry(dest, tokens):
    return ManifestEntry(task_id="t", description="d", tier="low",
                         destination=dest, status="pending",
                         est_tokens=tokens)


def test_quota_state():
    q = quota_state(mk_plan())
    assert q["remaining_tokens"] == 550_000
    assert q["used_frac"] == 0.725


def test_savings_arithmetic_exact():
    m = [entry("local", 1_000_000), entry("premium", 1_000_000)]
    s = savings(m, mk_plan())
    # 1M offloaded at $15/Mtok = $15.00
    assert s["offloaded_tokens_est"] == 1_000_000
    assert s["usd_equivalent_saved_est"] == 15.0
    assert s["share_offloaded_pct"] == 50.0


def test_savings_zero_when_nothing_offloaded():
    s = savings([entry("premium", 500_000)], mk_plan())
    assert s["offloaded_tokens_est"] == 0
    assert s["usd_equivalent_saved_est"] == 0
    assert s["share_offloaded_pct"] == 0.0


def test_savings_fractional():
    m = [entry("local", 12_000), entry("local", 3_000),
         entry("premium", 18_000), entry("premium", 22_000)]
    s = savings(m, mk_plan())
    assert s["offloaded_tokens_est"] == 15_000
    assert s["tasks_offloaded"] == 2
    # 15000 / 1e6 * 15 = 0.225
    assert abs(s["usd_equivalent_saved_est"] - 0.225) < 1e-9
    # 15k offloaded / 55k total = 27.3%
    assert s["share_offloaded_pct"] == 27.3


def test_empty_manifest_no_division_error():
    s = savings([], mk_plan())
    assert s["offloaded_tokens_est"] == 0
    assert s["share_offloaded_pct"] == 0.0
