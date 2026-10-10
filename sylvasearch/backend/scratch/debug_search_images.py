import sys
sys.path.insert(0, ".")
from app.main import search

res = search(q="LinkedIn", category="images")
print(f"Total results: {res.get('total_results')}")
for idx, r in enumerate(res.get("results", []), 1):
    print(f"#{idx}: ID={r.get('id')}, Title={r.get('title')}, URL={r.get('image_url')}")
