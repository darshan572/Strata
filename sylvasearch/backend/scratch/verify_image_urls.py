import urllib.request

urls = [
    ("LinkedIn Logo", "https://upload.wikimedia.org/wikipedia/commons/c/ca/LinkedIn_logo_initials.png"),
    ("Python Logo", "https://www.python.org/static/community_logos/python-logo-master-v3-TM.png"),
    ("AI Image", "https://images.unsplash.com/photo-1677442136019-21780ecad995?auto=format&fit=crop&w=800&q=80")
]
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
for name, u in urls:
    req = urllib.request.Request(u, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[{name}] Status {resp.status}, Content-Type: {resp.headers.get('Content-Type')}, URL: {u}")
    except Exception as e:
        print(f"[{name}] ERROR: {e}, URL: {u}")
