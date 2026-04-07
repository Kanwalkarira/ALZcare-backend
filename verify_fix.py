import json
import os

def test_logic(val):
    print(f"Testing value: {val[:20]}...")
    json_str = val.strip()
    if json_str.startswith('{') and json_str.endswith('}'):
        try:
            key_dict = json.loads(json_str)
            print("Successfully parsed as JSON")
            return "DICT"
        except Exception as e:
            print(f"Failed to parse as JSON: {e}")
            return "ERROR"
    else:
        print("Treating as FILE PATH")
        return "PATH"

# Case 1: JSON String
json_val = '{"type": "service_account", "project_id": "test"}'
assert test_logic(json_val) == "DICT"

# Case 2: File Path
path_val = "/app/service-account.json"
assert test_logic(path_val) == "PATH"

# Case 3: JSON with newlines (like the user's error)
json_val_multi = '{\n  "type": "service_account"\n}'
assert test_logic(json_val_multi) == "DICT"

print("All tests passed!")
