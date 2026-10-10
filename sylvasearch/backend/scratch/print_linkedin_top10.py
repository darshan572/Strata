import sys
sys.path.insert(0, ".")
from app.search.engine import SearchEngine
from app.indexer.index import InvertedIndex
from app.database import get_connection
from app.main import load_page_ranks

index = InvertedIndex()
conn = get_connection()
rows = conn.execute("SELECT id, title, content, url FROM documents").fetchall()
for r in rows:
    index.add_document(r["id"], {"title": r["title"] or "", "text": r["content"] or "", "url": r["url"]})
conn.close()
engine = SearchEngine(index, load_page_ranks())
results = engine.search("LinkedIn")[:10]
for idx, r in enumerate(results, 1):
    print(f"#{idx}: ID={r['id']} URL={r['url']}")
