"""
severity.py

DL-009: Severity rules. Takes the bare drift entries produced by
diff_engine.py (DL-008) — {key, kind, value_a, value_b} — and adds
`severity` and `rule_id`. Does NOT touch attribution (DL-019) or
explanation (DL-028, stretch).

Exactly three severity buckets, per PRD §5.2 and TICKETS.md DL-009.
No fourth bucket. Ever.
"""

import re
from typing import Any

from src.diff_engine import (
    KIND_VALUE_MISMATCH,
    KIND_TYPE_MISMATCH,
    KIND_MISSING_IN_A,
    KIND_MISSING_IN_B,
)

SEVERITY_CRITICAL = "critical"
SEVERITY_SUSPICIOUS = "suspicious"
SEVERITY_EXPECTED = "expected"

# Rule IDs — one per distinguishable reason, matching the fixtures exactly.
RULE_FLAG_DIVERGED = "R-FLAG-DIVERGED"
RULE_KEY_MISSING = "R-KEY-MISSING"
RULE_NUMERIC_DELTA = "R-NUMERIC-DELTA"
RULE_TYPE_MISMATCH = "R-TYPE-MISMATCH"
RULE_REDACTED_HASH_MISMATCH = "R-REDACTED-HASH-MISMATCH"
RULE_STRING_NOT_ALLOWLISTED = "R-STRING-NOT-ALLOWLISTED"
RULE_ALLOWLIST_REGION = "R-ALLOWLIST-REGION"
RULE_ALLOWLIST_ACCOUNT_ID = "R-ALLOWLIST-ACCOUNT-ID"
RULE_ALLOWLIST_ARN_ENV_NAME = "R-ALLOWLIST-ARN-ENV-NAME"
RULE_ALLOWLIST_HOSTNAME_ENV_NAME = "R-ALLOWLIST-HOSTNAME-ENV-NAME"

# Numeric drift beyond this fraction is "suspicious". Exactly 20% is NOT
# suspicious per TICKETS.md wording ("differs >20%") — must exceed it.
NUMERIC_DELTA_THRESHOLD = 0.20

# Key-name signal for "this is a flag" even when the value isn't a clean
# true/false string. Secondary signal only; the string check is primary.
_FLAG_NAME_PATTERN = re.compile(
    r"(flag|feature|enabled|_on\b|_off\b|toggle)", re.IGNORECASE
)

_BOOL_STRINGS = {"true", "false"}

# Environment names we recognise for the ARN/hostname "expected" allowlist.
# Extend this list, don't hardcode new environment names elsewhere.
_KNOWN_ENV_NAMES = {"staging", "production", "prod", "dev", "development", "test"}


def _is_redacted_entry(value: Any) -> bool:
    return value == "<redacted>"


def _is_boolean_like(value_a: Any, value_b: Any) -> bool:
    """True if both sides look like a boolean flag: string 'true'/'false'."""
    if not isinstance(value_a, str) or not isinstance(value_b, str):
        return False
    return value_a.lower() in _BOOL_STRINGS and value_b.lower() in _BOOL_STRINGS


def _key_looks_like_flag(key: str) -> bool:
    return bool(_FLAG_NAME_PATTERN.search(key))


def _try_parse_number(value: Any):
    """Return a float if value parses cleanly as a number, else None."""
    if isinstance(value, bool):  # bool is a subclass of int; exclude explicitly
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _numeric_percent_delta(a: float, b: float) -> float:
    """Percent change relative to the larger-magnitude side's counterpart (a)."""
    if a == 0:
        # Avoid division by zero. Any change from exactly 0 is a full swing.
        return float("inf") if b != 0 else 0.0
    return abs(b - a) / abs(a)


def _is_expected_region_diff(key: str) -> bool:
    return key == "environment/region"


def _is_expected_account_id_diff(key: str) -> bool:
    return key == "environment/account_id"


def _contains_env_name(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(env in lowered for env in _KNOWN_ENV_NAMES)


def _is_expected_arn_env_diff(key: str, value_a: Any, value_b: Any) -> bool:
    if not key.endswith("/resource_arn"):
        return False
    return _contains_env_name(value_a) and _contains_env_name(value_b)


def _is_expected_hostname_env_diff(key: str, value_a: Any, value_b: Any) -> bool:
    if "hostname" not in key.lower():
        return False
    return _contains_env_name(value_a) and _contains_env_name(value_b)


def classify(entry: dict) -> dict:
    """
    Take one bare drift entry from diff_engine.diff_snapshots() and return
    a new dict with `severity` and `rule_id` added. Does not mutate the
    input entry.
    """
    key = entry["key"]
    kind = entry["kind"]
    value_a = entry.get("value_a")
    value_b = entry.get("value_b")

    result = dict(entry)

    # --- missing_in_a / missing_in_b: always critical, per TICKETS.md ---
    if kind in (KIND_MISSING_IN_A, KIND_MISSING_IN_B):
        result["severity"] = SEVERITY_CRITICAL
        result["rule_id"] = RULE_KEY_MISSING
        return result

    # --- type_mismatch: always suspicious ---
    if kind == KIND_TYPE_MISMATCH:
        result["severity"] = SEVERITY_SUSPICIOUS
        result["rule_id"] = RULE_TYPE_MISMATCH
        return result

    # From here on, kind == value_mismatch.

    # --- redacted-hash mismatch: always suspicious, checked before
    #     anything else, since a redacted value must never be treated
    #     as a plain string or number. ---
    if _is_redacted_entry(value_a) or _is_redacted_entry(value_b):
        result["severity"] = SEVERITY_SUSPICIOUS
        result["rule_id"] = RULE_REDACTED_HASH_MISMATCH
        return result

    # --- expected allowlist checks, before critical/suspicious, so a
    #     region or ARN diff is never miscaught as a "string not
    #     allowlisted" suspicious case. ---
    if _is_expected_region_diff(key):
        result["severity"] = SEVERITY_EXPECTED
        result["rule_id"] = RULE_ALLOWLIST_REGION
        return result

    if _is_expected_account_id_diff(key):
        result["severity"] = SEVERITY_EXPECTED
        result["rule_id"] = RULE_ALLOWLIST_ACCOUNT_ID
        return result

    if _is_expected_arn_env_diff(key, value_a, value_b):
        result["severity"] = SEVERITY_EXPECTED
        result["rule_id"] = RULE_ALLOWLIST_ARN_ENV_NAME
        return result

    if _is_expected_hostname_env_diff(key, value_a, value_b):
        result["severity"] = SEVERITY_EXPECTED
        result["rule_id"] = RULE_ALLOWLIST_HOSTNAME_ENV_NAME
        return result

    # --- critical: boolean/flag diverged ---
    if _is_boolean_like(value_a, value_b) or _key_looks_like_flag(key):
        result["severity"] = SEVERITY_CRITICAL
        result["rule_id"] = RULE_FLAG_DIVERGED
        return result

    # --- suspicious: numeric differs >20% ---
    num_a = _try_parse_number(value_a)
    num_b = _try_parse_number(value_b)
    if num_a is not None and num_b is not None:
        if _numeric_percent_delta(num_a, num_b) > NUMERIC_DELTA_THRESHOLD:
            result["severity"] = SEVERITY_SUSPICIOUS
            result["rule_id"] = RULE_NUMERIC_DELTA
            return result
        # Numeric but within threshold — still not "expected" (nothing
        # allowlisted it), so it falls through to the default below.

    # --- suspicious: string not on any allowlist (default catch-all
    #     for value_mismatch that matched nothing above) ---
    result["severity"] = SEVERITY_SUSPICIOUS
    result["rule_id"] = RULE_STRING_NOT_ALLOWLISTED
    return result


def classify_all(entries: list) -> list:
    """Apply classify() to every entry in a diff_snapshots() result list."""
    return [classify(e) for e in entries]