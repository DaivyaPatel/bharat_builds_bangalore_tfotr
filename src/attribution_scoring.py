from datetime import datetime, timezone, timedelta

IST_OFFSET = timedelta(hours=5, minutes=30)


def _format_ist(event_time_iso):
    if not event_time_iso:
        return "an unknown time"
    try:
        dt_utc = datetime.strptime(event_time_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return "an unknown time"
    dt_ist = dt_utc + IST_OFFSET
    return dt_ist.strftime("%H:%M IST on %d %b")


def _short_principal(principal_arn):
    if not principal_arn:
        return "an unknown principal"
    if "/" in principal_arn:
        return principal_arn.rsplit("/", 1)[-1]
    return principal_arn


def score_attribution(candidate_events):
    if not candidate_events:
        return {
            "confidence": "none",
            "event_name": None,
            "event_time": None,
            "principal_arn": None,
            "principal_type": None,
            "source_ip": None,
            "cloudtrail_event_id": None,
            "narrative": "No attributable event found for this divergence.",
        }

    if len(candidate_events) == 1:
        event = candidate_events[0]
        principal = _short_principal(event.get("principal_arn"))
        time_str = _format_ist(event.get("event_time"))
        narrative = (
            f"Set by {principal} via {event.get('event_name')} at {time_str}."
        )
        return {
            "confidence": "high",
            "event_name": event.get("event_name"),
            "event_time": event.get("event_time"),
            "principal_arn": event.get("principal_arn"),
            "principal_type": event.get("principal_type"),
            "source_ip": event.get("source_ip"),
            "cloudtrail_event_id": event.get("cloudtrail_event_id"),
            "narrative": narrative,
        }

    most_recent = max(candidate_events, key=lambda e: e.get("event_time") or "")
    principal = _short_principal(most_recent.get("principal_arn"))
    time_str = _format_ist(most_recent.get("event_time"))
    narrative = (
        f"Several candidate events found in the divergence window; "
        f"most likely {most_recent.get('event_name')} by {principal} at {time_str}, "
        f"but not uniquely confirmed."
    )
    return {
        "confidence": "medium",
        "event_name": most_recent.get("event_name"),
        "event_time": most_recent.get("event_time"),
        "principal_arn": most_recent.get("principal_arn"),
        "principal_type": most_recent.get("principal_type"),
        "source_ip": most_recent.get("source_ip"),
        "cloudtrail_event_id": most_recent.get("cloudtrail_event_id"),
        "narrative": narrative,
    }