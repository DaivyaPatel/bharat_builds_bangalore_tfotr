import pytest
from src.collector.redaction import should_redact, process_config_item

SALT = "test_salt_12345"

def test_key_name_redaction():
    assert should_redact("DB_PASSWORD", "123")[0] == True
    assert should_redact("api_key_v2", "abc")[0] == True
    assert should_redact("session_id", "xyz")[0] == True
    
    # Innocent key name
    assert should_redact("feature_flag", "true")[0] == False

def test_value_shape_redaction():
    # Fake AWS Key
    assert should_redact("innocent_key", "AKIAIOSFODNN7EXAMPLE")[0] == True
    # JWT
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI.eyJzdWIiOiIxMjM0NTY3ODkw.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    assert should_redact("my_auth", jwt_token)[0] == True
    # Slack token
    assert should_redact("slack", "xoxb-1234-5678-abcdef")[0] == True
    # Connection string
    dsn = "postgres://admin:secret123@localhost:5432/db"
    assert should_redact("db_url", dsn)[0] == True

def test_high_entropy_redaction():
    # High entropy string > 20 chars
    random_str = "aB3$kL9#mP2!qR8*zV5&xY"
    assert should_redact("unknown_config", random_str)[0] == True

def test_no_plaintext_in_output():
    fake_aws_key = "AKIAIOSFODNN7EXAMPLE"
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI.eyJzdWIiOiIxMjM0NTY3ODkw.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    random_str = "aB3$kL9#mP2!qR8*zV5&xY"
    dsn = "postgres://admin:secret123@localhost:5432/db"

    test_cases = [
        ("aws_key", fake_aws_key),
        ("token", jwt_token),
        ("random", random_str),
        ("db", dsn)
    ]

    for key, val in test_cases:
        res = process_config_item(key, val, SALT)
        assert res["redacted"] == True
        assert res["value"] is None
        assert "value_sha256" in res
        # Ensure plaintext is not in the output dict
        assert val not in str(res)

def test_non_redacted_output():
    res = process_config_item("feature_new_ui", "false", SALT)
    assert res["redacted"] == False
    assert res["value"] == "false"
