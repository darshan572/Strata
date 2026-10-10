import urllib.request
import json
import urllib.parse

queries = [
    "LinkedIn",
    "LinkedIn login",
    "what is LinkedIn",
    "LinkedIn history",
    "Python",
    "Python beginner tutorial",
    "latest AI news"
]

print("=== TESTING LIVE FASTAPI BACKEND (http://127.0.0.1:8000/search) ===")
for q in queries:
    url = f"http://127.0.0.1:8000/search?q={urllib.parse.quote(q)}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            print(f"\nQuery: '{q}' (returned {len(results)} results, total={data.get('total')})")
            for idx, r in enumerate(results[:3], 1):
                print(f"  #{idx}: [{r.get('title')}]")
                print(f"       URL: {r.get('url')}")
                print(f"       Score: {r.get('score', 0):.4f}")
    except Exception as e:
        print(f"\nQuery '{q}' FAILED: {e}")
