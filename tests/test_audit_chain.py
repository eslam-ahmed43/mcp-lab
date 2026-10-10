import json

import pytest

import audit


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "audit.jsonl")
    monkeypatch.delenv("MCP_AUDIT_KEY", raising=False)


def write_three():
    audit.record("bob", "create_task", {"title": "a"}, "ALLOW", "executed")
    audit.record("carol", "delete_task", {"task_id": 1}, "REQUIRE_APPROVAL", "queued approval 1")
    audit.record("dave", "review_approval", {"approval_id": 1}, "ALLOW", "approved")


def lines():
    return audit.AUDIT_PATH.read_bytes().splitlines()


def rewrite(items):
    audit.AUDIT_PATH.write_bytes(b"\n".join(items) + b"\n")


def test_clean_chain_verifies():
    write_three()
    result = audit.verify()
    assert result["ok"] is True
    assert result["entries"] == 3
    assert result["legacy_lines"] == 0
    assert result["problem"] is None
    assert result["head"]["seq"] == 3


def test_entries_are_linked_to_each_other():
    write_three()
    items = [json.loads(line) for line in lines()]
    assert [e["seq"] for e in items] == [1, 2, 3]
    assert items[0]["prev"] == "0" * 64
    assert items[1]["prev"] == items[0]["hash"]
    assert items[2]["prev"] == items[1]["hash"]


def test_modified_entry_is_detected():
    write_three()
    items = lines()
    entry = json.loads(items[1])
    entry["outcome"] = "nothing happened"
    items[1] = json.dumps(entry).encode()
    rewrite(items)
    result = audit.verify()
    assert result["ok"] is False
    assert result["line"] == 2
    assert "modified" in result["problem"]


def test_deleted_entry_is_detected():
    write_three()
    items = lines()
    del items[1]
    rewrite(items)
    result = audit.verify()
    assert result["ok"] is False
    assert result["line"] == 2


def test_reordered_entries_are_detected():
    write_three()
    items = lines()
    items[1], items[2] = items[2], items[1]
    rewrite(items)
    assert audit.verify()["ok"] is False


def test_tail_truncation_needs_an_anchor():
    write_three()
    marker = audit.head()
    rewrite(lines()[:-1])
    assert audit.verify()["ok"] is True
    result = audit.verify(f"{marker['seq']}:{marker['hash']}")
    assert result["ok"] is False
    assert "truncated" in result["problem"]


def test_correct_anchor_passes():
    write_three()
    marker = audit.head()
    assert audit.verify(f"{marker['seq']}:{marker['hash']}")["ok"] is True


def test_legacy_lines_are_covered_by_the_first_chained_entry():
    audit.AUDIT_PATH.write_bytes(b'{"user": "x"}\r\n{"user": "y"}\r\n')
    write_three()
    result = audit.verify()
    assert result["ok"] is True
    assert result["legacy_lines"] == 2
    assert result["entries"] == 3
    data = audit.AUDIT_PATH.read_bytes().replace(b'"x"', b'"z"', 1)
    audit.AUDIT_PATH.write_bytes(data)
    result = audit.verify()
    assert result["ok"] is False
    assert result["line"] == 3
    assert "previous hash mismatch" in result["problem"]


def test_keyed_entries_need_the_key_to_verify(monkeypatch):
    monkeypatch.setenv("MCP_AUDIT_KEY", "secret")
    audit.record("bob", "create_task", {}, "ALLOW", "executed")
    assert json.loads(lines()[0])["alg"] == "hmac-sha256"
    monkeypatch.delenv("MCP_AUDIT_KEY")
    result = audit.verify()
    assert result["ok"] is False
    assert "MCP_AUDIT_KEY" in result["problem"]
    monkeypatch.setenv("MCP_AUDIT_KEY", "secret")
    assert audit.verify()["ok"] is True


def test_wrong_key_fails_verification(monkeypatch):
    monkeypatch.setenv("MCP_AUDIT_KEY", "a")
    audit.record("bob", "create_task", {}, "ALLOW", "executed")
    monkeypatch.setenv("MCP_AUDIT_KEY", "b")
    result = audit.verify()
    assert result["ok"] is False
    assert "modified" in result["problem"]


def test_downgrade_to_plain_hash_is_rejected(monkeypatch):
    monkeypatch.setenv("MCP_AUDIT_KEY", "secret")
    audit.record("bob", "t", {}, "ALLOW", "executed")
    audit.record("bob", "t", {}, "ALLOW", "executed")
    items = lines()
    forged = json.loads(items[1])
    forged["alg"] = "sha256"
    body = {k: v for k, v in forged.items() if k != "hash"}
    forged["hash"] = audit._digest(None, audit._canonical(body))
    items[1] = json.dumps(forged).encode()
    rewrite(items)
    result = audit.verify()
    assert result["ok"] is False
    assert "downgrade" in result["problem"]


def test_missing_file_verifies_as_empty():
    result = audit.verify()
    assert result["ok"] is True
    assert result["entries"] == 0
    assert result["head"] is None


def test_invalid_json_line_is_reported():
    audit.AUDIT_PATH.write_bytes(b"not json\n")
    result = audit.verify()
    assert result["ok"] is False
    assert result["line"] == 1


def test_command_line_exit_codes():
    write_three()
    assert audit.main(["audit.py", "verify"]) == 0
    items = lines()
    entry = json.loads(items[0])
    entry["user"] = "eve"
    items[0] = json.dumps(entry).encode()
    rewrite(items)
    assert audit.main(["audit.py", "verify"]) == 1
