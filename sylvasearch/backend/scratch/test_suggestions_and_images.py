import urllib.request
import json
import urllib.parse

print("=== TESTING /suggest ENDPOINT ===")
prefixes = ["Li", "Link", "LinkedIn", "Py", "Python", "AI", "what", "nonexistentxyz123"]
for p in prefixes:
    url = f"http://127.0.0.1:8000/suggest?q={urllib.parse.quote(p)}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            print(f"Prefix '{p}': suggestions = {data.get('suggestions')}")
    except Exception as e:
        print(f"Prefix '{p}' error: {e}")

print("\n=== TESTING /search?category=images ENDPOINT ===")
img_queries = ["LinkedIn", "Python", "AI", "Quantum", "UnknownQueryXYZ12345"]
for q in img_queries:
    url = f"http://127.0.0.1:8000/search?q={urllib.parse.quote(q)}&category=images"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            results = data.get("results", [])
            print(f"\nImage Query: '{q}' (returned {len(results)} images, total_results={data.get('total_results')})")
            for idx, img in enumerate(results[:3], 1):
                print(f"  #{idx} Title: {img.get('title')}")
                print(f"       Image URL: {img.get('image_url')}")
                print(f"       Source: {img.get('source')} | Score: {img.get('score')}")
    except Exception as e:
        print(f"Image Query '{q}' error: {e}")
