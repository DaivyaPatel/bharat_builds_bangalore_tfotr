"""
test_diff_engine.py

DL-008 acceptance test: runs the diff engine against the real fixtures
and checks the output. Also covers each `kind` in isolation with small,
hand-built inputs so a failure points at the exact rule that broke.
"""

import json
import os

from src.diff_engine import diff_snapshots, KIND_VALUE_MISMATCH, KIND_TYPE_MISMATCH, KIND_MISSING_IN_A, KIND_MISSING_IN_B

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return json.load(f)


def find_entry(entries, key):
    """Helper: pull out the one entry with a given key, or None."""
    for e in entries:
        if e["key"] == key:
            return e
    return None


# ---------------------------------------------------------------------
# Full fixture run — the actual DL-008 acceptance criterion
# ---------------------------------------------------------------------

def test_diff_against_real_fixtures_finds_all_expected_keys():
    staging = load_fixture("staging_snapshot.json")
    production = load_fixture("production_snapshot.json")

    result = diff_snapshots(staging, production)
    found_keys = {e["key"] for e in result}

    expected_keys = {
        "environment/region",
        "lambda:checkout/env_vars/API_TIMEOUT_MS",
        "lambda:checkout/env_vars/DB_PASSWORD",
        "lambda:checkout/env_vars/FEATURE_NEW_CHECKOUT",
        "lambda:checkout/env_vars/LEGACY_PAYMENT_FALLBACK",
        "lambda:checkout/resource_arn",
    }

    assert found_keys == expected_keys


def test_flipped_boolean_flag_is_value_mismatch():
    staging = load_fixture("staging_snapshot.json")
    production = load_fixture("production_snapshot.json")

    result = diff_snapshots(staging, production)
    entry = find_entry(result, "lambda:checkout/env_vars/FEATURE_NEW_CHECKOUT")

    assert entry is not None
    assert entry["kind"] == KIND_VALUE_MISMATCH
    assert entry["value_a"] == "true"
    assert entry["value_b"] == "false"


def test_key_missing_in_production_is_missing_in_b():
    staging = load_fixture("staging_snapshot.json")
    production = load_fixture("production_snapshot.json")

    result = diff_snapshots(staging, production)
    entry = find_entry(result, "lambda:checkout/env_vars/LEGACY_PAYMENT_FALLBACK")

    assert entry is not None
    assert entry["kind"] == KIND_MISSING_IN_B
    assert entry["value_a"] == "true"
    assert entry["value_b"] is None


def test_redacted_secret_mismatch_never_leaks_real_value():
    staging = load_fixture("staging_snapshot.json")
    production = load_fixture("production_snapshot.json")

    result = diff_snapshots(staging, production)
    entry = find_entry(result, "lambda:checkout/env_vars/DB_PASSWORD")

    assert entry is not None
    assert entry["kind"] == KIND_VALUE_MISMATCH
    # The diff engine must never surface the real value or the hash directly.
    assert entry["value_a"] == "<redacted>"
    assert entry["value_b"] == "<redacted>"


def test_region_difference_is_detected_as_value_mismatch():
    staging = load_fixture("staging_snapshot.json")
    production = load_fixture("production_snapshot.json")

    result = diff_snapshots(staging, production)
    entry = find_entry(result, "environment/region")

    assert entry is not None
    assert entry["kind"] == KIND_VALUE_MISMATCH
    assert entry["value_a"] == "ap-south-1"
    assert entry["value_b"] == "ap-south-2"


def test_no_drift_reported_for_identical_snapshots():
    staging = load_fixture("staging_snapshot.json")
    result = diff_snapshots(staging, staging)
    assert result == []


# ---------------------------------------------------------------------
# Isolated unit tests for each `kind`, with small hand-built snapshots.
# These exist so a broken rule points at itself, not just "fixtures failed".
# ---------------------------------------------------------------------

def _minimal_snapshot(region="ap-south-1", env_vars=None, resource_arn="arn:aws:lambda:ap-south-1:111122223333:function:test"):
    return {
        "schema_version": "1.0",
        "environment": "test",
        "region": region,
        "resources": [
            {
                "resource_type": "lambda",
                "logical_name": "checkout",
                "resource_arn": resource_arn,
                "config": {
                    "env_vars": env_vars or {}
                }
            }
        ]
    }


def test_type_mismatch_detected():
    a = _minimal_snapshot(env_vars={"TIMEOUT": {"value": 30, "redacted": False}})
    b = _minimal_snapshot(env_vars={"TIMEOUT": {"value": "30", "redacted": False}})

    result = diff_snapshots(a, b)
    entry = find_entry(result, "lambda:checkout/env_vars/TIMEOUT")

    assert entry is not None
    assert entry["kind"] == KIND_TYPE_MISMATCH


def test_missing_in_a_when_only_in_snapshot_b():
    a = _minimal_snapshot(env_vars={})
    b = _minimal_snapshot(env_vars={"NEW_FLAG": {"value": "true", "redacted": False}})

    result = diff_snapshots(a, b)
    entry = find_entry(result, "lambda:checkout/env_vars/NEW_FLAG")

    assert entry is not None
    assert entry["kind"] == KIND_MISSING_IN_A
    assert entry["value_a"] is None
    assert entry["value_b"] == "true"


def test_missing_in_b_when_only_in_snapshot_a():
    a = _minimal_snapshot(env_vars={"OLD_FLAG": {"value": "true", "redacted": False}})
    b = _minimal_snapshot(env_vars={})

    result = diff_snapshots(a, b)
    entry = find_entry(result, "lambda:checkout/env_vars/OLD_FLAG")

    assert entry is not None
    assert entry["kind"] == KIND_MISSING_IN_B
    assert entry["value_a"] == "true"
    assert entry["value_b"] is None


def test_resource_missing_entirely_in_one_environment():
    a = _minimal_snapshot()
    b = {
        "schema_version": "1.0",
        "environment": "test",
        "region": "ap-south-1",
        "resources": []
    }

    result = diff_snapshots(a, b)
    entry = find_entry(result, "lambda:checkout")

    assert entry is not None
    assert entry["kind"] == KIND_MISSING_IN_B


def test_diff_engine_module_has_no_boto3_dependency():
    """
    Checks diff_engine.py's own source and its direct imports, not the whole
    process's sys.modules — other modules in this repo (collectors) legitimately
    import boto3, and pytest runs everything in one process.
    """
    import ast
    import inspect
    import src.diff_engine as de

    source = inspect.getsource(de)
    tree = ast.parse(source)

    imported_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_names.append(node.module)

    assert not any("boto3" in name or "botocore" in name for name in imported_names)