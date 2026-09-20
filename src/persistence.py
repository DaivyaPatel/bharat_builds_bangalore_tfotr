"""
persistence.py

DL-017: DynamoDB persistence for DriftRecords.

Table: driftlens-drift-records
PK: pair (e.g. "staging::production")
SK: key  (e.g. "lambda:checkout/env_vars/FEATURE_NEW_CHECKOUT")

Core behavior: this is what turns drift detection into a time series.
On each write:
  - If a drift already exists under the same (pair, key), AND its
    value_a, value_b, and kind are unchanged, we KEEP its original
    first_seen_diverged timestamp.
  - If anything about the drift is different (including if it's brand
    new), we treat it as freshly diverged and set first_seen_diverged
    to now.

Uses real boto3 against a real DynamoDB table. No mocking.
"""

import boto3
from datetime import datetime, timezone

TABLE_NAME = "driftlens-drift-records"
REGION = "ap-south-1"

_dynamodb = boto3.resource("dynamodb", region_name=REGION)
_table = _dynamodb.Table(TABLE_NAME) #type:ignore


def _now_iso() -> str:
    """Current UTC time in the same ISO 8601 format used throughout the project."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_same_drift(existing_item: dict, new_drift: dict) -> bool:
    """
    Decide whether an existing stored drift and a newly-computed drift
    are "the same ongoing divergence" for purposes of keeping
    first_seen_diverged.

    Matching fields: value_a, value_b, kind.
    Deliberately NOT matching on severity/rule_id, since those are
    derived from value_a/value_b/kind by the severity rules (DL-009) -
    if the underlying values match, severity will recompute identically
    anyway, so comparing it separately would be redundant.
    """
    return (
        existing_item.get("value_a") == new_drift.get("value_a")
        and existing_item.get("value_b") == new_drift.get("value_b")
        and existing_item.get("kind") == new_drift.get("kind")
    )


def persist_drift(drift: dict) -> dict:
    """
    Write one drift record to DynamoDB, preserving first_seen_diverged
    if this is the same ongoing drift as what's already stored.

    `drift` is expected to be a dict with at least:
        pair, key, kind, value_a, value_b
    plus whatever else the caller has already computed
    (severity, rule_id, attribution, etc.)

    Returns the item as actually written (including whichever
    first_seen_diverged was chosen), so the caller can inspect it.
    """
    pair = drift["pair"]
    key = drift["key"]

    existing_response = _table.get_item(Key={"pair": pair, "key": key})
    existing_item = existing_response.get("Item")

    now = _now_iso()

    item = dict(drift)  # shallow copy, don't mutate the caller's dict
    item["last_confirmed"] = now

    if existing_item is not None and _is_same_drift(existing_item, drift):
        # Same ongoing drift: keep the original first_seen_diverged.
        item["first_seen_diverged"] = existing_item["first_seen_diverged"]
    else:
        # Either brand new, or the values/kind changed - treat as freshly diverged.
        item["first_seen_diverged"] = now

    _table.put_item(Item=item)
    return item


def get_drift(pair: str, key: str) -> dict | None:
    """Fetch one stored drift record by its pair+key, or None if not found."""
    response = _table.get_item(Key={"pair": pair, "key": key})
    return response.get("Item")


def delete_drift(pair: str, key: str) -> None:
    """
    Remove a stored drift record. Used when a drift has been resolved
    (the two environments no longer differ on this key) and should no
    longer appear as ongoing.
    """
    _table.delete_item(Key={"pair": pair, "key": key})


def _list_stored_keys_for_pair(pair: str) -> list[str]:
    """
    Return every key currently stored under this pair, following
    pagination if the pair has more drift records than one Query page.
    """
    keys = []
    last_evaluated_key = None

    while True:
        query_kwargs = {
            "KeyConditionExpression": "pair = :pair",
            "ExpressionAttributeValues": {":pair": pair},
        }
        if last_evaluated_key:
            query_kwargs["ExclusiveStartKey"] = last_evaluated_key

        response = _table.query(**query_kwargs)
        keys.extend(item["key"] for item in response.get("Items", []))

        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    return keys


def reconcile_drifts(pair: str, current_drifts: list[dict]) -> dict:
    """
    Remove any stored drift under this pair that no longer appears in
    the latest diff run - meaning the divergence has been resolved.

    current_drifts: the fresh list of drift dicts from this run's diff
    (each expected to have a "key" field), for this same pair.

    A malformed entry missing "key" is skipped rather than crashing
    the whole reconciliation, but it IS reported back so the caller
    can see something went wrong instead of it being silently dropped.

    Returns a dict:
        {"resolved_keys": [...], "skipped_malformed_entries": [...]}
    """
    current_keys = set()
    skipped_malformed_entries = []

    for drift in current_drifts:
        if "key" not in drift:
            skipped_malformed_entries.append(drift)
            continue
        current_keys.add(drift["key"])

    stored_keys = _list_stored_keys_for_pair(pair)
    resolved_keys = [key for key in stored_keys if key not in current_keys]

    for key in resolved_keys:
        delete_drift(pair, key)

    return {
        "resolved_keys": resolved_keys,
        "skipped_malformed_entries": skipped_malformed_entries,
    }