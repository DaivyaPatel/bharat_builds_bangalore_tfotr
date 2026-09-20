from handler import lambda_handler
import json

# Test /environments
event = {"httpMethod": "GET", "resource": "/environments"}
print(json.dumps(lambda_handler(event, None), indent=2))

# Test /comparisons/{id}
event = {"httpMethod": "GET", "resource": "/comparisons/{id}"}
print(json.dumps(lambda_handler(event, None), indent=2))