from src.time_travel_diff import time_travel_diff


class FakeResolver:
    def __init__(self, before_snapshot, now_snapshot):
        self.before_snapshot = before_snapshot
        self.now_snapshot = now_snapshot
        self.get_snapshot_at_calls = []
        self.get_latest_snapshot_calls = []

    def get_snapshot_at(self, environment, at_timestamp):
        self.get_snapshot_at_calls.append((environment, at_timestamp))
        return self.before_snapshot

    def get_latest_snapshot(self, environment):
        self.get_latest_snapshot_calls.append(environment)
        return self.now_snapshot


def _minimal_snapshot(region="ap-south-1", env_vars=None):
    return {
        "region": region,
        "resources": [{
            "resource_type": "lambda",
            "logical_name": "checkout",
            "resource_arn": "arn:aws:lambda:ap-south-1:111:function:checkout",
            "config": {"env_vars": env_vars or {}},
        }],
    }


def test_time_travel_diff_detects_a_flipped_flag():
    before = _minimal_snapshot(env_vars={"FEATURE_X": {"value": "false", "redacted": False}})
    now = _minimal_snapshot(env_vars={"FEATURE_X": {"value": "true", "redacted": False}})

    resolver = FakeResolver(before, now)
    result = time_travel_diff(resolver, "production", "2026-09-11T00:00:00Z")

    assert len(result) == 1
    assert result[0]["key"] == "lambda:checkout/env_vars/FEATURE_X"
    assert result[0]["kind"] == "value_mismatch"
    assert result[0]["value_a"] == "false"
    assert result[0]["value_b"] == "true"


def test_time_travel_diff_returns_empty_list_when_nothing_changed():
    same = _minimal_snapshot(env_vars={"FEATURE_X": {"value": "true", "redacted": False}})

    resolver = FakeResolver(same, same)
    result = time_travel_diff(resolver, "production", "2026-09-11T00:00:00Z")

    assert result == []


def test_time_travel_diff_calls_resolver_with_correct_environment_and_timestamp():
    before = _minimal_snapshot()
    now = _minimal_snapshot()
    resolver = FakeResolver(before, now)

    time_travel_diff(resolver, "production", "2026-09-11T00:00:00Z")

    assert resolver.get_snapshot_at_calls == [("production", "2026-09-11T00:00:00Z")]
    assert resolver.get_latest_snapshot_calls == ["production"]


def test_time_travel_diff_detects_resource_added_since_before():
    before = {"region": "ap-south-1", "resources": []}
    now = _minimal_snapshot(env_vars={"FEATURE_X": {"value": "true", "redacted": False}})

    resolver = FakeResolver(before, now)
    result = time_travel_diff(resolver, "production", "2026-09-11T00:00:00Z")

    assert len(result) == 1
    assert result[0]["kind"] == "missing_in_a"
    assert result[0]["key"] == "lambda:checkout"


def test_time_travel_diff_detects_resource_removed_since_before():
    before = _minimal_snapshot(env_vars={"FEATURE_X": {"value": "true", "redacted": False}})
    now = {"region": "ap-south-1", "resources": []}

    resolver = FakeResolver(before, now)
    result = time_travel_diff(resolver, "production", "2026-09-11T00:00:00Z")

    assert len(result) == 1
    assert result[0]["kind"] == "missing_in_b"
    assert result[0]["key"] == "lambda:checkout"


def test_time_travel_diff_uses_diff_engine_kinds_only_no_severity_or_attribution():
    before = _minimal_snapshot(env_vars={"FEATURE_X": {"value": "false", "redacted": False}})
    now = _minimal_snapshot(env_vars={"FEATURE_X": {"value": "true", "redacted": False}})

    resolver = FakeResolver(before, now)
    result = time_travel_diff(resolver, "production", "2026-09-11T00:00:00Z")

    for entry in result:
        assert "severity" not in entry
        assert "rule_id" not in entry
        assert "attribution" not in entry


def test_time_travel_diff_works_for_any_environment_name_not_just_production():
    before = _minimal_snapshot(env_vars={"X": {"value": "1", "redacted": False}})
    now = _minimal_snapshot(env_vars={"X": {"value": "2", "redacted": False}})

    resolver = FakeResolver(before, now)
    result = time_travel_diff(resolver, "staging", "2026-09-11T00:00:00Z")

    assert resolver.get_snapshot_at_calls == [("staging", "2026-09-11T00:00:00Z")]
    assert len(result) == 1