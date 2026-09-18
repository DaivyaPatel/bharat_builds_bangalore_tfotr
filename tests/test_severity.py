"""
test_severity.py

DL-009 acceptance test: every rule ID gets its own isolated test so a
broken rule points at itself. Also runs the real fixtures end-to-end
through diff_engine + severity and checks against expected_drift_records.json.
"""

import json
import os

from src.diff_engine import diff_snapshots
from src.severity import (
    classify,
    classify_all,
    SEVERITY_CRITICAL,
    SEVERITY_SUSPICIOUS,
    SEVERITY_EXPECTED,
    RULE_FLAG_DIVERGED,
    RULE_KEY_MISSING,
    RULE_NUMERIC_DELTA,
    RULE_TYPE_MISMATCH,
    RULE_REDACTED_HASH_MISMATCH,
    RULE_STRING_NOT_ALLOWLISTED,
    RULE_ALLOWLIST_REGION,
    RULE_ALLOWLIST_ARN_ENV_NAME,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return json.load(f)


def find_entry(entries, key):
    for e in entries:
        if e["key"] == key:
            return e
    return None


# ---------------------------------------------------------------------
# Real fixture run end-to-end (diff_engine -> severity)
# ---------------------------------------------------------------------

def test_classify_all_matches_expected_drift_records_on_real_fixtures():
    staging = load_fixture("staging_snapshot.json")
    production = load_fixture("production_snapshot.json")
    expected = load_fixture("expected_drift_records.json")

    entries = diff_snapshots(staging, production)
    classified = classify_all(entries)

    expected_by_key = {e["key"]: e for e in expected}
    classified_by_key = {e["key"]: e for e in classified}

    assert set(classified_by_key.keys()) == set(expected_by_key.keys())

    for key, exp in expected_by_key.items():
        got = classified_by_key[key]
        assert got["severity"] == exp["severity"], f"{key}: severity mismatch"
        assert got["rule_id"] == exp["rule_id"], f"{key}: rule_id mismatch"


# ---------------------------------------------------------------------
# Only exactly three severity buckets exist, ever.
# ---------------------------------------------------------------------

def test_only_three_severity_values_are_possible():
    staging = load_fixture("staging_snapshot.json")
    production = load_fixture("production_snapshot.json")

    entries = diff_snapshots(staging, production)
    classified = classify_all(entries)

    severities = {e["severity"] for e in classified}
    assert severities.issubset({SEVERITY_CRITICAL, SEVERITY_SUSPICIOUS, SEVERITY_EXPECTED})


# ---------------------------------------------------------------------
# Isolated tests per rule ID, with small hand-built entries.
# ---------------------------------------------------------------------

def test_boolean_flag_diverged_is_critical():
    entry = {
        "key": "lambda:checkout/env_vars/FEATURE_X",
        "kind": "value_mismatch",
        "value_a": "true",
        "value_b": "false",
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_CRITICAL
    assert result["rule_id"] == RULE_FLAG_DIVERGED


def test_flag_like_key_name_diverged_is_critical_even_if_not_true_false_strings():
    entry = {
        "key": "lambda:checkout/env_vars/FEATURE_MODE",
        "kind": "value_mismatch",
        "value_a": "on",
        "value_b": "off",
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_CRITICAL
    assert result["rule_id"] == RULE_FLAG_DIVERGED


def test_missing_in_a_is_critical():
    entry = {
        "key": "lambda:checkout/env_vars/SOME_KEY",
        "kind": "missing_in_a",
        "value_a": None,
        "value_b": "true",
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_CRITICAL
    assert result["rule_id"] == RULE_KEY_MISSING


def test_missing_in_b_is_critical():
    entry = {
        "key": "lambda:checkout/env_vars/SOME_KEY",
        "kind": "missing_in_b",
        "value_a": "true",
        "value_b": None,
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_CRITICAL
    assert result["rule_id"] == RULE_KEY_MISSING


def test_numeric_delta_over_20_percent_is_suspicious():
    entry = {
        "key": "lambda:checkout/env_vars/API_TIMEOUT_MS",
        "kind": "value_mismatch",
        "value_a": "5000",
        "value_b": "7000",  # 40% increase
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_SUSPICIOUS
    assert result["rule_id"] == RULE_NUMERIC_DELTA


def test_numeric_delta_exactly_20_percent_is_not_flagged_as_numeric_delta():
    """Ticket says '>20%' — exactly 20% must not trigger this rule."""
    entry = {
        "key": "lambda:checkout/env_vars/SOME_NUMBER",
        "kind": "value_mismatch",
        "value_a": "100",
        "value_b": "120",  # exactly 20%
    }
    result = classify(entry)
    assert result["rule_id"] != RULE_NUMERIC_DELTA


def test_numeric_delta_under_20_percent_falls_to_string_not_allowlisted():
    entry = {
        "key": "lambda:checkout/env_vars/SOME_NUMBER",
        "kind": "value_mismatch",
        "value_a": "100",
        "value_b": "105",  # 5%
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_SUSPICIOUS
    assert result["rule_id"] == RULE_STRING_NOT_ALLOWLISTED


def test_type_mismatch_is_suspicious():
    entry = {
        "key": "lambda:checkout/env_vars/TIMEOUT",
        "kind": "type_mismatch",
        "value_a": 30,
        "value_b": "30",
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_SUSPICIOUS
    assert result["rule_id"] == RULE_TYPE_MISMATCH


def test_redacted_hash_mismatch_is_suspicious():
    entry = {
        "key": "lambda:checkout/env_vars/DB_PASSWORD",
        "kind": "value_mismatch",
        "value_a": "<redacted>",
        "value_b": "<redacted>",
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_SUSPICIOUS
    assert result["rule_id"] == RULE_REDACTED_HASH_MISMATCH


def test_string_not_on_allowlist_is_suspicious():
    entry = {
        "key": "lambda:checkout/env_vars/LOG_LEVEL",
        "kind": "value_mismatch",
        "value_a": "info",
        "value_b": "debug",
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_SUSPICIOUS
    assert result["rule_id"] == RULE_STRING_NOT_ALLOWLISTED


def test_region_diff_is_expected():
    entry = {
        "key": "environment/region",
        "kind": "value_mismatch",
        "value_a": "ap-south-1",
        "value_b": "ap-south-2",
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_EXPECTED
    assert result["rule_id"] == RULE_ALLOWLIST_REGION


def test_arn_differing_by_env_name_is_expected():
    entry = {
        "key": "lambda:checkout/resource_arn",
        "kind": "value_mismatch",
        "value_a": "arn:aws:lambda:ap-south-1:111122223333:function:staging-checkout",
        "value_b": "arn:aws:lambda:ap-south-2:111122223333:function:prod-checkout",
    }
    result = classify(entry)
    assert result["severity"] == SEVERITY_EXPECTED
    assert result["rule_id"] == RULE_ALLOWLIST_ARN_ENV_NAME


def test_classify_does_not_mutate_input_entry():
    entry = {
        "key": "environment/region",
        "kind": "value_mismatch",
        "value_a": "ap-south-1",
        "value_b": "ap-south-2",
    }
    original = dict(entry)
    classify(entry)
    assert entry == original