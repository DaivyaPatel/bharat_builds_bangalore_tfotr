"""
test_persistence.py

DL-017 acceptance test: run the pipeline twice, first_seen_diverged
does not move on run two; changes to the drift reset it.

These tests hit REAL DynamoDB (no mocking), per the team's decision to
wire in real AWS directly. That means teammates without AWS credentials
configured cannot run these specific tests - they are skipped
gracefully in that case, rather than crashing the whole test suite.
"""

import os
import time
import uuid

import boto3
import pytest
from botocore.exceptions import NoCredentialsError, ClientError

from src.persistence import persist_drift, get_drift, delete_drift, TABLE_NAME, REGION


def _has_aws_credentials() -> bool:
    """
    Real check, not a guess: try an actual, cheap AWS call and see if it
    succeeds. This is the only reliable way to know credentials are both
    present AND valid (not just present but expired/wrong).
    """
    try:
        boto3.client("sts", region_name=REGION).get_caller_identity()
        return True
    except (NoCredentialsError, ClientError, Exception):
        return False


requires_aws = pytest.mark.skipif(
    not _has_aws_credentials(),
    reason="No valid AWS credentials configured - DL-017 tests need real DynamoDB access.",
)


def _unique_key() -> str:
    """Avoid collisions between test runs / parallel developers hitting the same table."""
    return f"test/persistence_{uuid.uuid4().hex[:8]}"


@requires_aws
def test_first_seen_diverged_is_set_on_first_write():
    pair = "staging::production"
    key = _unique_key()

    drift = {
        "pair": pair,
        "key": key,
        "kind": "value_mismatch",
        "value_a": "true",
        "value_b": "false",
    }

    try:
        result = persist_drift(drift)
        assert result["first_seen_diverged"] == result["last_confirmed"]
        assert result["pair"] == pair
        assert result["key"] == key
    finally:
        delete_drift(pair, key)


@requires_aws
def test_first_seen_diverged_does_not_move_on_repeat_write():
    pair = "staging::production"
    key = _unique_key()

    drift = {
        "pair": pair,
        "key": key,
        "kind": "value_mismatch",
        "value_a": "true",
        "value_b": "false",
    }

    try:
        first_result = persist_drift(drift)
        time.sleep(1.5)  # ensure timestamps would differ if (incorrectly) reset
        second_result = persist_drift(drift)

        assert second_result["first_seen_diverged"] == first_result["first_seen_diverged"]
        assert second_result["last_confirmed"] != first_result["last_confirmed"]
    finally:
        delete_drift(pair, key)


@requires_aws
def test_first_seen_diverged_resets_when_values_change():
    pair = "staging::production"
    key = _unique_key()

    original = {
        "pair": pair,
        "key": key,
        "kind": "value_mismatch",
        "value_a": "true",
        "value_b": "false",
    }
    changed = {
        "pair": pair,
        "key": key,
        "kind": "value_mismatch",
        "value_a": "true",
        "value_b": "CHANGED_VALUE",
    }

    try:
        first_result = persist_drift(original)
        time.sleep(1.5)
        second_result = persist_drift(changed)

        assert second_result["first_seen_diverged"] != first_result["first_seen_diverged"]
        assert second_result["value_b"] == "CHANGED_VALUE"
    finally:
        delete_drift(pair, key)


@requires_aws
def test_first_seen_diverged_resets_when_kind_changes_even_if_values_look_similar():
    """
    A missing_in_b with value_a="true" is a fundamentally different
    situation than a value_mismatch that happens to also have
    value_a="true". Matching on kind too (not just values) is the
    documented design decision for DL-017.
    """
    pair = "staging::production"
    key = _unique_key()

    as_mismatch = {
        "pair": pair,
        "key": key,
        "kind": "value_mismatch",
        "value_a": "true",
        "value_b": "true",  # same value on both sides, but...
    }
    as_missing = {
        "pair": pair,
        "key": key,
        "kind": "missing_in_b",
        "value_a": "true",
        "value_b": None,
    }

    try:
        first_result = persist_drift(as_mismatch)
        time.sleep(1.5)
        second_result = persist_drift(as_missing)

        assert second_result["first_seen_diverged"] != first_result["first_seen_diverged"]
        assert second_result["kind"] == "missing_in_b"
    finally:
        delete_drift(pair, key)


@requires_aws
def test_delete_drift_actually_removes_it():
    pair = "staging::production"
    key = _unique_key()

    drift = {
        "pair": pair,
        "key": key,
        "kind": "value_mismatch",
        "value_a": "true",
        "value_b": "false",
    }

    persist_drift(drift)
    assert get_drift(pair, key) is not None

    delete_drift(pair, key)
    assert get_drift(pair, key) is None


@requires_aws
def test_get_drift_returns_none_for_nonexistent_key():
    result = get_drift("staging::production", "test/definitely_does_not_exist_xyz")
    assert result is None


def test_persistence_module_targets_the_correct_table_and_region():
    """
    This one runs even without AWS credentials - it just checks the
    module's configuration constants, not a live call.
    """
    assert TABLE_NAME == "driftlens-drift-records"
    assert REGION == "ap-south-1"