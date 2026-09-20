import uuid
import boto3
import pytest
from botocore.exceptions import NoCredentialsError, ClientError

from src.persistence import persist_drift, reconcile_drifts, get_drift, delete_drift, REGION


def _has_aws_credentials():
    try:
        boto3.client("sts", region_name=REGION).get_caller_identity()
        return True
    except (NoCredentialsError, ClientError, Exception):
        return False


requires_aws = pytest.mark.skipif(
    not _has_aws_credentials(),
    reason="No valid AWS credentials configured.",
)


def _unique_key(suffix):
    return f"test/reconcile_{uuid.uuid4().hex[:8]}_{suffix}"


@requires_aws
def test_reconcile_deletes_drift_no_longer_present():
    pair = "staging::production"
    key_resolved = _unique_key("resolved")
    key_ongoing = _unique_key("ongoing")

    try:
        persist_drift({"pair": pair, "key": key_resolved, "kind": "value_mismatch", "value_a": "a", "value_b": "b"})
        persist_drift({"pair": pair, "key": key_ongoing, "kind": "value_mismatch", "value_a": "c", "value_b": "d"})

        current_drifts = [{"key": key_ongoing, "kind": "value_mismatch", "value_a": "c", "value_b": "d"}]
        result = reconcile_drifts(pair, current_drifts)

        assert key_resolved in result["resolved_keys"]
        assert key_ongoing not in result["resolved_keys"]
        assert result["skipped_malformed_entries"] == []
        assert get_drift(pair, key_resolved) is None
        assert get_drift(pair, key_ongoing) is not None
    finally:
        delete_drift(pair, key_resolved)
        delete_drift(pair, key_ongoing)


@requires_aws
def test_reconcile_deletes_nothing_when_all_drifts_still_present():
    pair = "staging::production"
    key = _unique_key("stillhere")

    try:
        persist_drift({"pair": pair, "key": key, "kind": "value_mismatch", "value_a": "a", "value_b": "b"})

        current_drifts = [{"key": key, "kind": "value_mismatch", "value_a": "a", "value_b": "b"}]
        result = reconcile_drifts(pair, current_drifts)

        assert result["resolved_keys"] == []
        assert get_drift(pair, key) is not None
    finally:
        delete_drift(pair, key)


@requires_aws
def test_reconcile_deletes_everything_when_current_drifts_is_empty():
    pair = "staging::production"
    key = _unique_key("nowfixed")

    try:
        persist_drift({"pair": pair, "key": key, "kind": "value_mismatch", "value_a": "a", "value_b": "b"})

        result = reconcile_drifts(pair, [])

        assert key in result["resolved_keys"]
        assert get_drift(pair, key) is None
    finally:
        delete_drift(pair, key)


@requires_aws
def test_reconcile_only_affects_the_given_pair_not_others():
    pair_a = "staging::production"
    pair_b = "staging::qa"
    key_a = _unique_key("pairA")
    key_b = _unique_key("pairB")

    try:
        persist_drift({"pair": pair_a, "key": key_a, "kind": "value_mismatch", "value_a": "a", "value_b": "b"})
        persist_drift({"pair": pair_b, "key": key_b, "kind": "value_mismatch", "value_a": "c", "value_b": "d"})

        result = reconcile_drifts(pair_a, [])

        assert key_a in result["resolved_keys"]
        assert get_drift(pair_a, key_a) is None
        assert get_drift(pair_b, key_b) is not None
    finally:
        delete_drift(pair_a, key_a)
        delete_drift(pair_b, key_b)


@requires_aws
def test_reconcile_returns_empty_resolved_list_when_nothing_stored_for_pair():
    pair = "staging::production"
    result = reconcile_drifts(pair, [{"key": "irrelevant", "kind": "value_mismatch", "value_a": "a", "value_b": "b"}])
    assert isinstance(result["resolved_keys"], list)


@requires_aws
def test_reconcile_skips_malformed_entry_without_crashing():
    pair = "staging::production"
    key = _unique_key("edgecase")

    try:
        persist_drift({"pair": pair, "key": key, "kind": "value_mismatch", "value_a": "a", "value_b": "b"})

        malformed_entry = {"kind": "value_mismatch", "value_a": "a", "value_b": "b"}
        current_drifts = [{"key": key, "kind": "value_mismatch", "value_a": "a", "value_b": "b"}, malformed_entry]

        result = reconcile_drifts(pair, current_drifts)

        assert malformed_entry in result["skipped_malformed_entries"]
        assert key not in result["resolved_keys"]
        assert get_drift(pair, key) is not None
    finally:
        delete_drift(pair, key)


@requires_aws
def test_reconcile_still_resolves_valid_entries_when_others_are_malformed():
    pair = "staging::production"
    key_valid = _unique_key("valid")
    key_resolved = _unique_key("resolved")

    try:
        persist_drift({"pair": pair, "key": key_valid, "kind": "value_mismatch", "value_a": "a", "value_b": "b"})
        persist_drift({"pair": pair, "key": key_resolved, "kind": "value_mismatch", "value_a": "c", "value_b": "d"})

        malformed_entry = {"kind": "value_mismatch", "value_a": "x", "value_b": "y"}
        current_drifts = [{"key": key_valid, "kind": "value_mismatch", "value_a": "a", "value_b": "b"}, malformed_entry]

        result = reconcile_drifts(pair, current_drifts)

        assert key_resolved in result["resolved_keys"]
        assert malformed_entry in result["skipped_malformed_entries"]
        assert get_drift(pair, key_valid) is not None
        assert get_drift(pair, key_resolved) is None
    finally:
        delete_drift(pair, key_valid)
        delete_drift(pair, key_resolved)