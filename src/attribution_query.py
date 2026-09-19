import json
import time
import boto3

ATHENA_DATABASE = "driftlens_cloudtrail"
ATHENA_TABLE = "cloudtrail_logs"
ATHENA_OUTPUT_LOCATION = "s3://driftlens-athena-results-678360600444/"
ATHENA_REGION = "eu-north-1"

_athena = boto3.client("athena", region_name=ATHENA_REGION)

_WRITE_EVENT_PREFIXES = (
    "Put", "Update", "Create", "Delete", "Modify", "Set",
    "StartConfigurationSession", "TagResource", "UntagResource",
)

_RESOURCE_FIELD_CANDIDATES = (
    "functionName", "name", "resourceArn", "parameterName",
    "secretId", "clusterName", "serviceName", "taskDefinition",
)


def _escape_sql_string(value: str) -> str:
    return value.replace("'", "''")


def _run_query_and_wait(query, timeout_seconds=30, poll_interval=1.0):
    response = _athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": ATHENA_DATABASE},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT_LOCATION},
    )
    query_execution_id = response["QueryExecutionId"]

    elapsed = 0.0
    while elapsed < timeout_seconds:
        status_response = _athena.get_query_execution(QueryExecutionId=query_execution_id)
        state = status_response["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            return query_execution_id
        if state in ("FAILED", "CANCELLED"):
            reason = status_response["QueryExecution"]["Status"].get("StateChangeReason", "unknown reason")
            raise RuntimeError(f"Athena query {state}: {reason}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise RuntimeError(f"Athena query did not finish within {timeout_seconds}s (query_execution_id={query_execution_id})")


def _fetch_all_rows(query_execution_id):
    rows = []
    column_names = None
    next_token = None

    while True:
        kwargs = {"QueryExecutionId": query_execution_id}
        if next_token:
            kwargs["NextToken"] = next_token

        response = _athena.get_query_results(**kwargs)
        result_rows = response["ResultSet"]["Rows"]

        for row in result_rows:
            values = [cell.get("VarCharValue") for cell in row["Data"]]

            if column_names is None:
                column_names = values
                continue

            rows.append(dict(zip(column_names, values)))

        next_token = response.get("NextToken")
        if not next_token:
            break

    return rows


def _parse_json_field(raw_value):
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed


def _extract_resource_value(parsed_json):
    values = set()
    for field in _RESOURCE_FIELD_CANDIDATES:
        value = parsed_json.get(field)
        if isinstance(value, str):
            values.add(value)
    return values


def _matches_resource(row, resource_identifier):
    request_params = _parse_json_field(row.get("requestparameters"))
    response_elements = _parse_json_field(row.get("responseelements"))

    candidate_values = _extract_resource_value(request_params) | _extract_resource_value(response_elements)

    for value in candidate_values:
        if resource_identifier == value or resource_identifier in value:
            return True
    return False


def find_candidate_events(resource_identifier, window_start, window_end):
    safe_start = _escape_sql_string(window_start)
    safe_end = _escape_sql_string(window_end)

    query = f"""
        SELECT
            eventname,
            eventtime,
            useridentity.arn AS principal_arn,
            useridentity.type AS principal_type,
            sourceipaddress,
            eventid,
            requestparameters,
            responseelements
        FROM {ATHENA_DATABASE}.{ATHENA_TABLE}
        WHERE eventtime BETWEEN '{safe_start}' AND '{safe_end}'
        ORDER BY eventtime ASC
    """

    query_execution_id = _run_query_and_wait(query)
    raw_rows = _fetch_all_rows(query_execution_id)

    candidates = []
    for row in raw_rows:
        event_name = row.get("eventname")
        if event_name is None:
            continue

        if not any(event_name.startswith(prefix) for prefix in _WRITE_EVENT_PREFIXES):
            continue

        if not _matches_resource(row, resource_identifier):
            continue

        candidates.append({
            "event_name": event_name,
            "event_time": row.get("eventtime"),
            "principal_arn": row.get("principal_arn"),
            "principal_type": row.get("principal_type"),
            "source_ip": row.get("sourceipaddress"),
            "cloudtrail_event_id": row.get("eventid"),
        })

    return candidates