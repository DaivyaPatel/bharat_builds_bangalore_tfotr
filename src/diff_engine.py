"""
diff_engine.py

DL-008: Pure Python diff engine. Compares two EnvironmentSnapshot documents
and emits drift entries describing WHAT differs and WHAT KIND of difference
it is. Does NOT assign severity, rule_id, or attribution — those are added
by later stages (DL-009, DL-019) on top of this output.

No boto3 import. No AWS calls. This module only ever sees Python dicts
that were already loaded from JSON (fixtures, or real snapshots) by the
caller.
"""

from typing import Any, Optional


# The four allowed kinds. Nothing else is ever produced.
KIND_VALUE_MISMATCH = "value_mismatch"
KIND_TYPE_MISMATCH = "type_mismatch"
KIND_MISSING_IN_A = "missing_in_a"
KIND_MISSING_IN_B = "missing_in_b"


def _make_entry(key: str, kind: str, value_a: Any, value_b: Any) -> dict:
    """Build one bare drift entry: just enough to say what differs."""
    return {
        "key": key,
        "kind": kind,
        "value_a": value_a,
        "value_b": value_b,
    }


def _compare_scalar(key: str, value_a: Any, value_b: Any) -> Optional[dict]:
    """
    Compare two plain values (already extracted from wherever they live).
    Returns a drift entry dict, or None if they match.
    """
    if value_a is None and value_b is None:
        return None

    if type(value_a) is not type(value_b):
        return _make_entry(key, KIND_TYPE_MISMATCH, value_a, value_b)

    if value_a != value_b:
        return _make_entry(key, KIND_VALUE_MISMATCH, value_a, value_b)

    return None


def _resource_map(snapshot: dict) -> dict:
    """Index a snapshot's resources by logical_name for lookup."""
    return {r["logical_name"]: r for r in snapshot.get("resources", [])}


def _diff_env_vars(prefix: str, res_a: Optional[dict], res_b: Optional[dict]) -> list:
    """
    Compare the env_vars block of one resource between two snapshots.
    Handles redacted values by comparing value_sha256 instead of value.
    """
    entries = []

    env_a = (res_a or {}).get("config", {}).get("env_vars", {})
    env_b = (res_b or {}).get("config", {}).get("env_vars", {})

    all_keys = set(env_a.keys()) | set(env_b.keys())

    for var_name in sorted(all_keys):
        key = f"{prefix}/env_vars/{var_name}"

        entry_a = env_a.get(var_name)
        entry_b = env_b.get(var_name)

        if entry_a is None:
            entries.append(_make_entry(key, KIND_MISSING_IN_A, None, _display_value(entry_b)))
            continue
        if entry_b is None:
            entries.append(_make_entry(key, KIND_MISSING_IN_B, _display_value(entry_a), None))
            continue

        # Both sides have this variable. If either is redacted, this is a
        # redacted comparison: compare hashes only, and the output must
        # NEVER show anything but "<redacted>" for value_a/value_b — not
        # the hash, not the value, regardless of which side is redacted
        # or whether a hash is present at all.
        redacted_a = entry_a.get("redacted", False)
        redacted_b = entry_b.get("redacted", False)

        if redacted_a or redacted_b:
            hash_a = entry_a.get("value_sha256")
            hash_b = entry_b.get("value_sha256")

            if hash_a is None and hash_b is None:
                # Neither side has a hash to compare (e.g. hash generation
                # failed upstream, or one side was redacted without ever
                # producing a hash). We cannot verify sameness — this is
                # NOT the same as "no drift", so it must not be silently
                # dropped. Report it explicitly as a comparison we can't
                # verify, rather than staying quiet about it.
                entries.append(
                    _make_entry(key, KIND_TYPE_MISMATCH, "<redacted>", "<redacted>")
                )
                continue

            if hash_a != hash_b:
                # Covers: both hashes present and differ, OR only one side
                # has a hash at all (redaction inconsistency between
                # environments). Either way this is a real, reportable
                # difference, and the real hash value must never appear
                # in the output — only "<redacted>".
                entries.append(
                    _make_entry(key, KIND_VALUE_MISMATCH, "<redacted>", "<redacted>")
                )
            # else: hashes match exactly -> same secret in both envs, no drift.
        else:
            diff = _compare_scalar(key, entry_a.get("value"), entry_b.get("value"))
            if diff:
                entries.append(diff)

    return entries


def _display_value(entry: Optional[dict]) -> Any:
    """For a missing-on-one-side env var, show its value if not redacted."""
    if entry is None:
        return None
    if entry.get("redacted", False):
        return "<redacted>"
    return entry.get("value")


def _diff_resource_arns(prefix: str, res_a: Optional[dict], res_b: Optional[dict]) -> list:
    """Compare the resource_arn field itself between two snapshots."""
    if res_a is None or res_b is None:
        return []  # a missing resource entirely is its own case, not handled here

    key = f"{prefix}/resource_arn"
    diff = _compare_scalar(key, res_a.get("resource_arn"), res_b.get("resource_arn"))
    return [diff] if diff else []


def _diff_top_level_fields(snapshot_a: dict, snapshot_b: dict) -> list:
    """Compare simple top-level fields like region."""
    entries = []
    for field in ["region"]:
        key = f"environment/{field}"
        diff = _compare_scalar(key, snapshot_a.get(field), snapshot_b.get(field))
        if diff:
            entries.append(diff)
    return entries


def diff_snapshots(snapshot_a: dict, snapshot_b: dict) -> list:
    """
    Compare two EnvironmentSnapshot dicts (already loaded from JSON).

    snapshot_a is treated as "side A" (e.g. staging), snapshot_b as
    "side B" (e.g. production) — matching value_a / value_b naming.

    Returns a list of bare drift entries:
        { "key": ..., "kind": ..., "value_a": ..., "value_b": ... }

    Severity, rule_id, and attribution are NOT set here — that is DL-009
    and DL-019's job, layered on top of this output.
    """
    entries = []

    entries.extend(_diff_top_level_fields(snapshot_a, snapshot_b))

    resources_a = _resource_map(snapshot_a)
    resources_b = _resource_map(snapshot_b)

    all_resource_names = set(resources_a.keys()) | set(resources_b.keys())

    for logical_name in sorted(all_resource_names):
        res_a = resources_a.get(logical_name)
        res_b = resources_b.get(logical_name)
        resource_type = (res_a or res_b).get("resource_type", "resource") #type:ignore
        prefix = f"{resource_type}:{logical_name}"

        if res_a is None:
            entries.append(_make_entry(prefix, KIND_MISSING_IN_A, None, res_b.get("resource_arn"))) #type:ignore
            continue
        if res_b is None:
            entries.append(_make_entry(prefix, KIND_MISSING_IN_B, res_a.get("resource_arn"), None))
            continue

        entries.extend(_diff_env_vars(prefix, res_a, res_b))
        entries.extend(_diff_resource_arns(prefix, res_a, res_b))

    return entries