from handler import lambda_handler
import json

# Test /environments
event = {"httpMethod": "GET", "path": "/environments"}
print(json.dumps(lambda_handler(event, None), indent=2))

# Test /comparisons/{id}
event = {"httpMethod": "GET", "path": "/comparisons/anything"}
print(json.dumps(lambda_handler(event, None), indent=2))