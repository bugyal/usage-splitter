"""End-to-end CLI tests, fully offline, against the sample config."""
import json
import os

import pytest

from usage_splitter.cli import main

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, "..", "examples", "sample_config.json")


def test_plan_text(capsys):
    rc = main(["plan", "--config", SAMPLE])
    out = capsys.readouterr().out
    assert rc == 0
    assert "1,450,000 / 2,000,000" in out
    assert "security-and-auth" in out
    assert "mechanical-tests" in out
    assert "estimate" in out.lower()
    assert "not vendor metering" in out


def test_plan_classification_of_fixture(capsys):
    rc = main(["--json", "plan", "--config", SAMPLE])
    d = json.loads(capsys.readouterr().out)
    tiers = {t["id"]: t for t in d["tasks"]}
    # evidence-1 shape: mechanical work offloaded, trust-boundary work kept
    assert tiers["T1"]["destination"] == "local"    # tests
    assert tiers["T2"]["destination"] == "local"    # docs
    assert tiers["T3"]["destination"] == "premium"  # auth (keyword)
    assert tiers["T4"]["destination"] == "local"    # docstrings
    assert tiers["T5"]["destination"] == "premium"  # migration (keyword+glob)
    assert tiers["T6"]["destination"] == "local"    # boilerplate glob
    assert tiers["T3"]["matched_rule"] == "security-and-auth"
    assert tiers["T5"]["matched_rule"] == "data-migrations"
    # offloaded token estimate: 12000+3000+6000+4000 = 25000
    assert d["savings_est"]["offloaded_tokens_est"] == 25_000
    # 25000/1e6*15 = 0.375
    assert abs(d["savings_est"]["usd_equivalent_saved_est"] - 0.375) < 1e-9


def test_run_without_executor_records_pending(tmp_path, capsys):
    m = tmp_path / "m.json"
    rc = main(["run", "--config", SAMPLE, "--manifest", str(m)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "offloaded-pending : 4" in out
    d = json.loads(m.read_text())
    pend = [e for e in d["entries"] if e["status"] == "pending"]
    assert len(pend) == 4
    assert all(e["executor"] is None for e in pend)


def test_run_with_executor_records_offloaded(tmp_path, capsys):
    m = tmp_path / "m.json"
    rc = main(["run", "--config", SAMPLE, "--manifest", str(m),
               "--executor", "ollama@spare-laptop",
               "--output-dir", str(tmp_path / "out")])
    out = capsys.readouterr().out
    assert rc == 0
    assert "offloaded-executed: 4" in out
    d = json.loads(m.read_text())
    off = [e for e in d["entries"] if e["status"] == "offloaded"]
    assert all(e["output_path"] for e in off)
    # outputs recorded, not fabricated: the paths need not exist on disk
    assert not any(os.path.exists(e["output_path"]) for e in off)


def test_merge_flags_missing_outputs(tmp_path, capsys):
    m = tmp_path / "m.json"
    main(["run", "--config", SAMPLE, "--manifest", str(m),
          "--executor", "ollama@spare"])
    rc = main(["merge", "--manifest", str(m)])
    out = capsys.readouterr().out
    assert rc == 1  # outputs missing -> not mergeable yet
    assert "nothing is fabricated" in out
    assert "review checklist" in out


def test_report_from_manifest(tmp_path, capsys):
    m = tmp_path / "m.json"
    main(["run", "--config", SAMPLE, "--manifest", str(m),
          "--executor", "ollama@spare"])
    rc = main(["report", "--config", SAMPLE, "--manifest", str(m)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "25,000 tokens" in out
    assert "$0.375" in out
    assert "not vendor metering" in out


def test_missing_config_is_usage_error(capsys):
    rc = main(["plan", "--config", "/nope/missing.json"])
    assert rc == 2
    assert capsys.readouterr().err.startswith("usage-splitter:")


def test_invalid_config_is_usage_error(tmp_path, capsys):
    bad = tmp_path / "c.json"
    bad.write_text('{"plan": {}}')
    rc = main(["plan", "--config", str(bad)])
    assert rc == 2
    assert "config.plan." in capsys.readouterr().err
