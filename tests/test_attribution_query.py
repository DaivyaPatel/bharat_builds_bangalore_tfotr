import json
import boto3
import pytest
from botocore.exceptions import NoCredentialsError, ClientError

from src.attribution_query import (
    find_candidate_events,
    _parse_json_field,
    _extract_resource_value,
    _matches_resource,
    _escape_sql_string,
    ATHENA_REGION,
)


def _has_aws_credentials():
    try:
        boto3.client("sts", region_name=ATHENA_REGION).get_caller_identity()
        return True
    except (NoCredentialsError, ClientError, Exception):
        return False


requires_aws = pytest.mark.skipif(
    not _has_aws_credentials(),
    reason="No valid AWS credentials configured - attribution query tests need real Athena access.",
)


def test_parse_json_field_returns_empty_dict_for_none():
    assert _parse_json_field(None) == {}


def test_parse_json_field_returns_empty_dict_for_empty_string():
    assert _parse_json_field("") == {}


def test_parse_json_field_returns_empty_dict_for_json_null():
    assert _parse_json_field("null") == {}


def test_parse_json_field_returns_empty_dict_for_json_array():
    assert _parse_json_field("[1, 2, 3]") == {}


def test_parse_json_field_returns_empty_dict_for_invalid_json():
    assert _parse_json_field("not valid json {{{") == {}


def test_parse_json_field_returns_empty_dict_for_non_string_input():
    assert _parse_json_field(12345) == {}
    assert _parse_json_field([1, 2, 3]) == {}


def test_parse_json_field_parses_valid_dict():
    result = _parse_json_field('{"functionName": "prod-checkout"}')
    assert result == {"functionName": "prod-checkout"}


def test_extract_resource_value_pulls_known_fields():
    parsed = {"functionName": "prod-checkout", "unrelatedField": "ignore-me"}
    values = _extract_resource_value(parsed)
    assert values == {"prod-checkout"}


def test_extract_resource_value_ignores_non_string_field_values():
    parsed = {"functionName": {"nested": "object"}, "name": 12345}
    values = _extract_resource_value(parsed)
    assert values == set()


def test_extract_resource_value_collects_multiple_matching_fields():
    parsed = {"functionName": "prod-checkout", "resourceArn": "arn:aws:lambda:...:prod-checkout"}
    values = _extract_resource_value(parsed)
    assert values == {"prod-checkout", "arn:aws:lambda:...:prod-checkout"}


def test_extract_resource_value_returns_empty_set_for_empty_dict():
    assert _extract_resource_value({}) == set()


def test_matches_resource_true_when_request_params_match():
    row = {
        "requestparameters": json.dumps({"functionName": "prod-checkout"}),
        "responseelements": None,
    }
    assert _matches_resource(row, "prod-checkout") is True


def test_matches_resource_true_when_response_elements_match():
    row = {
        "requestparameters": None,
        "responseelements": json.dumps({"functionName": "prod-checkout"}),
    }
    assert _matches_resource(row, "prod-checkout") is True


def test_matches_resource_true_on_partial_substring_match():
    row = {
        "requestparameters": json.dumps({"resourceArn": "arn:aws:lambda:ap-south-1:111122223333:function:prod-checkout"}),
        "responseelements": None,
    }
    assert _matches_resource(row, "prod-checkout") is True


def test_matches_resource_false_when_no_field_matches():
    row = {
        "requestparameters": json.dumps({"functionName": "staging-checkout"}),
        "responseelements": None,
    }
    assert _matches_resource(row, "prod-checkout") is False


def test_matches_resource_false_when_both_fields_are_null():
    row = {"requestparameters": None, "responseelements": None}
    assert _matches_resource(row, "prod-checkout") is False


def test_matches_resource_false_when_fields_are_malformed_json():
    row = {"requestparameters": "{{{broken", "responseelements": "also broken"}
    assert _matches_resource(row, "prod-checkout") is False


def test_matches_resource_does_not_false_positive_on_unrelated_short_substring():
    row = {
        "requestparameters": json.dumps({"functionName": "prod-checkout-v2-extended"}),
        "responseelements": None,
    }
    assert _matches_resource(row, "checkout") is True
    assert _matches_resource(row, "checkout-v3") is False


def test_escape_sql_string_escapes_single_quotes():
    assert _escape_sql_string("O'Brien") == "O''Brien"


def test_escape_sql_string_leaves_normal_strings_unchanged():
    assert _escape_sql_string("prod-checkout") == "prod-checkout"


def test_escape_sql_string_handles_multiple_quotes():
    assert _escape_sql_string("a'b'c") == "a''b''c"


@requires_aws
def test_find_candidate_events_returns_list():
    results = find_candidate_events("checkout", "2026-09-18T00:00:00Z", "2026-09-20T00:00:00Z")
    assert isinstance(results, list)


@requires_aws
def test_find_candidate_events_only_returns_write_type_events():
    results = find_candidate_events("checkout", "2026-09-18T00:00:00Z", "2026-09-20T00:00:00Z")
    read_only_prefixes = ("Get", "List", "Describe")
    for event in results:
        assert not event["event_name"].startswith(read_only_prefixes)


@requires_aws
def test_find_candidate_events_result_shape_has_all_required_fields():
    results = find_candidate_events("checkout", "2026-09-18T00:00:00Z", "2026-09-20T00:00:00Z")
    required_fields = {"event_name", "event_time", "principal_arn", "principal_type", "source_ip", "cloudtrail_event_id"}
    for event in results:
        assert required_fields.issubset(event.keys())


@requires_aws
def test_find_candidate_events_returns_empty_list_for_nonexistent_resource():
    results = find_candidate_events(
        "definitely-does-not-exist-xyz-resource-name-12345",
        "2026-09-18T00:00:00Z",
        "2026-09-20T00:00:00Z",
    )
    assert results == []


@requires_aws
def test_find_candidate_events_respects_time_window():
    results = find_candidate_events("checkout", "2020-01-01T00:00:00Z", "2020-01-02T00:00:00Z")
    assert results == []


@requires_aws
def test_find_candidate_events_handles_sql_injection_attempt_safely():
    malicious_input = "checkout' OR '1'='1"
    results = find_candidate_events(malicious_input, "2026-09-18T00:00:00Z", "2026-09-20T00:00:00Z")
    assert isinstance(results, list)