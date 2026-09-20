import json
from datetime import datetime, timedelta
from src.attribution_query import run_cloudtrail_query, wait_and_get_results, parse_results
from src.attribution_scoring import score_attribution

def lambda_handler(event, context):
    print("Attribute handler invoked with event:", event)
    drifts = event.get("drifts", [])
    
    if not drifts:
        print("No drifts to attribute, skipping.")
        return event
        
    # We only attribute critical drifts during the hackathon to save Athena query time (3-10s per query)
    for drift in drifts:
        if drift.get("severity") == "critical":
            key = drift.get("key", "")
            # Roughly guess the time window: last 7 days since it's a hackathon demo
            window_end = datetime.utcnow()
            window_start = window_end - timedelta(days=7)
            
            try:
                print(f"Running Athena query for critical drift: {key}")
                execution_id = run_cloudtrail_query(key, window_start, window_end, region="eu-north-1")
                results = wait_and_get_results(execution_id, region="eu-north-1")
                parsed_events = parse_results(results)
                
                attribution = score_attribution(drift, parsed_events)
                drift["attribution"] = attribution
            except Exception as e:
                print(f"Failed to attribute drift {key}: {e}")
                drift["attribution"] = {"confidence": "none", "narrative": "Attribution failed."}
        else:
            drift["attribution"] = {"confidence": "none", "narrative": "Not attributed (non-critical)."}
            
    return event
