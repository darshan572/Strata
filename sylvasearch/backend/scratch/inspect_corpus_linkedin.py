import sys
sys.path.insert(0, ".")
from app.database import get_connection

conn = get_connection()
rows = conn.execute("SELECT id, url, title FROM documents WHERE url LIKE '%linkedin%' OR title LIKE '%linkedin%'").fetchall()
conn.close()

print(f"Total LinkedIn documents in corpus: {len(rows)}")
for r in rows:
    print(f"ID {r['id']}: URL: {r['url']} | Title: {r['title']}")
