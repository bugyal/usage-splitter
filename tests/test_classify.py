"""Classification tests — auditable tiers, named rules, safe default."""
import pytest

from usage_splitter.classify import classify
from usage_splitter.model import Rule, Task


def mk(tasks, rules, default="high"):
    return classify(tasks, rules, default)


def test_keyword_rule_matches():
    t = mk([Task(id="a", description="write unit tests for helper")],
           [Rule(name="tests", tier="low", any_keyword=["unit test"])])
    assert t[0].tier == "low" and t[0].matched_rule == "tests"
    assert t[0].destination == "local"


def test_path_glob_rule_matches():
    t = mk([Task(id="a", description="update stuff", path="tests/test_x.py")],
           [Rule(name="testdir", tier="low", path_glob="tests/**")])
    assert t[0].tier == "low" and t[0].matched_rule == "testdir"


def test_first_matching_rule_wins():
    # both rules match; config order decides
    t = mk([Task(id="a", description="security review of the test harness")],
           [Rule(name="sec", tier="high", any_keyword=["security"]),
            Rule(name="tests", tier="low", any_keyword=["test"])])
    assert t[0].tier == "high" and t[0].matched_rule == "sec"


def test_default_tier_catches_unmatched():
    t = mk([Task(id="a", description="something unmatched")], [], default="high")
    assert t[0].tier == "high"
    assert t[0].matched_rule == "default (high)"
    assert t[0].destination == "premium"


def test_default_low_is_allowed_but_explicit():
    t = mk([Task(id="a", description="unmatched")], [], default="low")
    assert t[0].tier == "low"


def test_invalid_default_raises():
    with pytest.raises(ValueError):
        mk([Task(id="a", description="x")], [], default="yolo")


def test_case_insensitive_keywords():
    t = mk([Task(id="a", description="Add Unit Tests for parser")],
           [Rule(name="tests", tier="low", any_keyword=["unit test"])])
    assert t[0].tier == "low"


def test_glob_star_and_doublestar():
    t = mk([Task(id="a", description="x", path="a/b/c.md")],
           [Rule(name="deep", tier="low", path_glob="a/**")])
    assert t[0].tier == "low"
    t2 = mk([Task(id="b", description="x", path="a/c.md")],
            [Rule(name="one", tier="low", path_glob="a/*.md")])
    assert t2[0].tier == "low"
    t3 = mk([Task(id="c", description="x", path="a/b/c.md")],
            [Rule(name="one", tier="low", path_glob="a/*.md")])
    assert t3[0].tier != "low" or t3[0].matched_rule != "one"
