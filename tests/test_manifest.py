"""Manifest + merge-back packet tests."""
import pytest

from usage_splitter.manifest import (entries_from_tasks, merge_packet,
                                     read_manifest, write_manifest)
from usage_splitter.model import ManifestEntry, Task


def mk_tasks():
    return [
        Task(id="T1", description="tests", path="tests/x.py", est_tokens=100),
        Task(id="T2", description="auth review", path="src/auth.py",
             est_tokens=200),
    ]


def mk_classified():
    from usage_splitter.classify import classify
    from usage_splitter.model import Rule

    tasks = mk_tasks()
    classify(tasks, [Rule(name="tests", tier="low", path_glob="tests/**")],
             "high")
    return tasks


def test_entries_split_and_status():
    entries = entries_from_tasks(mk_classified(), executor=None)
    by = {e.task_id: e for e in entries}
    assert by["T1"].destination == "local" and by["T1"].status == "pending"
    assert by["T1"].review_required is True
    assert by["T2"].destination == "premium" and by["T2"].status == "kept-premium"
    assert by["T2"].review_required is False


def test_executor_makes_it_offloaded_not_pending():
    entries = entries_from_tasks(mk_classified(), executor="ollama@spare")
    by = {e.task_id: e for e in entries}
    assert by["T1"].status == "offloaded"
    assert by["T1"].executor == "ollama@spare"


def test_manifest_roundtrip(tmp_path):
    entries = entries_from_tasks(mk_classified(), executor="ollama@spare")
    p = tmp_path / "m.json"
    write_manifest(str(p), entries)
    back = read_manifest(str(p))
    assert [(e.task_id, e.status) for e in back] == \
           [(e.task_id, e.status) for e in entries]


def test_merge_packet_flags_missing_outputs():
    entries = entries_from_tasks(mk_classified(), executor="ollama@spare")
    packet = merge_packet(entries)
    assert packet["review_required_count"] == 1
    assert packet["outputs_present"] == 0
    assert packet["outputs_missing"] == ["T1"]


def test_merge_packet_with_outputs():
    entries = entries_from_tasks(mk_classified(), executor="ollama@spare")
    entries[0].output_path = "/tmp/outputs/T1.out.md"
    packet = merge_packet(entries)
    assert packet["outputs_present"] == 1
    assert packet["outputs_missing"] == []


def test_read_manifest_rejects_garbage(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text('{"hello": "world"}')
    with pytest.raises(ValueError):
        read_manifest(str(p))


def test_unclassified_task_is_rejected_not_silently_routed():
    import pytest
    with pytest.raises(ValueError, match="not classified"):
        entries_from_tasks(mk_tasks(), executor=None)
