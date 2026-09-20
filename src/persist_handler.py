from src.persistence import persist_drift, reconcile_drifts
from src.bedrock_explainer import explain_drift


def lambda_handler(event, context):
    print("Persist handler invoked with event:", event)
    pair = event.get("pair")
    drifts = event.get("drifts", [])

    if not drifts:
        print("No drifts to persist, skipping.")
        return {"status": "skipped", "reason": "no drifts"}

    for drift in drifts:
        if drift.get("severity") != "critical":
            continue
        try:
            print(f"Generating explanation for critical drift: {drift.get('key')}")
            explanation = explain_drift(drift)
            if explanation:
                drift["explanation"] = explanation
        except Exception as e:
            print(f"Explanation failed for {drift.get('key')}: {e}")

    print(f"Persisting {len(drifts)} drifts to DynamoDB...")
    for drift in drifts:
        drift["pair"] = pair
        persist_drift(drift)

    print("Reconciling old drifts...")
    reconcile_drifts(pair, drifts)

    return {"status": "success", "processed_drifts": len(drifts)}