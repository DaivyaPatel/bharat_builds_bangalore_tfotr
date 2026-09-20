from datetime import datetime, timedelta
from src.attribution_query import find_candidate_events
from src.attribution_scoring import score_attribution


def lambda_handler(event, context):
    print("Attribute handler invoked with event:", event)
    drifts = event.get("drifts", [])

    if not drifts:
        print("No drifts to attribute, skipping.")
        return event

    # Only query Athena for critical drifts, to save query time during the hackathon.
    # Non-critical drifts are left untouched -- attribution stays whatever it already
    # was (typically None/unset), never forced to a canned "not attributed" value.
    for drift in drifts:
        if drift.get("severity") != "critical":
            continue

        key = drift.get("key", "")
        window_end = datetime.utcnow()
        window_start = window_end - timedelta(days=7)

        try:
            print(f"Running Athena query for critical drift: {key}")
            candidate_events = find_candidate_events(
                key,
                window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            drift["attribution"] = score_attribution(candidate_events)
        except Exception as e:
            print(f"Failed to attribute drift {key}: {e}")
            drift["attribution"] = {"confidence": "none", "narrative": "Attribution failed."}

    return event