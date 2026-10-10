import sys
sys.path.insert(0, ".")
from app.database import get_connection

conn = get_connection()
docs = conn.execute("SELECT id, url, title FROM documents WHERE url LIKE '%python%' LIMIT 20").fetchall()
print("Python docs in corpus:")
for d in docs[:10]:
    print(f"  ID {d['id']}: {d['url']} ({d['title']})")

ai_docs = conn.execute("SELECT id, url, title FROM documents WHERE url LIKE '%ai%' OR url LIKE '%artificial%' OR title LIKE '%AI%' LIMIT 10").fetchall()
print("\nAI docs in corpus:")
for d in ai_docs:
    print(f"  ID {d['id']}: {d['url']} ({d['title']})")
conn.close()
