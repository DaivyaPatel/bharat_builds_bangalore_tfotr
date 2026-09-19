from src.attribution_scoring import score_attribution


def test_zero_events_yields_none_confidence():
    result = score_attribution([])
    assert result["confidence"] == "none"
    assert result["narrative"] == "No attributable event found for this divergence."
    assert result["event_name"] is None
    assert result["principal_arn"] is None


def test_single_event_yields_high_confidence():
    events = [{
        "event_name": "ssm:PutParameter",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:user/rahul",
        "principal_type": "IAMUser",
        "source_ip": "203.0.113.4",
        "cloudtrail_event_id": "e1f2",
    }]
    result = score_attribution(events)
    assert result["confidence"] == "high"
    assert result["principal_arn"] == "arn:aws:iam::111122223333:user/rahul"
    assert "rahul" in result["narrative"]
    assert "07:44 IST on 12 Sep" in result["narrative"]
    assert result["event_name"] == "ssm:PutParameter"


def test_multiple_events_yields_medium_confidence():
    events = [
        {
            "event_name": "ssm:PutParameter",
            "event_time": "2026-09-12T02:14:55Z",
            "principal_arn": "arn:aws:iam::111122223333:user/rahul",
            "principal_type": "IAMUser",
            "source_ip": "203.0.113.4",
            "cloudtrail_event_id": "e1f2",
        },
        {
            "event_name": "lambda:UpdateFunctionConfiguration",
            "event_time": "2026-09-12T02:10:00Z",
            "principal_arn": "arn:aws:iam::111122223333:role/ci-deploy-role",
            "principal_type": "AssumedRole",
            "source_ip": "203.0.113.9",
            "cloudtrail_event_id": "f2a3",
        },
    ]
    result = score_attribution(events)
    assert result["confidence"] == "medium"
    assert "not uniquely confirmed" in result["narrative"]
    assert result["event_time"] == "2026-09-12T02:14:55Z"


def test_medium_confidence_picks_most_recent_event():
    older = {
        "event_name": "OldEvent",
        "event_time": "2026-09-12T01:00:00Z",
        "principal_arn": "arn:aws:iam::111122223333:user/older-user",
        "principal_type": "IAMUser",
        "source_ip": "1.1.1.1",
        "cloudtrail_event_id": "old1",
    }
    newer = {
        "event_name": "NewEvent",
        "event_time": "2026-09-12T05:00:00Z",
        "principal_arn": "arn:aws:iam::111122223333:user/newer-user",
        "principal_type": "IAMUser",
        "source_ip": "2.2.2.2",
        "cloudtrail_event_id": "new1",
    }
    result = score_attribution([older, newer])
    assert result["event_name"] == "NewEvent"
    assert result["principal_arn"] == "arn:aws:iam::111122223333:user/newer-user"


def test_missing_event_time_does_not_crash():
    events = [{
        "event_name": "ssm:PutParameter",
        "event_time": None,
        "principal_arn": "arn:aws:iam::111122223333:user/rahul",
        "principal_type": "IAMUser",
        "source_ip": "203.0.113.4",
        "cloudtrail_event_id": "e1f2",
    }]
    result = score_attribution(events)
    assert "an unknown time" in result["narrative"]
    assert result["confidence"] == "high"


def test_missing_principal_arn_does_not_crash():
    events = [{
        "event_name": "ssm:PutParameter",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": None,
        "principal_type": None,
        "source_ip": "203.0.113.4",
        "cloudtrail_event_id": "e1f2",
    }]
    result = score_attribution(events)
    assert "an unknown principal" in result["narrative"]


def test_malformed_event_time_does_not_crash():
    events = [{
        "event_name": "ssm:PutParameter",
        "event_time": "not-a-valid-timestamp",
        "principal_arn": "arn:aws:iam::111122223333:user/rahul",
        "principal_type": "IAMUser",
        "source_ip": "203.0.113.4",
        "cloudtrail_event_id": "e1f2",
    }]
    result = score_attribution(events)
    assert "an unknown time" in result["narrative"]


def test_result_shape_always_has_all_required_fields():
    required_fields = {
        "confidence", "event_name", "event_time", "principal_arn",
        "principal_type", "source_ip", "cloudtrail_event_id", "narrative",
    }
    for events in ([], [{"event_name": "X", "event_time": "2026-09-12T02:14:55Z", "principal_arn": "a", "principal_type": "b", "source_ip": "c", "cloudtrail_event_id": "d"}]):
        if isinstance(events, dict):
            events = [events]
        result = score_attribution(events)
        assert required_fields.issubset(result.keys())


def test_principal_arn_shortened_to_username_in_narrative():
    events = [{
        "event_name": "ssm:PutParameter",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:role/ci-deploy-role",
        "principal_type": "AssumedRole",
        "source_ip": "203.0.113.4",
        "cloudtrail_event_id": "e1f2",
    }]
    result = score_attribution(events)
    assert "ci-deploy-role" in result["narrative"]
    assert "arn:aws:iam" not in result["narrative"]


def test_ci_deploy_role_flagged_as_automated_not_human():
    events = [{
        "event_name": "lambda:UpdateFunctionConfiguration",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:role/ci-deploy-role",
        "principal_type": "AssumedRole",
        "source_ip": "203.0.113.9",
        "cloudtrail_event_id": "f2a3",
    }]
    result = score_attribution(events)
    assert "automated deploy" in result["narrative"]
    assert "IaC/CI-driven" in result["narrative"]
    assert result["confidence"] == "high"


def test_terraform_role_flagged_as_automated():
    events = [{
        "event_name": "lambda:UpdateFunctionConfiguration",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:role/terraform-execution-role",
        "principal_type": "AssumedRole",
        "source_ip": "203.0.113.9",
        "cloudtrail_event_id": "f2a3",
    }]
    result = score_attribution(events)
    assert "automated deploy" in result["narrative"]


def test_github_actions_role_flagged_as_automated():
    events = [{
        "event_name": "lambda:UpdateFunctionConfiguration",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:role/github-actions-deploy",
        "principal_type": "AssumedRole",
        "source_ip": "203.0.113.9",
        "cloudtrail_event_id": "f2a3",
    }]
    result = score_attribution(events)
    assert "automated deploy" in result["narrative"]


def test_human_iam_user_never_flagged_as_automated():
    events = [{
        "event_name": "ssm:PutParameter",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:user/rahul",
        "principal_type": "IAMUser",
        "source_ip": "203.0.113.4",
        "cloudtrail_event_id": "e1f2",
    }]
    result = score_attribution(events)
    assert "automated deploy" not in result["narrative"]
    assert "Set by rahul" in result["narrative"]


def test_generic_assumed_role_with_no_ci_keyword_not_falsely_flagged():
    events = [{
        "event_name": "lambda:UpdateFunctionConfiguration",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:role/some-other-role",
        "principal_type": "AssumedRole",
        "source_ip": "203.0.113.9",
        "cloudtrail_event_id": "f2a3",
    }]
    result = score_attribution(events)
    assert "automated deploy" not in result["narrative"]
    assert "Set by some-other-role" in result["narrative"]


def test_medium_confidence_also_flags_ci_role_correctly():
    ci_event = {
        "event_name": "lambda:UpdateFunctionConfiguration",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:role/ci-deploy-role",
        "principal_type": "AssumedRole",
        "source_ip": "203.0.113.9",
        "cloudtrail_event_id": "f2a3",
    }
    older_event = {
        "event_name": "ssm:PutParameter",
        "event_time": "2026-09-12T01:00:00Z",
        "principal_arn": "arn:aws:iam::111122223333:user/rahul",
        "principal_type": "IAMUser",
        "source_ip": "203.0.113.4",
        "cloudtrail_event_id": "e1f2",
    }
    result = score_attribution([older_event, ci_event])
    assert result["confidence"] == "medium"
    assert "automated deploy" in result["narrative"]
    assert "not uniquely confirmed" in result["narrative"]


def test_ci_detection_is_case_insensitive():
    events = [{
        "event_name": "lambda:UpdateFunctionConfiguration",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:role/CI-Deploy-Role",
        "principal_type": "AssumedRole",
        "source_ip": "203.0.113.9",
        "cloudtrail_event_id": "f2a3",
    }]
    result = score_attribution(events)
    assert "automated deploy" in result["narrative"]


def test_ci_detection_requires_assumed_role_type_not_just_name():
    events = [{
        "event_name": "lambda:UpdateFunctionConfiguration",
        "event_time": "2026-09-12T02:14:55Z",
        "principal_arn": "arn:aws:iam::111122223333:user/ci-deploy-role",
        "principal_type": "IAMUser",
        "source_ip": "203.0.113.9",
        "cloudtrail_event_id": "f2a3",
    }]
    result = score_attribution(events)
    assert "automated deploy" not in result["narrative"]