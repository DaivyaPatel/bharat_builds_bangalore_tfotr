import re
import math
import hashlib

KEY_NAME_PATTERNS = [
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "private_key", "credential", "auth", "session", "cookie",
    "signature", "salt", "dsn", "connection_string", "_key", "access_key"
]

VALUE_SHAPE_PATTERNS = [
    r"AKIA[0-9A-Z]{16}",
    r"ASIA[0-9A-Z]{16}",
    r"-----BEGIN .* PRIVATE KEY-----",
    r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+", # JWT approx
    r"ghp_[a-zA-Z0-9]{36}",
    r"github_pat_[a-zA-Z0-9_]{82}",
    r"xox[baprs]-[a-zA-Z0-9]+",
    r"sk_live_[a-zA-Z0-9]+"
]

# Connection string with credentials e.g., postgres://user:pass@host
CONNECTION_STRING_CREDS_PATTERN = r"[a-zA-Z0-9+.-]+://[^:]+:[^@]+@.+"

def _calculate_entropy(text: str) -> float:
    if not text:
        return 0.0
    entropy = 0.0
    length = len(text)
    char_counts = {}
    for char in text:
        char_counts[char] = char_counts.get(char, 0) + 1
    for count in char_counts.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

def should_redact(key_name: str, value: str) -> tuple[bool, str]:
    """Returns (should_redact, reason)"""
    # 1. Key-name pattern matching
    key_lower = key_name.lower()
    for pattern in KEY_NAME_PATTERNS:
        if pattern in key_lower:
            return True, "key_name"

    # 2. Value shape heuristics
    if value:
        # Known credential shapes
        for pattern in VALUE_SHAPE_PATTERNS:
            if re.search(pattern, value):
                return True, "shape_heuristic"
        
        # Connection string with credentials
        if re.search(CONNECTION_STRING_CREDS_PATTERN, value):
            return True, "connection_string"

        # Entropy check
        if len(value) > 20 and _calculate_entropy(value) > 4.0:
            return True, "entropy"

    return False, ""

def redact_value(value: str, salt: str, reason: str) -> dict:
    hasher = hashlib.sha256()
    hasher.update((salt + value).encode('utf-8'))
    value_sha256 = hasher.hexdigest()
    
    return {
        "value": None,
        "redacted": True,
        "redaction_reason": reason,
        "value_sha256": value_sha256
    }

def process_config_item(key_name: str, value: str, salt: str) -> dict:
    """Processes a config item and returns either the raw value or a redacted dict."""
    redact, reason = should_redact(key_name, value)
    if redact:
        return redact_value(value, salt, reason)
    return {
        "value": value,
        "redacted": False
    }
