import json

with open("splink_clusters_test.json", encoding="utf-8") as f:
    data = json.load(f)

# for key, values in data.items():
#     # Check if None is inside the original_name list
#     if "null" in values.get("original_name", []):
#         print(f"Found null in 'original_name' for key: {key}")
#
#     # Check if None is inside the full name list
#     if "null" in values.get("full name", []):
#         print(f"Found null in 'full name' for key: {key}")
print(data.get("rowling j k"))