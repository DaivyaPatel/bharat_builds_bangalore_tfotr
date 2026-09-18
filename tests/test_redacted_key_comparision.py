"""
test_redacted_key_comparison.py

DL-010: Redacted-key comparison. Explicit tests for the rule that a
redacted env var is always compared by value_sha256, never by value,
and the diff output never shows anything but "<redacted>" for either
side -- covering the edge cases discovered during review:
  - both sides redacted, hashes differ (the ticket's stated case)
  - both sides redacted, hashes match (no drift)
  - only one side redacted (inconsistency between environments)
  - redacted but no hash present on either/both sides
"""

from src.diff_engine import diff_snapshots, KIND_VALUE_MISMATCH, KIND_TYPE_MISMATCH
from src.severity import classify, SEVERITY_SUSPICIOUS, RULE_REDACTED_HASH_MISMATCH


def _snapshot_with_env_var(entry: dict) -> dict:
    return {
        "schema_version": "1.0",
        "environment": "test",
        "region": "ap-south-1",
        "resources": [
            {
                "resource_type": "lambda",
                "logical_name": "checkout",
                "resource_arn": "arn:aws:lambda:ap-south-1:111122223333:function:test",
                "config": {"env_vars": {"DB_PASSWORD": entry}},
            }
        ],
    }


def find_entry(entries, key):
    for e in entries:
        if e["key"] == key:
            return e
    return None


KEY = "lambda:checkout/env_vars/DB_PASSWORD"


def test_two_different_redacted_secrets_yield_suspicious_drift_rendered_as_redacted():
    """The ticket's literal acceptance criterion."""
    a = _snapshot_with_env_var(
        {"value": None, "redacted": True, "value_sha256": "hash_a_111"}
    )
    b = _snapshot_with_env_var(
        {"value": None, "redacted": True, "value_sha256": "hash_b_222"}
    )

    entries = diff_snapshots(a, b)
    entry = find_entry(entries, KEY)

    assert entry is not None
    assert entry["kind"] == KIND_VALUE_MISMATCH
    assert entry["value_a"] == "<redacted>"
    assert entry["value_b"] == "<redacted>"

    classified = classify(entry)
    assert classified["severity"] == SEVERITY_SUSPICIOUS
    assert classified["rule_id"] == RULE_REDACTED_HASH_MISMATCH


def test_redacted_comparison_never_leaks_the_hash_itself():
    """
    Regression guard: value_a/value_b must be the literal string
    "<redacted>", never the real hash value, even though the hash
    (not the plaintext) is what's actually being compared internally.
    """
    a = _snapshot_with_env_var(
        {"value": None, "redacted": True, "value_sha256": "9f86d081884c7d659a2feaa0c55ad015"}
    )
    b = _snapshot_with_env_var(
        {"value": None, "redacted": True, "value_sha256": "6b86b273ff34fce19d6b804eff5a3f57"}
    )

    entries = diff_snapshots(a, b)
    entry = find_entry(entries, KEY)

    serialized = str(entry)
    assert "9f86d081884c7d659a2feaa0c55ad015" not in serialized
    assert "6b86b273ff34fce19d6b804eff5a3f57" not in serialized


def test_same_redacted_secret_in_both_envs_yields_no_drift():
    a = _snapshot_with_env_var(
        {"value": None, "redacted": True, "value_sha256": "same_hash_123"}
    )
    b = _snapshot_with_env_var(
        {"value": None, "redacted": True, "value_sha256": "same_hash_123"}
    )

    entries = diff_snapshots(a, b)
    assert find_entry(entries, KEY) is None


def test_only_one_side_redacted_is_still_reported_and_masked():
    """
    Edge case found during review: if only one environment redacts a key
    (a real inconsistency worth knowing about), the old code silently
    produced a type_mismatch entry that leaked the raw hash string in
    value_a/value_b. This must never happen -- it's still reported, but
    always masked.
    """
    a = _snapshot_with_env_var(
        {"value": None, "redacted": True, "value_sha256": "hash_only_on_a"}
    )
    b = _snapshot_with_env_var({"value": "plaintext_oops", "redacted": False})

    entries = diff_snapshots(a, b)
    entry = find_entry(entries, KEY)

    assert entry is not None
    assert entry["value_a"] == "<redacted>"
    assert entry["value_b"] == "<redacted>"
    # The real hash and the real plaintext must never appear anywhere.
    serialized = str(entry)
    assert "hash_only_on_a" not in serialized
    assert "plaintext_oops" not in serialized


def test_redacted_both_sides_but_no_hash_present_is_reported_not_dropped():
    """
    Edge case found during review: if hash generation failed upstream and
    neither side has value_sha256, the old code treated this as "no
    drift" via the both-None short circuit in _compare_scalar. That's
    wrong -- an unverifiable redacted comparison must not look identical
    to a confirmed match. It must be surfaced, still masked.
    """
    a = _snapshot_with_env_var({"value": None, "redacted": True})
    b = _snapshot_with_env_var({"value": None, "redacted": True})

    entries = diff_snapshots(a, b)
    entry = find_entry(entries, KEY)

    assert entry is not None, (
        "an unverifiable redacted comparison (no hash on either side) "
        "must be reported, not silently treated as no drift"
    )
    assert entry["value_a"] == "<redacted>"
    assert entry["value_b"] == "<redacted>"